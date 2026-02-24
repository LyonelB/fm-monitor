#!/bin/bash
#
# FM Monitor - Installation automatique
# Compatible: Raspberry Pi OS (Debian/Ubuntu)
#
# Usage: curl -sSL https://raw.githubusercontent.com/user/fm-monitor/main/install.sh | bash
#

set -e  # Arrêter en cas d'erreur

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonctions d'affichage
print_header() {
    echo -e "${BLUE}"
    echo "=========================================="
    echo "   FM Monitor - Installation"
    echo "=========================================="
    echo -e "${NC}"
}

print_step() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Variables
INSTALL_DIR="$HOME/fm-monitor"
GITHUB_REPO="https://github.com/LyonelB/fm-monitor.git"
PYTHON_VERSION="3.9"

# Vérification root
if [ "$EUID" -eq 0 ]; then
    print_error "Ne lancez pas ce script en root (pas de sudo)"
    print_info "Le script demandera sudo uniquement quand nécessaire"
    exit 1
fi

print_header

# =============================================
# 1. VÉRIFICATION DU SYSTÈME
# =============================================
print_step "Vérification du système..."

# Vérifier l'OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VERSION=$VERSION_ID
    print_info "OS détecté: $PRETTY_NAME"
else
    print_error "Impossible de détecter l'OS"
    exit 1
fi

# Vérifier si Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    RPI_MODEL=$(cat /proc/device-tree/model)
    print_info "Raspberry Pi détecté: $RPI_MODEL"
fi

# Vérifier Python
if command -v python3 &> /dev/null; then
    PYTHON_INSTALLED=$(python3 --version | awk '{print $2}')
    print_info "Python installé: $PYTHON_INSTALLED"
else
    print_error "Python 3 n'est pas installé"
    exit 1
fi

# =============================================
# 2. MISE À JOUR DU SYSTÈME
# =============================================
print_step "Mise à jour du système..."
sudo apt update -qq

# =============================================
# 3. INSTALLATION DES DÉPENDANCES
# =============================================
print_step "Installation des dépendances système..."

PACKAGES=(
    "python3-pip"
    "python3-venv"
    "rtl-sdr"
    "sox"
    "libsox-fmt-all"
    "lame"
    "git"
    "openssl"
)

for package in "${PACKAGES[@]}"; do
    if dpkg -l | grep -q "^ii  $package "; then
        print_info "$package déjà installé"
    else
        print_info "Installation de $package..."
        sudo apt install -y -qq "$package"
    fi
done

# =============================================
# 4. TÉLÉCHARGEMENT/CLONAGE DE FM MONITOR
# =============================================
print_step "Installation de FM Monitor..."

if [ -d "$INSTALL_DIR" ]; then
    print_warning "Le répertoire $INSTALL_DIR existe déjà"
    read -p "Voulez-vous le sauvegarder et continuer ? (o/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Oo]$ ]]; then
        BACKUP_DIR="${INSTALL_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
        mv "$INSTALL_DIR" "$BACKUP_DIR"
        print_info "Backup créé: $BACKUP_DIR"
    else
        print_error "Installation annulée"
        exit 1
    fi
fi

# Option 1 : Clone depuis GitHub (si dispo)
if [ -n "$GITHUB_REPO" ] && git ls-remote "$GITHUB_REPO" &> /dev/null; then
    print_info "Clonage depuis GitHub..."
    git clone "$GITHUB_REPO" "$INSTALL_DIR"
else
    # Option 2 : Créer la structure manuellement
    print_info "Création de la structure..."
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/templates"
    mkdir -p "$INSTALL_DIR/static"
    
    print_warning "Les fichiers sources doivent être copiés manuellement dans $INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# =============================================
# 5. ENVIRONNEMENT VIRTUEL PYTHON
# =============================================
print_step "Création de l'environnement virtuel Python..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

# =============================================
# 6. INSTALLATION DES PACKAGES PYTHON
# =============================================
print_step "Installation des packages Python..."

# Packages de base
pip install --quiet --upgrade pip

PYTHON_PACKAGES=(
    "flask==3.0.0"
    "numpy==1.24.3"
    "redsea==0.18.1"
    "flask-bcrypt==1.0.1"
    "Flask-Limiter==3.5.0"
    "python-dotenv==1.0.0"
    "Flask-WTF==1.2.1"
)

for package in "${PYTHON_PACKAGES[@]}"; do
    print_info "Installation de $package..."
    pip install --quiet "$package"
done

deactivate

# =============================================
# 7. CONFIGURATION INITIALE
# =============================================
print_step "Configuration initiale..."

# Créer config.json si absent
if [ ! -f "config.json" ]; then
    print_info "Création de config.json..."
    cat > config.json << 'EOF'
{
  "station": {
    "name": "Ma Radio FM",
    "frequency": "88.6M"
  },
  "rtl_sdr": {
    "frequency": "88.6M",
    "sample_rate": "1140000",
    "gain": "auto",
    "device_index": "0"
  },
  "audio": {
    "silence_threshold": -40.0,
    "silence_duration": 15
  },
  "email": {
    "sender_email": "",
    "sender_password": "",
    "recipient_emails": [],
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587
  },
  "network": {
    "mode": "dhcp",
    "ip": "",
    "netmask": "",
    "gateway": "",
    "dns": "",
    "wifi_ssid": "",
    "wifi_password": ""
  },
  "auth": {
    "username": "admin",
    "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYzS9qvZiCm"
  }
}
EOF
    print_info "Mot de passe par défaut: 'password' (à changer !)"
