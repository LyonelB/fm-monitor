# ⚡ Guide Rapide - Clé USB Bootable FM Monitor

## 🎯 Résumé en 5 étapes

### 1️⃣ Créer la clé USB bootable
- Télécharger **Ubuntu Server 22.04 LTS** : https://ubuntu.com/download/server
- Utiliser **Rufus** (Windows) ou **Balena Etcher** (Mac/Linux)
- Flasher l'ISO sur une **clé USB de 16GB minimum**

### 2️⃣ Installer Ubuntu sur la clé
- Booter sur la clé USB (F12, F9 ou Esc au démarrage)
- Suivre l'installation d'Ubuntu
- ⚠️ **IMPORTANT** : Installer UNIQUEMENT sur la clé USB, pas sur le disque dur !
- Utilisateur : `fmradio` / Mot de passe : [votre choix]
- Activer OpenSSH server

### 3️⃣ Installer le logiciel FM Monitor
```bash
# Option A : Via clé USB
# Copier fm-monitor.tar.gz et usb-autoinstall.sh sur une autre clé USB
# Monter la clé et copier les fichiers
sudo mkdir /mnt/usb
sudo mount /dev/sdb1 /mnt/usb
cp /mnt/usb/fm-monitor.tar.gz ~/
cp /mnt/usb/usb-autoinstall.sh ~/
tar -xzf fm-monitor.tar.gz
cd fm-monitor
sudo ./usb-autoinstall.sh

# Option B : Via réseau (si connexion Internet disponible)
# Transférer via scp ou télécharger depuis un serveur
```

### 4️⃣ Configurer
```bash
cd fm-monitor
nano config.json
```

Modifier :
- `"frequency": "98.5M"` → votre fréquence FM
- `"sender_email"` et `"sender_password"` → vos identifiants email
- `"recipient_emails"` → destinataires des alertes
- `"station.name"` → nom de votre radio

### 5️⃣ Démarrer
```bash
sudo systemctl enable fm-monitor
sudo systemctl start fm-monitor

# Ou simplement
./start-fm-monitor.sh
```

Accéder à : `http://[IP-du-PC]:5000`

---

## 🔑 Touches de boot par fabricant

| Fabricant | Touche Boot Menu |
|-----------|-----------------|
| Dell      | F12             |
| HP        | F9 ou Esc       |
| Lenovo    | F12 ou F8       |
| Asus      | F8 ou Esc       |
| Acer      | F12             |
| MSI       | F11             |
| Gigabyte  | F12             |

---

## 📋 Commandes essentielles

```bash
# Démarrer le service
./start-fm-monitor.sh

# Arrêter le service
./stop-fm-monitor.sh

# Voir le statut
./status-fm-monitor.sh

# Trouver l'IP du système
hostname -I

# Voir les logs en direct
sudo journalctl -u fm-monitor -f

# Tester la clé RTL-SDR
rtl_test

# Arrêter proprement le système
sudo shutdown -h now
```

---

## 🌐 Configuration réseau

### WiFi (si pas de câble Ethernet)

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

Ajouter :
```yaml
network:
  version: 2
  wifis:
    wlan0:
      dhcp4: true
      access-points:
        "NomDuWiFi":
          password: "MotDePasseWiFi"
```

Appliquer :
```bash
sudo netplan apply
```

### IP fixe (optionnel)

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

```yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 192.168.1.100/24
      gateway4: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
```

```bash
sudo netplan apply
```

---

## 🔧 Dépannage rapide

### Le PC ne boot pas sur la clé
- Désactiver **Secure Boot** dans le BIOS
- Activer le mode **UEFI** (pas Legacy)

### Pas de son
- Vérifier la fréquence dans `config.json`
- Tester : `rtl_fm -f 98.5M -M fm -s 200k -r 48k - | aplay -r 48k -f S16_LE`

### La clé RTL-SDR n'est pas détectée
```bash
lsusb | grep RTL
# Si rien, vérifier que la clé est bien branchée
```

### Le service ne démarre pas
```bash
sudo journalctl -u fm-monitor -n 50
# Voir les erreurs et corriger config.json
```

---

## 💡 Astuces

### Accès SSH depuis un autre PC
```bash
ssh fmradio@[IP-du-système-FM]
```

### Copier des fichiers via SSH
```bash
scp fichier.txt fmradio@[IP]:~/
```

### Surveiller plusieurs radios
Créer plusieurs instances avec différents ports dans `config.json` :
```json
"web": {
  "port": 5001  // Deuxième instance
}
```

---

## 📊 Checklist avant production

- [ ] Ubuntu installé sur la clé USB
- [ ] fm-monitor installé avec `usb-autoinstall.sh`
- [ ] `config.json` configuré (fréquence, email)
- [ ] Clé RTL-SDR détectée (`rtl_test`)
- [ ] Service activé (`systemctl enable fm-monitor`)
- [ ] Interface web accessible
- [ ] Email de test envoyé et reçu
- [ ] Pare-feu configuré (`ufw status`)

---

**Votre clé USB est maintenant prête !** 🎉

Branchez-la sur n'importe quel PC, bootez, et surveillez votre radio FM en quelques minutes !
