#!/bin/bash
# Script d'application de la configuration réseau pour FM Monitor
# Compatible avec eth0 (Ethernet) et wlan0 (WiFi)

set -e

CONFIG_FILE="/home/graffiti/fm-monitor/config.json"
DHCPCD_CONF="/etc/dhcpcd.conf"
WPA_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"
WPA_CONF_WLAN0="/etc/wpa_supplicant/wpa_supplicant-wlan0.conf"

echo "=== Application de la configuration réseau ==="

# Vérifier que config.json existe
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Erreur: $CONFIG_FILE n'existe pas"
    exit 1
fi

# Lire la configuration
MODE=$(jq -r '.network.mode // "dhcp"' "$CONFIG_FILE")
IP=$(jq -r '.network.ip // ""' "$CONFIG_FILE")
NETMASK=$(jq -r '.network.netmask // ""' "$CONFIG_FILE")
GATEWAY=$(jq -r '.network.gateway // ""' "$CONFIG_FILE")
DNS=$(jq -r '.network.dns // ""' "$CONFIG_FILE")
WIFI_SSID=$(jq -r '.network.wifi_ssid // ""' "$CONFIG_FILE")
WIFI_PASSWORD=$(jq -r '.network.wifi_password // ""' "$CONFIG_FILE")

echo "Mode réseau: $MODE"

# ==========================================
# 1. DÉSACTIVER NETWORKMANAGER
# ==========================================
if systemctl is-active --quiet NetworkManager; then
    echo "Désactivation de NetworkManager..."
    systemctl stop NetworkManager
    systemctl disable NetworkManager
fi

# ==========================================
# 2. ACTIVER DHCPCD
# ==========================================
if ! systemctl is-enabled --quiet dhcpcd; then
    echo "Activation de dhcpcd..."
    systemctl unmask dhcpcd 2>/dev/null || true
    systemctl enable dhcpcd
fi

# ==========================================
# 3. CONFIGURER dhcpcd.conf
# ==========================================
echo "Configuration de $DHCPCD_CONF..."

# Backup de l'ancienne config
cp "$DHCPCD_CONF" "$DHCPCD_CONF.backup"

# Supprimer les anciennes configurations d'interface
sed -i '/^interface eth0/,/^$/d' "$DHCPCD_CONF"
sed -i '/^interface wlan0/,/^$/d' "$DHCPCD_CONF"

# Ajouter la nouvelle configuration
if [ "$MODE" = "static" ] && [ -n "$IP" ]; then
    echo "" >> "$DHCPCD_CONF"
    echo "# Configuration FM Monitor - Ethernet" >> "$DHCPCD_CONF"
    echo "interface eth0" >> "$DHCPCD_CONF"

    # Convertir netmask en CIDR
    if [ "$NETMASK" = "255.255.255.0" ]; then
        CIDR="24"
    elif [ "$NETMASK" = "255.255.0.0" ]; then
        CIDR="16"
    elif [ "$NETMASK" = "255.0.0.0" ]; then
        CIDR="8"
    else
        CIDR="24"  # Par défaut
    fi

    echo "static ip_address=$IP/$CIDR" >> "$DHCPCD_CONF"
    [ -n "$GATEWAY" ] && echo "static routers=$GATEWAY" >> "$DHCPCD_CONF"
    [ -n "$DNS" ] && echo "static domain_name_servers=$DNS" >> "$DHCPCD_CONF"

    echo "" >> "$DHCPCD_CONF"
    echo "# Configuration FM Monitor - WiFi" >> "$DHCPCD_CONF"
    echo "interface wlan0" >> "$DHCPCD_CONF"
    echo "static ip_address=$IP/$CIDR" >> "$DHCPCD_CONF"
    [ -n "$GATEWAY" ] && echo "static routers=$GATEWAY" >> "$DHCPCD_CONF"
    [ -n "$DNS" ] && echo "static domain_name_servers=$DNS" >> "$DHCPCD_CONF"

    echo "✓ Configuration IP fixe : $IP/$CIDR"
else
    echo "✓ Configuration DHCP activée"
fi

# ==========================================
# 4. CONFIGURER LE WIFI
# ==========================================
if [ -n "$WIFI_SSID" ]; then
    echo "Configuration WiFi: $WIFI_SSID"
    
    # Backup de l'ancienne config
    [ -f "$WPA_CONF" ] && cp "$WPA_CONF" "$WPA_CONF.backup"
    [ -f "$WPA_CONF_WLAN0" ] && cp "$WPA_CONF_WLAN0" "$WPA_CONF_WLAN0.backup"
    
    # Créer le fichier wpa_supplicant (générique)
    cat > "$WPA_CONF" << EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=FR

EOF
    
    # Ajouter le réseau WiFi avec mot de passe hashé
    if [ -n "$WIFI_PASSWORD" ]; then
        wpa_passphrase "$WIFI_SSID" "$WIFI_PASSWORD" >> "$WPA_CONF"
        echo "✓ WiFi configuré avec mot de passe"
    else
        echo "⚠️ Pas de mot de passe WiFi fourni"
    fi
    
    # Copier pour wlan0 spécifiquement (requis par wpa_supplicant@wlan0.service)
    cp "$WPA_CONF" "$WPA_CONF_WLAN0"
    echo "✓ Fichiers wpa_supplicant créés : wpa_supplicant.conf et wpa_supplicant-wlan0.conf"
fi

# ==========================================
# 5. ACTIVER WPA_SUPPLICANT SUR WLAN0
# ==========================================
if [ -n "$WIFI_SSID" ]; then
    echo "Activation de wpa_supplicant@wlan0..."

    # Arrêter le service générique
    systemctl stop wpa_supplicant 2>/dev/null || true

    # Activer le service spécifique à wlan0
    systemctl enable wpa_supplicant@wlan0
    systemctl restart wpa_supplicant@wlan0

    echo "✓ wpa_supplicant@wlan0 activé"
fi

# ==========================================
# 6. REDÉMARRER DHCPCD
# ==========================================
echo "Redémarrage de dhcpcd..."
systemctl restart dhcpcd

# Attendre la stabilisation
sleep 3

# Forcer dhcpcd à gérer wlan0 si WiFi configuré
if [ -n "$WIFI_SSID" ]; then
    echo "Activation de dhcpcd sur wlan0..."
    dhcpcd wlan0 2>/dev/null || true
    sleep 2
fi

# ==========================================
# 7. VÉRIFIER LE RÉSULTAT
# ==========================================
echo ""
echo "=== État du réseau ==="

# Vérifier eth0
echo "Interface eth0:"
ip -4 addr show eth0 | grep inet || echo "  Pas d'IP"

# Vérifier wlan0
echo "Interface wlan0:"
if [ -n "$WIFI_SSID" ]; then
    wpa_cli -i wlan0 status | grep -E "ssid|wpa_state|ip_address" || true
    ip -4 addr show wlan0 | grep inet || echo "  Pas d'IP"
else
    echo "  WiFi non configuré"
fi

echo ""
echo "✅ Configuration réseau appliquée avec succès"
exit 0
