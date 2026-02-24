#!/bin/bash

# Script de test pour la configuration réseau
# Permet de tester sans risque

echo "=========================================="
echo "Test de la configuration réseau FM Monitor"
echo "=========================================="
echo ""

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction de test
test_step() {
    local step=$1
    local description=$2
    echo -n "[$step] $description... "
}

pass() {
    echo -e "${GREEN}✓ OK${NC}"
}

fail() {
    echo -e "${RED}✗ ÉCHEC${NC}"
    echo "   $1"
}

warn() {
    echo -e "${YELLOW}⚠ ATTENTION${NC}"
    echo "   $1"
}

# Test 1 : jq installé
test_step "1" "Vérification de jq"
if command -v jq &> /dev/null; then
    pass
else
    fail "jq n'est pas installé. Installez-le avec: sudo apt install jq"
    exit 1
fi

# Test 2 : Script apply_network.sh existe
test_step "2" "Présence de apply_network.sh"
if [ -f "$HOME/fm-monitor/apply_network.sh" ]; then
    pass
else
    fail "Script apply_network.sh introuvable dans ~/fm-monitor/"
    echo "   Copiez-le avec: cp ~/Téléchargements/apply_network.sh ~/fm-monitor/"
    exit 1
fi

# Test 3 : Script exécutable
test_step "3" "Permissions du script"
if [ -x "$HOME/fm-monitor/apply_network.sh" ]; then
    pass
else
    fail "Script non exécutable"
    echo "   Corrigez avec: chmod +x ~/fm-monitor/apply_network.sh"
    exit 1
fi

# Test 4 : Permissions sudo
test_step "4" "Permissions sudo"
if sudo -n /home/graffiti/fm-monitor/apply_network.sh &> /dev/null; then
    pass
else
    warn "Le script ne peut pas être exécuté avec sudo sans mot de passe"
    echo "   Configurez avec: sudo visudo -f /etc/sudoers.d/fm-monitor"
    echo "   Ajoutez: graffiti ALL=(ALL) NOPASSWD: /home/graffiti/fm-monitor/apply_network.sh"
fi

# Test 5 : config.json existe
test_step "5" "Présence de config.json"
if [ -f "$HOME/fm-monitor/config.json" ]; then
    pass
else
    fail "config.json introuvable"
    exit 1
fi

# Test 6 : Section network dans config.json
test_step "6" "Section network dans config.json"
if jq -e '.network' "$HOME/fm-monitor/config.json" &> /dev/null; then
    pass
else
    warn "Pas de section 'network' dans config.json"
    echo "   Normal si vous n'avez pas encore sauvegardé la config réseau"
fi

# Test 7 : Sauvegardes des configs système
test_step "7" "Sauvegardes des configs réseau"
if [ -f "/etc/dhcpcd.conf.backup" ]; then
    pass
else
    warn "Pas de sauvegarde de /etc/dhcpcd.conf"
    echo "   Créez-la avec: sudo cp /etc/dhcpcd.conf /etc/dhcpcd.conf.backup"
fi

# Test 8 : app.py modifié
test_step "8" "Modification de app.py"
if grep -q "apply_network.sh" "$HOME/fm-monitor/app.py" 2>/dev/null; then
    pass
else
    warn "app.py ne semble pas modifié"
    echo "   Suivez le guide PATCH_APP_PY.md"
fi

# Test 9 : subprocess importé dans app.py
test_step "9" "Import subprocess dans app.py"
if grep -q "import subprocess" "$HOME/fm-monitor/app.py" 2>/dev/null; then
    pass
else
    warn "subprocess n'est pas importé dans app.py"
    echo "   Ajoutez 'import subprocess' en haut du fichier"
fi

# Test 10 : Service fm-monitor actif
test_step "10" "Service fm-monitor"
if systemctl is-active --quiet fm-monitor; then
    pass
else
    warn "Service fm-monitor non actif"
    echo "   Démarrez-le avec: sudo systemctl start fm-monitor"
fi

echo ""
echo "=========================================="
echo "Résumé du test"
echo "=========================================="

# Afficher l'IP actuelle
echo ""
echo "Configuration réseau actuelle:"
echo "  IP eth0: $(ip -4 addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo 'N/A')"
echo "  Passerelle: $(ip route | grep default | awk '{print $3}' || echo 'N/A')"
echo ""

# Afficher le contenu de la section network de config.json
if [ -f "$HOME/fm-monitor/config.json" ]; then
    echo "Configuration réseau dans config.json:"
    jq -r '.network // "Pas de section network"' "$HOME/fm-monitor/config.json" 2>/dev/null | head -10
    echo ""
fi

# Recommandations
echo "=========================================="
echo "Prochaines étapes recommandées:"
echo "=========================================="
echo ""
echo "1. Vérifiez que toutes les étapes sont OK (✓)"
echo "2. Créez les sauvegardes si manquantes:"
echo "   sudo cp /etc/dhcpcd.conf /etc/dhcpcd.conf.backup"
echo ""
echo "3. Test en mode DHCP (sans risque):"
echo "   - Allez sur http://192.168.1.185:5000/config"
echo "   - Vérifiez que le toggle est sur DHCP"
echo "   - Cliquez Enregistrer"
echo "   - Vérifiez les logs: tail -20 ~/fm-monitor/network_apply.log"
echo ""
echo "4. Test en IP fixe (AVEC ACCÈS PHYSIQUE REQUIS):"
echo "   - Configurez une IP proche de l'actuelle"
echo "   - Cliquez Enregistrer"
echo "   - Attendez 15 secondes"
echo "   - Reconnectez-vous à la nouvelle IP"
echo ""

exit 0
