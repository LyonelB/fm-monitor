#!/bin/bash
#
# FM Monitor - Script de mise à jour
#

set -e

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

echo -e "${BLUE}"
echo "=========================================="
echo "   FM Monitor - Mise à jour"
echo "=========================================="
echo -e "${NC}"

INSTALL_DIR="$HOME/fm-monitor"

# Vérifier que FM Monitor est installé
if [ ! -d "$INSTALL_DIR" ]; then
    echo "FM Monitor n'est pas installé dans $INSTALL_DIR"
    exit 1
fi

cd "$INSTALL_DIR"

# Arrêter le service
print_step "Arrêt du service..."
sudo systemctl stop fm-monitor

# Sauvegarder la configuration
print_step "Sauvegarde de la configuration..."
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp config.json "$BACKUP_DIR/" 2>/dev/null || true
cp .env "$BACKUP_DIR/" 2>/dev/null || true
print_info "Backup: $BACKUP_DIR"

# Mettre à jour depuis Git
print_step "Téléchargement de la dernière version..."
if [ -d ".git" ]; then
    git fetch origin
    git pull origin main
else
    print_warning "Pas de dépôt Git détecté"
    print_info "Mise à jour manuelle requise"
fi

# Activer le venv
source venv/bin/activate

# Mettre à jour les dépendances Python
print_step "Mise à jour des dépendances Python..."
pip install --quiet --upgrade pip
pip install --quiet --upgrade -r requirements.txt

deactivate

# Restaurer la configuration
print_step "Restauration de la configuration..."
if [ -f "$BACKUP_DIR/config.json" ]; then
    cp "$BACKUP_DIR/config.json" config.json
fi
if [ -f "$BACKUP_DIR/.env" ]; then
    cp "$BACKUP_DIR/.env" .env
fi

# Recharger systemd si nécessaire
if [ -f "/etc/systemd/system/fm-monitor.service" ]; then
    sudo systemctl daemon-reload
fi

# Redémarrer le service
print_step "Redémarrage du service..."
sudo systemctl start fm-monitor

sleep 2

# Vérifier le statut
if sudo systemctl is-active --quiet fm-monitor; then
    print_step "Mise à jour terminée avec succès !"
    print_info "FM Monitor est en cours d'exécution"
else
    print_warning "Le service ne s'est pas démarré correctement"
    print_info "Vérifiez les logs: sudo journalctl -u fm-monitor -n 50"
fi

echo ""
print_info "Changelog: https://github.com/LyonelB/fm-monitor/releases"
echo ""

