#!/bin/bash
# Script d'installation automatique pour système de surveillance FM
# Optimisé pour clé USB bootable sur PC x86/64
# Version: 2.0

set -e

echo "=========================================="
echo "Installation Système de Surveillance FM"
echo "Version Clé USB Bootable"
echo "=========================================="
echo ""

# Vérifier que c'est bien exécuté en root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Ce script doit être exécuté avec les privilèges root"
    echo "Utilisez: sudo ./usb-autoinstall.sh"
    exit 1
fi

# Détection du système
echo "🔍 Détection du système..."
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_NAME=$NAME
    OS_VERSION=$VERSION_ID
    echo "✅ OS détecté: $OS_NAME $OS_VERSION"
else
    echo "❌ Impossible de détecter le système d'exploitation"
    exit 1
fi

# Vérifier que c'est bien un système Debian/Ubuntu
if [[ ! "$ID" =~ ^(ubuntu|debian)$ ]]; then
    echo "⚠️  Ce script est conçu pour Ubuntu/Debian"
    echo "Votre système: $ID"
    read -p "Continuer quand même? (o/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Oo]$ ]]; then
        exit 1
    fi
fi

# Mise à jour du système
echo ""
echo "📦 Mise à jour du système..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq

# Installation des dépendances système
echo ""
echo "📦 Installation des dépendances..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    rtl-sdr \
    sox \
    librtlsdr-dev \
    git \
    wget \
    curl \
    ufw \
    net-tools \
    htop \
    nano \
    2>&1 | grep -v "^Setting up\|^Processing\|^Preparing" || true

echo "✅ Dépendances système installées"

# Configuration RTL-SDR
echo ""
echo "🔧 Configuration RTL-SDR..."

# Blacklist des drivers DVB-T
if [ ! -f /etc/modprobe.d/rtl-sdr-blacklist.conf ]; then
    cat > /etc/modprobe.d/rtl-sdr-blacklist.conf << 'EOF'
# Blacklist pour RTL-SDR
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF
    echo "✅ Drivers DVB-T désactivés"
fi

# Règles udev pour RTL-SDR
if [ ! -f /etc/udev/rules.d/20-rtlsdr.rules ]; then
    cat > /etc/udev/rules.d/20-rtlsdr.rules << 'EOF'
# RTL-SDR udev rules
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", GROUP="plugdev", MODE="0666"
EOF
    udevadm control --reload-rules
    udevadm trigger
    echo "✅ Règles udev configurées"
fi

# Ajouter l'utilisateur au groupe plugdev
REAL_USER="${SUDO_USER:-$USER}"
if [ "$REAL_USER" != "root" ]; then
    usermod -a -G plugdev "$REAL_USER"
    echo "✅ Utilisateur $REAL_USER ajouté au groupe plugdev"
fi

# Déterminer le répertoire du projet
if [ -d "$(dirname "$0")" ]; then
    cd "$(dirname "$0")"
fi

PROJECT_DIR="$(pwd)"
echo "📁 Répertoire du projet: $PROJECT_DIR"

# Vérifier que les fichiers du projet sont présents
if [ ! -f "app.py" ] || [ ! -f "monitor.py" ]; then
    echo "❌ Fichiers du projet non trouvés dans $PROJECT_DIR"
    echo "Assurez-vous d'exécuter ce script depuis le répertoire fm-monitor"
    exit 1
fi

# Créer l'environnement virtuel Python
echo ""
echo "🐍 Configuration de l'environnement Python..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Environnement virtuel créé"
fi

# Activer et installer les dépendances Python
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo "✅ Dépendances Python installées"

# Créer les répertoires nécessaires
mkdir -p logs
chmod 755 logs
chown -R "$REAL_USER:$REAL_USER" logs

# Configuration du pare-feu
echo ""
echo "🔒 Configuration du pare-feu..."
ufw --force reset > /dev/null 2>&1
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 5000/tcp comment 'FM Monitor Web Interface'
echo "y" | ufw enable > /dev/null 2>&1
echo "✅ Pare-feu configuré"

# Créer le service systemd
echo ""
echo "⚙️  Configuration du service systemd..."

SERVICE_PATH="/etc/systemd/system/fm-monitor.service"

cat > "$SERVICE_PATH" << EOF
[Unit]
Description=FM Radio Monitoring System
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$REAL_USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Limites de ressources
MemoryMax=512M
CPUQuota=80%

[Install]
WantedBy=multi-user.target
EOF

# Recharger systemd
systemctl daemon-reload
echo "✅ Service systemd créé"

# Créer un script de démarrage rapide pour l'utilisateur
cat > "$PROJECT_DIR/start-fm-monitor.sh" << 'EOF'
#!/bin/bash
# Script de démarrage rapide

