"""
Configuration IPv4 de l'interface filaire via NetworkManager (nmcli).

Remplace l'ancien apply_network.sh (dhcpcd, supprimé en v0.3.1).

Principe :
  - on travaille sur la connexion NetworkManager ethernet active (ex. "Wired connection 1") ;
  - validation stricte des champs avant toute modification ;
  - application en tâche de fond, après un court délai, pour que la réponse HTTP
    parte avant que l'adresse change ;
  - garde-fou : si la passerelle (IP fixe) ou une adresse IPv4 (DHCP) n'est pas
    joignable après bascule, retour automatique à la configuration précédente.

nmcli est appelé via sudo : une règle sudoers NOPASSWD limitée à /usr/bin/nmcli
est nécessaire pour l'utilisateur du service (voir install/build/60-services.sh).
"""

import ipaddress
import logging
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

NMCLI = '/usr/bin/nmcli'
APPLY_DELAY = 3        # secondes avant bascule (laisse partir la réponse HTTP)
VERIFY_TIMEOUT = 20    # secondes max pour valider la nouvelle config

_lock = threading.Lock()


class NetworkConfigError(ValueError):
    pass


# ─── Helpers nmcli ──────────────────────────────────────────────────────────

def _nmcli(*args, sudo=True, timeout=15):
    cmd = (['sudo', '-n', NMCLI] if sudo else [NMCLI]) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"nmcli {' '.join(args)} : {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def get_wired_connection():
    """Retourne (nom_connexion, interface) de la connexion ethernet active."""
    out = _nmcli('-t', '-f', 'NAME,TYPE,DEVICE', 'connection', 'show', '--active', sudo=False)
    for line in out.splitlines():
        # Les ':' dans le nom sont échappés en '\:' par nmcli -t
        parts = line.replace('\\:', '\x00').split(':')
        parts = [p.replace('\x00', ':') for p in parts]
        if len(parts) >= 3 and parts[1] == '802-3-ethernet':
            return parts[0], parts[2]
    raise RuntimeError("Aucune connexion ethernet active gérée par NetworkManager")


def get_current_ipv4(conn_name):
    """Réglages IPv4 enregistrés dans le profil NetworkManager."""
    fields = 'ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns,ipv4.ignore-auto-dns'
    out = _nmcli('-g', fields, 'connection', 'show', conn_name, sudo=False)
    vals = out.split('\n')
    vals += [''] * (5 - len(vals))
    return {
        'method': vals[0],
        'addresses': vals[1],
        'gateway': vals[2],
        'dns': vals[3].replace(' ', ''),
        'ignore_auto_dns': vals[4],
    }


def get_device_ipv4(device):
    """Adresses IPv4 réellement présentes sur l'interface (liste de 'a.b.c.d/nn')."""
    r = subprocess.run(['ip', '-4', '-o', 'addr', 'show', 'dev', device],
                       capture_output=True, text=True, timeout=5)
    return [line.split()[3] for line in r.stdout.splitlines() if 'inet' in line]


# ─── Validation ─────────────────────────────────────────────────────────────

def validate(net):
    """
    Valide la config réseau reçue de l'UI et renvoie la cible normalisée :
      {'method': 'auto'} ou
      {'method': 'manual', 'address': '192.168.1.50/24', 'gateway': ..., 'dns': '...'}
    Lève NetworkConfigError si invalide.
    """
    mode = (net.get('mode') or 'dhcp').strip().lower()
    if mode == 'dhcp':
        return {'method': 'auto'}
    if mode != 'static':
        raise NetworkConfigError(f"Mode réseau inconnu : {mode}")

    ip = (net.get('ip') or '').strip()
    mask = (net.get('netmask') or '').strip().lstrip('/')
    gw = (net.get('gateway') or '').strip()
    dns = (net.get('dns') or '').strip()

    if not ip or not mask or not gw:
        raise NetworkConfigError("IP fixe : adresse, masque et passerelle sont obligatoires")
    try:
        iface = ipaddress.IPv4Interface(f"{ip}/{mask}")
    except ValueError:
        raise NetworkConfigError(f"Adresse ou masque invalide : {ip} / {mask}")
    if iface.ip in (iface.network.network_address, iface.network.broadcast_address):
        raise NetworkConfigError(f"{ip} est l'adresse réseau ou de broadcast du sous-réseau")
    try:
        gw_ip = ipaddress.IPv4Address(gw)
    except ValueError:
        raise NetworkConfigError(f"Passerelle invalide : {gw}")
    if gw_ip not in iface.network:
        raise NetworkConfigError(f"La passerelle {gw} n'est pas dans le sous-réseau {iface.network}")
    if gw_ip == iface.ip:
        raise NetworkConfigError("L'adresse IP et la passerelle sont identiques")

    dns_list = []
    for d in dns.replace(';', ',').replace(' ', ',').split(','):
        if d:
            try:
                dns_list.append(str(ipaddress.IPv4Address(d)))
            except ValueError:
                raise NetworkConfigError(f"DNS invalide : {d}")
    if not dns_list:
        dns_list = [gw]   # à défaut, la box/passerelle fait office de DNS

    return {
        'method': 'manual',
        'address': iface.with_prefixlen,
        'gateway': str(gw_ip),
        'dns': ','.join(dns_list),
    }