fi

# Créer fichier .env
if [ ! -f ".env" ]; then
    print_info "Génération de la clé secrète..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    
    cat > .env << EOF
# FM Monitor - Variables d'environnement
SECRET_KEY=$SECRET_KEY
FLASK_ENV=production
EOF
    chmod 600 .env
fi

# =============================================
# 8. GÉNÉRATION DU CERTIFICAT SSL
# =============================================
print_step "Génération du certificat SSL..."

if [ ! -f "cert.pem" ] || [ ! -f "key.pem" ]; then
    openssl req -x509 -newkey rsa:4096 -nodes \
        -out cert.pem \
        -keyout key.pem \
        -days 3650 \
        -subj "/C=FR/ST=France/L=Paris/O=FM Monitor/OU=Radio/CN=fm-monitor.local" \
        2>/dev/null
    
    chmod 644 cert.pem
    chmod 600 key.pem
    print_info "Certificat SSL généré (valide 10 ans)"
else
    print_info "Certificat SSL déjà présent"
fi

# =============================================
# 9. SERVICE SYSTEMD
# =============================================
print_step "Configuration du service systemd..."

sudo tee /etc/systemd/system/fm-monitor.service > /dev/null << EOF
[Unit]
Description=FM Radio Monitoring System
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Recharger systemd
sudo systemctl daemon-reload

# Activer le service au démarrage
sudo systemctl enable fm-monitor

print_info "Service systemd configuré"

# =============================================
# 10. PERMISSIONS
# =============================================
print_step "Configuration des permissions..."

# Donner accès au RTL-SDR
if [ -f /etc/udev/rules.d/20-rtlsdr.rules ]; then
    print_info "Règles udev RTL-SDR déjà configurées"
else
    sudo tee /etc/udev/rules.d/20-rtlsdr.rules > /dev/null << 'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0666"
EOF
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    print_info "Règles udev RTL-SDR ajoutées"
fi

# Ajouter l'utilisateur au groupe plugdev
sudo usermod -a -G plugdev "$USER"

# =============================================
# 11. VÉRIFICATION
# =============================================
print_step "Vérification de l'installation..."

# Vérifier RTL-SDR
if rtl_test -t 2>&1 | grep -q "Found"; then
    print_info "RTL-SDR détecté"
else
    print_warning "RTL-SDR non détecté (branchez le dongle USB)"
fi

# Vérifier que tous les fichiers critiques existent
CRITICAL_FILES=(
    "app.py"
    "monitor.py"
    "auth.py"
    "config.json"
    ".env"
    "cert.pem"
    "key.pem"
)

missing_files=0
for file in "${CRITICAL_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        print_error "Fichier manquant: $file"
        missing_files=$((missing_files + 1))
    fi
done

if [ $missing_files -gt 0 ]; then
    print_warning "$missing_files fichier(s) manquant(s)"
    print_info "Copiez les fichiers sources dans $INSTALL_DIR"
fi

# =============================================
# 12. FINALISATION
# =============================================
echo ""
echo -e "${GREEN}=========================================="
echo "   Installation terminée !"
echo -e "==========================================${NC}"
echo ""

print_info "Résumé de l'installation:"
echo "  • Répertoire: $INSTALL_DIR"
echo "  • Service: fm-monitor.service"
echo "  • URL: https://$(hostname -I | awk '{print $1}'):5000"
echo ""

print_info "Commandes utiles:"
echo "  • Démarrer:  sudo systemctl start fm-monitor"
echo "  • Arrêter:   sudo systemctl stop fm-monitor"
echo "  • Statut:    sudo systemctl status fm-monitor"
echo "  • Logs:      sudo journalctl -u fm-monitor -f"
echo ""

print_info "Identifiants par défaut:"
echo "  • Username:  admin"
echo "  • Password:  password"
echo -e "  ${RED}⚠️  CHANGEZ LE MOT DE PASSE IMMÉDIATEMENT !${NC}"
echo ""

# Demander si on démarre le service
read -p "Voulez-vous démarrer FM Monitor maintenant ? (o/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Oo]$ ]]; then
    sudo systemctl start fm-monitor
    sleep 2
    
    if sudo systemctl is-active --quiet fm-monitor; then
        print_step "FM Monitor démarré avec succès !"
        print_info "Accédez à https://$(hostname -I | awk '{print $1}'):5000"
    else
        print_error "Erreur au démarrage"
        print_info "Vérifiez les logs: sudo journalctl -u fm-monitor -n 50"
    fi
else
    print_info "Pour démarrer plus tard: sudo systemctl start fm-monitor"
fi

echo ""
print_info "Documentation: https://github.com/LyonelB/fm-monitor/wiki"
print_info "Support: https://github.com/LyonelB/fm-monitor/issues"
echo ""

print_step "Installation terminée ! 🎉"