echo "🚀 Démarrage du système de surveillance FM..."
sudo systemctl start fm-monitor

# Attendre que le service démarre
sleep 3

if systemctl is-active --quiet fm-monitor; then
    echo "✅ Service démarré avec succès!"
    echo ""
    echo "🌐 Accès à l'interface web:"
    IP=$(hostname -I | awk '{print $1}')
    echo "   http://$IP:5000"
    echo "   http://localhost:5000 (en local)"
    echo ""
else
    echo "❌ Erreur de démarrage"
    echo "Voir les logs: sudo journalctl -u fm-monitor -n 50"
fi
EOF

chmod +x "$PROJECT_DIR/start-fm-monitor.sh"
chown "$REAL_USER:$REAL_USER" "$PROJECT_DIR/start-fm-monitor.sh"

# Créer un script d'arrêt
cat > "$PROJECT_DIR/stop-fm-monitor.sh" << 'EOF'
#!/bin/bash
echo "⏹️  Arrêt du système de surveillance FM..."
sudo systemctl stop fm-monitor
echo "✅ Service arrêté"
EOF

chmod +x "$PROJECT_DIR/stop-fm-monitor.sh"
chown "$REAL_USER:$REAL_USER" "$PROJECT_DIR/stop-fm-monitor.sh"

# Créer un script de statut
cat > "$PROJECT_DIR/status-fm-monitor.sh" << 'EOF'
#!/bin/bash
echo "📊 Statut du système de surveillance FM"
echo "========================================"
echo ""
sudo systemctl status fm-monitor --no-pager
echo ""
echo "🌐 Interface web:"
IP=$(hostname -I | awk '{print $1}')
echo "   http://$IP:5000"
echo ""
echo "📝 Derniers logs:"
sudo journalctl -u fm-monitor -n 10 --no-pager
EOF

chmod +x "$PROJECT_DIR/status-fm-monitor.sh"
chown "$REAL_USER:$REAL_USER" "$PROJECT_DIR/status-fm-monitor.sh"

# Optimisations pour clé USB
echo ""
echo "⚡ Optimisations système pour clé USB..."

# Réduire les écritures sur la clé USB
if ! grep -q "noatime" /etc/fstab; then
    echo "# Optimisation pour clé USB - réduction des écritures" >> /etc/fstab
    echo "tmpfs /tmp tmpfs defaults,noatime,mode=1777 0 0" >> /etc/fstab
    echo "tmpfs /var/log tmpfs defaults,noatime,mode=0755 0 0" >> /etc/fstab
fi

# Désactiver le swap (pour préserver la clé USB)
swapoff -a 2>/dev/null || true
sed -i '/swap/d' /etc/fstab

echo "✅ Optimisations appliquées"

# Message de fin
echo ""
echo "=========================================="
echo "✅ Installation terminée avec succès!"
echo "=========================================="
echo ""
echo "📝 Configuration requise:"
echo ""
echo "1. Éditer le fichier de configuration:"
echo "   nano $PROJECT_DIR/config.json"
echo ""
echo "   Modifier au minimum:"
echo "   - La fréquence FM (frequency)"
echo "   - Les paramètres email (smtp_server, sender_email, etc.)"
echo "   - Le nom de la station (station.name)"
echo ""
echo "2. Tester la clé RTL-SDR:"
echo "   rtl_test"
echo "   (Ctrl+C pour arrêter)"
echo ""
echo "3. Démarrer le service:"
echo "   sudo systemctl start fm-monitor"
echo "   Ou utiliser: ./start-fm-monitor.sh"
echo ""
echo "4. Activer le démarrage automatique:"
echo "   sudo systemctl enable fm-monitor"
echo ""
echo "📊 Commandes utiles:"
echo "   ./start-fm-monitor.sh      # Démarrer"
echo "   ./stop-fm-monitor.sh       # Arrêter"
echo "   ./status-fm-monitor.sh     # Voir le statut"
echo ""
echo "🌐 Accès à l'interface web:"
IP=$(hostname -I | awk '{print $1}' 2>/dev/null)
if [ -n "$IP" ]; then
    echo "   http://$IP:5000"
else
    echo "   http://localhost:5000 (en local)"
    echo "   Trouvez votre IP avec: hostname -I"
fi
echo ""
echo "📝 Logs en temps réel:"
echo "   sudo journalctl -u fm-monitor -f"
echo ""
echo "🔥 Pare-feu configuré:"
echo "   Port 22 (SSH) et 5000 (Web) ouverts"
echo "   Status: sudo ufw status"
echo ""
echo "⚠️  N'oubliez pas de configurer config.json avant de démarrer!"
echo ""