def is_change_needed(target, current):
    if target['method'] == 'auto':
        return current['method'] != 'auto'
    return not (current['method'] == 'manual'
                and current['addresses'] == target['address']
                and current['gateway'] == target['gateway']
                and current['dns'] == target['dns'])


# ─── Application ────────────────────────────────────────────────────────────

def _modify(conn_name, s):
    if s['method'] == 'auto':
        _nmcli('connection', 'modify', conn_name,
               'ipv4.method', 'auto', 'ipv4.addresses', '', 'ipv4.gateway', '',
               'ipv4.dns', '', 'ipv4.ignore-auto-dns', 'no')
    else:
        _nmcli('connection', 'modify', conn_name,
               'ipv4.method', 'manual', 'ipv4.addresses', s['address'],
               'ipv4.gateway', s['gateway'], 'ipv4.dns', s['dns'],
               'ipv4.ignore-auto-dns', 'yes')
    _nmcli('connection', 'up', conn_name, timeout=45)


def _restore(conn_name, snap):
    args = ['connection', 'modify', conn_name,
            'ipv4.method', snap['method'] or 'auto',
            'ipv4.addresses', snap['addresses'],
            'ipv4.gateway', snap['gateway'],
            'ipv4.dns', snap['dns'],
            'ipv4.ignore-auto-dns', snap['ignore_auto_dns'] or 'no']
    _nmcli(*args)
    _nmcli('connection', 'up', conn_name, timeout=45)


def _verify(target, device):
    deadline = time.time() + VERIFY_TIMEOUT
    while time.time() < deadline:
        addrs = get_device_ipv4(device)
        if target['method'] == 'manual':
            if target['address'] in addrs:
                r = subprocess.run(['ping', '-c', '1', '-W', '2', target['gateway']],
                                   capture_output=True, timeout=5)
                if r.returncode == 0:
                    return True
        elif addrs:
            return True
        time.sleep(2)
    return False


def _apply_worker(target, conn_name, device, snapshot):
    with _lock:
        time.sleep(APPLY_DELAY)
        try:
            logger.info(f"Réseau : application {target} sur '{conn_name}' ({device})")
            _modify(conn_name, target)
            if _verify(target, device):
                logger.info(f"Réseau : nouvelle configuration active, IP {get_device_ipv4(device)}")
                return
            logger.error("Réseau : vérification échouée (passerelle injoignable), retour arrière")
        except Exception as e:
            logger.error(f"Réseau : échec de l'application ({e}), retour arrière")
        try:
            _restore(conn_name, snapshot)
            logger.warning(f"Réseau : configuration précédente restaurée, IP {get_device_ipv4(device)}")
        except Exception as e:
            logger.critical(f"Réseau : ÉCHEC du retour arrière : {e}")


def schedule_apply(net):
    """
    Valide puis planifie l'application en tâche de fond.
    Renvoie un dict décrivant ce qui va se passer (pour l'UI).
    Lève NetworkConfigError (config invalide) ou RuntimeError (nmcli/sudo KO).
    """
    target = validate(net)
    conn_name, device = get_wired_connection()
    current = get_current_ipv4(conn_name)

    if not is_change_needed(target, current):
        return {'changed': False}

    # Vérifie que sudo nmcli est autorisé AVANT de lancer quoi que ce soit
    _nmcli('general', 'status')

    threading.Thread(target=_apply_worker,
                     args=(target, conn_name, device, current),
                     daemon=True).start()

    result = {'changed': True, 'method': target['method'], 'delay': APPLY_DELAY}
    if target['method'] == 'manual':
        result['new_ip'] = target['address'].split('/')[0]
    return result
