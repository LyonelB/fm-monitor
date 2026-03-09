#!/bin/bash
#
# FM Monitor - Installation automatique
# Compatible: Raspberry Pi OS (Debian/Ubuntu)
#
# Usage: curl -sSL https://raw.githubusercontent.com/LyonelB/fm-monitor/main/install.sh | bash
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}"
    echo "=========================================="
    echo "   FM Monitor - Installation"
    echo "=========================================="
    echo -e "${NC}"
}

print_step()    { echo -e "${GREEN}[✓]${NC} $1"; }
print_info()    { echo -e "${BLUE}[i]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error()   { echo -e "${RED}[✗]${NC} $1"; }

INSTALL_DIR="$HOME/fm-monitor"
GITHUB_REPO="https://github.com/LyonelB/fm-monitor.git"
ICECAST_PASSWORD="fmmonitor2026"

if [ "$EUID" -eq 0 ]; then
    print_error "Ne lancez pas ce script en root (pas de sudo)"
    print_info "Le script demandera sudo uniquement quand nécessaire"
    exit 1
fi

print_header

# =============================================
# ÉTAPE PRÉLIMINAIRE : BRANCHEMENT DU DONGLE
# =============================================
echo ""
print_warning "╔══════════════════════════════════════════════╗"
print_warning "║  BRANCHEZ MAINTENANT la clé RTL-SDR          ║"
print_warning "║  dans un port USB de votre Raspberry Pi      ║"
print_warning "╚══════════════════════════════════════════════╝"
echo ""
read -p "Appuyez sur Entrée une fois la clé RTL-SDR branchée..."

# =============================================
# 1. VÉRIFICATION DU SYSTÈME
# =============================================
print_step "Vérification du système..."

if [ -f /etc/os-release ]; then
    . /etc/os-release
    print_info "OS détecté: $PRETTY_NAME"
else
    print_error "Impossible de détecter l'OS"
    exit 1
fi

if [ -f /proc/device-tree/model ]; then
    RPI_MODEL=$(cat /proc/device-tree/model)
    print_info "Raspberry Pi détecté: $RPI_MODEL"
fi

if command -v python3 &> /dev/null; then
    print_info "Python installé: $(python3 --version)"
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
# 3. PRÉ-CONFIGURATION ICECAST2 (silencieux)
# =============================================
print_step "Pré-configuration d'Icecast2 (mode silencieux)..."
sudo debconf-set-selections <<EOF
icecast2 icecast2/icecast-setup boolean true
icecast2 icecast2/hostname string localhost
icecast2 icecast2/sourcepassword password $ICECAST_PASSWORD
icecast2 icecast2/relaypassword password $ICECAST_PASSWORD
icecast2 icecast2/adminpassword password $ICECAST_PASSWORD
EOF
print_info "Icecast2 pré-configuré ✓"

# =============================================
# 4. INSTALLATION DES DÉPENDANCES SYSTÈME
# =============================================
print_step "Installation des dépendances système..."

PACKAGES=(
    "python3-pip"
    "python3-venv"
    "rtl-sdr"
    "ffmpeg"
    "icecast2"
    "git"
    "openssl"
    "coreutils"
    "build-essential"
    "meson"
    "ninja-build"
    "libsndfile1-dev"
    "libliquid-dev"
)

for package in "${PACKAGES[@]}"; do
    if dpkg -l 2>/dev/null | grep -q "^ii  $package "; then
        print_info "$package déjà installé"
    else
        print_info "Installation de $package..."
        sudo DEBIAN_FRONTEND=noninteractive apt install -y -qq "$package"
    fi
done

# =============================================
# 5. INSTALLATION DE REDSEA (décodeur RDS)
# =============================================
print_step "Installation de redsea (décodeur RDS)..."

if command -v redsea &> /dev/null; then
    print_info "redsea déjà installé: $(redsea --version 2>&1 | head -1)"
else
    print_info "Compilation de redsea depuis les sources (quelques minutes)..."
    REDSEA_TMP=$(mktemp -d)
    git clone --quiet https://github.com/windytan/redsea.git "$REDSEA_TMP"
    cd "$REDSEA_TMP"
    meson setup build
    ninja -C build -j$(nproc) 2>/dev/null
    sudo ninja -C build install 2>/dev/null
    cd -
    rm -rf "$REDSEA_TMP"

    if command -v redsea &> /dev/null; then
        print_info "redsea installé: $(redsea --version 2>&1 | head -1)"
    else
        print_error "Échec de l'installation de redsea"
        exit 1
    fi
fi

# =============================================
# 6. CONFIGURATION ICECAST2
# =============================================
print_step "Configuration d'Icecast2..."

ICECAST_CONF="/etc/icecast2/icecast.xml"
if [ -f "$ICECAST_CONF" ]; then
    sudo cp "$ICECAST_CONF" "${ICECAST_CONF}.bak"
    # Configurer le mot de passe source (remplace valeur vide ou existante)
    sudo python3 -c "
import re
with open('$ICECAST_CONF', 'r') as f:
    content = f.read()
content = re.sub(r'<source-password>[^<]*</source-password>', '<source-password>$ICECAST_PASSWORD</source-password>', content)
with open('$ICECAST_CONF', 'w') as f:
    f.write(content)
print('  mot de passe source configuré')
"
    sudo systemctl enable icecast2
    sudo systemctl restart icecast2
    sleep 2
    if sudo systemctl is-active --quiet icecast2; then
        print_info "Icecast2 démarré ✓"
    else
        print_warning "Icecast2 ne démarre pas - vérifiez: sudo systemctl status icecast2"
    fi
else
    print_warning "icecast.xml non trouvé - configuration manuelle requise"
fi

# =============================================
# 7. TÉLÉCHARGEMENT DE FM MONITOR
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

if git ls-remote "$GITHUB_REPO" &> /dev/null; then
    print_info "Clonage depuis GitHub..."
    git clone --quiet "$GITHUB_REPO" "$INSTALL_DIR"
else
    print_error "Impossible d'accéder à GitHub"
    exit 1
fi

cd "$INSTALL_DIR"

# Corriger l'URL du proxy stream (http:8000 au lieu de https:8443)
python3 -c "
with open('app.py', 'r') as f:
    c = f.read()
old = \"with requests.get('https://localhost:8443/fmmonitor', stream=True, verify=False, timeout=5) as r:\"
new = \"with requests.get('http://localhost:8000/fmmonitor', stream=True, timeout=5) as r:\"
if old in c:
    with open('app.py', 'w') as f: f.write(c.replace(old, new))
    print('  proxy stream corrigé (http:8000)')
else:
    print('  proxy stream déjà correct')
" 2>/dev/null || true

# =============================================
# 8. ENVIRONNEMENT VIRTUEL PYTHON
# =============================================
print_step "Création de l'environnement virtuel Python..."

python3 -m venv venv
source venv/bin/activate

# =============================================
# 9. INSTALLATION DES PACKAGES PYTHON
# =============================================
print_step "Installation des packages Python..."

pip install --quiet --upgrade pip setuptools wheel

PYTHON_PACKAGES=(
    "flask==3.0.0"
    "numpy"
    "requests"
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
# 10. CONFIGURATION INITIALE
# =============================================
print_step "Configuration initiale..."

if [ ! -f "config.json" ]; then
    print_info "Création de config.json..."
    cat > config.json << 'EOF'
{
  "station": {
    "name": "Ma Radio FM",
    "frequency": "88.6M",
    "frequency_display": "88.6 MHz"
  },
  "rtl_sdr": {
    "frequency": "88.6M",
    "sample_rate": "1140000",
    "gain": "40",
    "device_index": "0",
    "ppm_error": 0
  },
  "audio": {
    "output_rate": "44100",
    "silence_threshold": -40.0,
    "silence_duration": 15,
    "enabled": true
  },
  "email": {
    "sender_email": "",
    "sender_password": "",
    "recipient_emails": [],
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "enabled": false,
    "use_tls": true
  },
  "network": {
    "mode": "dhcp",
    "ip": "",
    "netmask": "",
    "gateway": "",
    "dns": "",
    "wifi_ssid": "",
    "wifi_password": ""
  }
}
EOF
    # Générer le hash bcrypt pour "password"
    print_info "Génération du hash du mot de passe par défaut..."
    source venv/bin/activate
    PW_HASH=$(python3 -c "
from flask_bcrypt import Bcrypt
from flask import Flask
app = Flask(__name__)
bcrypt = Bcrypt(app)
print(bcrypt.generate_password_hash('password').decode('utf-8'))
")
    deactivate
    python3 -c "
import json
with open('config.json') as f:
    c = json.load(f)
c['auth'] = {'username': 'admin', 'password_hash': '$PW_HASH'}
with open('config.json', 'w') as f:
    json.dump(c, f, indent=2)
"
    print_info "Mot de passe par défaut: 'password' (à changer !)"
fi

if [ ! -f ".env" ]; then
    print_info "Génération de la clé secrète..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > .env << EOF
SECRET_KEY=$SECRET_KEY
FLASK_ENV=production
EOF
    chmod 600 .env
fi

# =============================================
# 11. GÉNÉRATION DU CERTIFICAT SSL
# =============================================
print_step "Génération du certificat SSL..."

if [ ! -f "cert.pem" ] || [ ! -f "key.pem" ]; then
    openssl req -x509 -newkey rsa:4096 -nodes \
        -out cert.pem -keyout key.pem \
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
# 12. SERVICE SYSTEMD
# =============================================
print_step "Configuration du service systemd..."

sudo tee /etc/systemd/system/fm-monitor.service > /dev/null << EOF
[Unit]
Description=FM Radio Monitoring System
After=network.target icecast2.service
Requires=icecast2.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$INSTALL_DIR/venv/bin"
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable fm-monitor
print_info "Service systemd configuré"

# =============================================
# 13. PERMISSIONS RTL-SDR
# =============================================
print_step "Configuration des permissions RTL-SDR..."

if [ ! -f /etc/udev/rules.d/20-rtlsdr.rules ]; then
    sudo tee /etc/udev/rules.d/20-rtlsdr.rules > /dev/null << 'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", GROUP="plugdev", MODE="0666"
EOF
    print_info "Règles udev RTL-SDR ajoutées"
else
    print_info "Règles udev RTL-SDR déjà configurées"
fi

sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -a -G plugdev "$USER"

# =============================================
# 14. VÉRIFICATION
# =============================================
print_step "Vérification de l'installation..."

if rtl_test -t 2>&1 | grep -q "Found"; then
    print_info "RTL-SDR détecté ✓"
else
    print_warning "RTL-SDR non détecté - vérifiez le branchement USB"
fi

if sudo systemctl is-active --quiet icecast2; then
    print_info "Icecast2 actif ✓"
else
    print_warning "Icecast2 inactif - vérifiez: sudo systemctl status icecast2"
fi

if command -v redsea &> /dev/null; then
    print_info "redsea installé ✓"
fi

CRITICAL_FILES=("app.py" "monitor.py" "auth.py" "config.json" ".env" "cert.pem" "key.pem")
missing_files=0
for file in "${CRITICAL_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        print_error "Fichier manquant: $file"
        missing_files=$((missing_files + 1))
    fi
done
if [ $missing_files -eq 0 ]; then
    print_info "Tous les fichiers critiques présents ✓"
fi

# =============================================
# 15. FINALISATION
# =============================================
echo ""
echo -e "${GREEN}=========================================="
echo "   Installation terminée !"
echo -e "==========================================${NC}"
echo ""
print_info "Résumé:"
echo "  • Répertoire : $INSTALL_DIR"
echo "  • URL        : https://$(hostname -I | awk '{print $1}'):5000"
echo ""
print_info "Identifiants par défaut:"
echo "  • Username : admin"
echo "  • Password : password"
echo -e "  ${RED}⚠️  CHANGEZ LE MOT DE PASSE dans Configuration > Sécurité${NC}"
echo ""
print_info "Commandes utiles:"
echo "  • Démarrer : sudo systemctl start fm-monitor"
echo "  • Arrêter  : sudo systemctl stop fm-monitor"
echo "  • Statut   : sudo systemctl status fm-monitor"
echo "  • Logs     : sudo journalctl -u fm-monitor -f"
echo ""

read -p "Voulez-vous démarrer FM Monitor maintenant ? (o/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Oo]$ ]]; then
    sudo systemctl start fm-monitor
    sleep 3
    if sudo systemctl is-active --quiet fm-monitor; then
        print_step "FM Monitor démarré !"
        print_info "Accédez à https://$(hostname -I | awk '{print $1}'):5000"
    else
        print_error "Erreur au démarrage"
        print_info "Diagnostic: sudo journalctl -u fm-monitor -n 50"
    fi
else
    print_info "Pour démarrer: sudo systemctl start fm-monitor"
fi

echo ""
print_step "Terminé ! 🎉"
