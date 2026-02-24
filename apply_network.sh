#!/bin/bash

# Script pour appliquer la configuration réseau depuis config.json
# Appelé automatiquement après la sauvegarde de la configuration

set -e

CONFIG_FILE="/home/graffiti/fm-monitor/config.json"
LOG_FILE="/home/graffiti/fm-monitor/network_apply.log"

# Fonction de logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================"
log "Application de la configuration réseau"
log "========================================"

# Vérifier que config.json existe
if [ ! -f "$CONFIG_FILE" ]; then
    log "ERREUR: config.json introuvable"
    exit 1
fi

# Vérifier que jq est installé
if ! command -v jq &> /dev/null; then
    log "ERREUR: jq n'est pas installé"
    log "Installez-le avec: sudo apt install jq"
    exit 1
fi

# Lire la configuration réseau
MODE=$(jq -r '.network.mode // "dhcp"' "$CONFIG_FILE")
IP=$(jq -r '.network.ip // ""' "$CONFIG_FILE")
NETMASK=$(jq -r '.network.netmask // ""' "$CONFIG_FILE")
GATEWAY=$(jq -r '.network.gateway // ""' "$CONFIG_FILE")
DNS=$(jq -r '.network.dns // ""' "$CONFIG_FILE")
WIFI_SSID=$(jq -r '.network.wifi_ssid // ""' "$CONFIG_FILE")
WIFI_PASSWORD=$(jq -r '.network.wifi_password // ""' "$CONFIG_FILE")

log "Configuration réseau détectée: $MODE"

# ======================================
# Configuration Ethernet (eth0)
# ======================================

if [ "$MODE" = "dhcp" ]; then
    log "Configuration DHCP pour eth0..."
    
    # Raspberry Pi OS avec dhcpcd
    cat > /tmp/dhcpcd.conf << 'EOF'
# Configuration générée automatiquement par FM Monitor
# Ne pas éditer manuellement

# Interface loopback
interface lo

# Interface Ethernet - DHCP
interface eth0
# DHCP configuré par défaut
EOF
    
    sudo cp /tmp/dhcpcd.conf /etc/dhcpcd.conf
    log "✓ Configuration DHCP appliquée"
    
elif [ "$MODE" = "static" ]; then
    log "Configuration IP fixe pour eth0..."
    log "  IP: $IP"
    log "  Masque: $NETMASK"
    log "  Passerelle: $GATEWAY"
    log "  DNS: $DNS"
    
    # Calculer le CIDR depuis le masque
    # Par exemple: 255.255.255.0 → /24
    CIDR=24
    case "$NETMASK" in
        255.255.255.0) CIDR=24 ;;
        255.255.0.0) CIDR=16 ;;
        255.0.0.0) CIDR=8 ;;
        255.255.255.128) CIDR=25 ;;
        255.255.255.192) CIDR=26 ;;
        255.255.255.224) CIDR=27 ;;
        255.255.255.240) CIDR=28 ;;
        255.255.255.248) CIDR=29 ;;
        255.255.255.252) CIDR=30 ;;
    esac
    
    log "  CIDR: /$CIDR"
    
    # Raspberry Pi OS avec dhcpcd
    cat > /tmp/dhcpcd.conf << EOF
# Configuration générée automatiquement par FM Monitor
# Ne pas éditer manuellement

# Interface loopback
interface lo

# Interface Ethernet - IP fixe
interface eth0
static ip_address=${IP}/${CIDR}
static routers=${GATEWAY}
static domain_name_servers=${DNS}
EOF
    
    sudo cp /tmp/dhcpcd.conf /etc/dhcpcd.conf
    log "✓ Configuration IP fixe appliquée"
fi

# ======================================
# Configuration WiFi
# ======================================

if [ -n "$WIFI_SSID" ]; then
    log "Configuration WiFi..."
    log "  SSID: $WIFI_SSID"
    
    if [ -n "$WIFI_PASSWORD" ] && [ "$WIFI_PASSWORD" != "" ]; then
        log "  Génération de la clé WPA..."
        
        # Générer le PSK avec wpa_passphrase
        PSK=$(wpa_passphrase "$WIFI_SSID" "$WIFI_PASSWORD" 2>/dev/null | grep -v '#psk' | grep 'psk=' | cut -d'=' -f2)
        
        if [ -z "$PSK" ]; then
            log "ERREUR: Impossible de générer la clé WPA"
            log "SSID ou mot de passe invalide"
        else
            cat > /tmp/wpa_supplicant.conf << EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=FR

network={
    ssid="$WIFI_SSID"
    psk=$PSK
    key_mgmt=WPA-PSK
}
EOF
            
            sudo cp /tmp/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf
            sudo chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf
            log "✓ Configuration WiFi appliquée"
        fi
    else
        log "Pas de mot de passe WiFi fourni, conservation de la config existante"
    fi
fi

# ======================================
# Redémarrage des services réseau
# ======================================

log "Redémarrage des services réseau..."

# Méthode 1 : Redémarrer dhcpcd (plus rapide)
if sudo systemctl restart dhcpcd; then
    log "✓ Service dhcpcd redémarré"
else
    log "⚠️ Échec redémarrage dhcpcd"
fi

# Si WiFi configuré, redémarrer wpa_supplicant
if [ -n "$WIFI_SSID" ] && [ -n "$WIFI_PASSWORD" ]; then
    if sudo systemctl restart wpa_supplicant; then
        log "✓ Service wpa_supplicant redémarré"
    else
        log "⚠️ Échec redémarrage wpa_supplicant"
    fi
fi

# Attendre que le réseau se stabilise
sleep 3

# ======================================
# Vérification
# ======================================

log "Vérification de la connectivité..."

# Récupérer l'IP actuelle
CURRENT_IP=$(ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "N/A")
log "IP actuelle eth0: $CURRENT_IP"

# Tester la connectivité internet
if ping -c 1 -W 2 8.8.8.8 &> /dev/null; then
    log "✓ Connectivité Internet OK (ping 8.8.8.8)"
elif ping -c 1 -W 2 "$GATEWAY" &> /dev/null; then
    log "✓ Passerelle accessible ($GATEWAY)"
    log "⚠️ Pas d'accès Internet"
else
    log "⚠️ Aucune connectivité réseau détectée"
    log "   Vérifiez les paramètres réseau"
fi

log "========================================"
log "Configuration réseau terminée"
log "========================================"
log ""

# Afficher un résumé
echo ""
echo "Résumé de la configuration appliquée:"
echo "  Mode: $MODE"
if [ "$MODE" = "static" ]; then
    echo "  IP: $IP/$CIDR"
    echo "  Passerelle: $GATEWAY"
    echo "  DNS: $DNS"
fi
if [ -n "$WIFI_SSID" ]; then
    echo "  WiFi SSID: $WIFI_SSID"
fi
echo "  IP actuelle: $CURRENT_IP"
echo ""
echo "Logs détaillés: $LOG_FILE"

exit 0
