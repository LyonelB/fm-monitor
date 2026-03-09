#!/bin/bash
#
# Script de préparation pour GitHub
# Copie tous les nouveaux fichiers au bon endroit
#

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_info() {
    echo -e "${BLUE}[i]${NC} $1"
}

echo -e "${BLUE}"
echo "=========================================="
echo "   Préparation pour GitHub"
echo "=========================================="
echo -e "${NC}"

REPO_DIR="$HOME/fm-monitor"
DOWNLOADS_DIR="$HOME/Téléchargements"

# Vérifier que le repo existe
if [ ! -d "$REPO_DIR" ]; then
    echo "Erreur: Le répertoire $REPO_DIR n'existe pas"
    exit 1
fi

cd "$REPO_DIR"

# 1. Scripts d'installation
print_step "Copie des scripts d'installation..."
cp "$DOWNLOADS_DIR/install.sh" .
cp "$DOWNLOADS_DIR/update.sh" .
cp "$DOWNLOADS_DIR/requirements.txt" .
chmod +x install.sh update.sh

# 2. Fichiers sécurisés
print_step "Copie des fichiers sécurisés..."
cp "$DOWNLOADS_DIR/app_secure.py" app.py
cp "$DOWNLOADS_DIR/auth_secure.py" auth.py

# 3. Templates
print_step "Copie des templates..."
cp "$DOWNLOADS_DIR/login_final.html" templates/login.html
cp "$DOWNLOADS_DIR/index_final.html" templates/index.html
cp "$DOWNLOADS_DIR/config_final.html" templates/config.html
cp "$DOWNLOADS_DIR/stats_final.html" templates/stats.html

# 4. Fichiers exemple
print_step "Création des fichiers exemple..."
cp "$DOWNLOADS_DIR/.env.example" .env.example
cp "$DOWNLOADS_DIR/config.json.example" config.json.example

# 5. .gitignore
print_step "Mise à jour du .gitignore..."
cp "$DOWNLOADS_DIR/.gitignore" .gitignore

# 6. Documentation
print_step "Copie de la documentation..."
mkdir -p docs
cp "$DOWNLOADS_DIR/INSTALLATION_SIMPLE.md" docs/
cp "$DOWNLOADS_DIR/INSTALLATION_SECURITE.md" docs/
cp "$DOWNLOADS_DIR/INSTALLATION_HTTPS.md" docs/
cp "$DOWNLOADS_DIR/INSTALLATION_CSRF.md" docs/
cp "$DOWNLOADS_DIR/GUIDE_INSTALLATION_SYSTEM.md" docs/

# 7. README
print_step "Mise à jour du README..."
if [ -f "README.md" ]; then
    mv README.md README.old.md
fi
cp "$DOWNLOADS_DIR/README.md" README.md

# 8. Vérification
print_step "Vérification des fichiers..."

echo ""
print_info "Fichiers prêts à être commités :"
echo "  • install.sh"
echo "  • update.sh"
echo "  • requirements.txt"
echo "  • app.py (sécurisé)"
echo "  • auth.py (sécurisé)"
echo "  • templates/*.html (4 fichiers)"
echo "  • .env.example"
echo "  • config.json.example"
echo "  • .gitignore"
echo "  • docs/ (5 fichiers)"
echo "  • README.md"
echo ""

print_info "Prochaines étapes :"
echo "  1. Vérifier les changements : git status"
echo "  2. Ajouter les fichiers : git add ."
echo "  3. Commit : git commit -m '🎉 Version 2.0 - Sécurité + Installation automatique'"
echo "  4. Push : git push origin main"
echo "  5. Créer une release sur GitHub"
echo ""

print_step "Préparation terminée !"

