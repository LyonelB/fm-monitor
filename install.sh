#!/bin/bash
# Script d'installation du système de surveillance FM
# Compatible Raspberry Pi et distributions Linux

set -e

echo "=========================================="
echo "Installation du système de surveillance FM"
echo "=========================================="
echo ""

# Vérifier les privilèges root pour certaines installations
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Certaines opérations nécessitent les privilèges root"
    echo "Veuillez exécuter: sudo ./install.sh"
    exit 1
fi

# Détection de l'OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
    echo "OS détecté: $OS"
else
    echo "❌ Impossible de détecter l'OS"
    exit 1
fi

# Mise à jour du système
echo ""
echo "📦 Mise à jour du système..."
apt-get update

# Installation des dépendances système
echo ""
echo "📦 Installation des dépendances système..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    rtl-sdr \
    sox \
    librtlsdr-dev \
    git \
    wget

# Vérifier que rtl-sdr fonctionne
echo ""
echo "🔍 Vérification de RTL-SDR..."
if ! command -v rtl_fm &> /dev/null; then
    echo "❌ rtl_fm n'est pas installé correctement"
    exit 1
fi

# Bloquer le pilote DVB-T qui peut interférer avec RTL-SDR
echo ""
echo "🚫 Configuration du système pour RTL-SDR..."
if [ ! -f /etc/modprobe.d/rtl-sdr-blacklist.conf ]; then
    cat > /etc/modprobe.d/rtl-sdr-blacklist.conf << EOF
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF
    echo "✅ Pilotes DVB-T désactivés"
fi

# Créer les règles udev pour RTL-SDR
if [ ! -f /etc/udev/rules.d/20-rtlsdr.rules ]; then
    cat > /etc/udev/rules.d/20-rtlsdr.rules << EOF
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0666"
EOF
    udevadm control --reload-rules
    echo "✅ Règles udev configurées"
fi

# Créer un environnement virtuel Python
echo ""
echo "🐍 Configuration de l'environnement Python..."
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Environnement virtuel créé"
fi

# Activer l'environnement virtuel et installer les dépendances
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ Dépendances Python installées"

# Créer le répertoire de logs
mkdir -p logs
chmod 755 logs

# Créer un service systemd
echo ""
echo "⚙️  Configuration du service systemd..."

SERVICE_PATH="/etc/systemd/system/fm-monitor.service"
INSTALL_PATH="$(pwd)"

cat > $SERVICE_PATH << EOF
[Unit]
Description=FM Radio Monitoring System
After=network.target

[Service]
Type=simple
User=$SUDO_USER
WorkingDirectory=$INSTALL_PATH
Environment="PATH=$INSTALL_PATH/venv/bin"
ExecStart=$INSTALL_PATH/venv/bin/python3 $INSTALL_PATH/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Recharger systemd
systemctl daemon-reload

echo "✅ Service systemd créé"

# Afficher les informations de configuration
echo ""
echo "=========================================="
echo "✅ Installation terminée avec succès!"
echo "=========================================="
echo ""
echo "📝 Prochaines étapes:"
echo ""
echo "1. Brancher votre clé RTL-SDR"
echo ""
echo "2. Tester la réception FM:"
echo "   rtl_test"
echo ""
echo "3. Éditer le fichier config.json pour configurer:"
echo "   - La fréquence FM de votre radio"
echo "   - Les paramètres email (SMTP)"
echo "   - Les destinataires des alertes"
echo ""
echo "4. Démarrer le service:"
echo "   sudo systemctl start fm-monitor"
echo ""
echo "5. Activer le démarrage automatique:"
echo "   sudo systemctl enable fm-monitor"
echo ""
echo "6. Vérifier le statut:"
echo "   sudo systemctl status fm-monitor"
echo ""
echo "7. Voir les logs:"
echo "   sudo journalctl -u fm-monitor -f"
echo ""
echo "8. Accéder à l'interface web:"
echo "   http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "📚 Commandes utiles:"
echo "   sudo systemctl stop fm-monitor      # Arrêter"
echo "   sudo systemctl restart fm-monitor   # Redémarrer"
echo "   sudo systemctl disable fm-monitor   # Désactiver auto-start"
echo ""
echo "⚠️  N'oubliez pas de configurer config.json avant de démarrer!"
echo ""
