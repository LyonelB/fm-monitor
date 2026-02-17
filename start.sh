#!/bin/bash
# Script de démarrage rapide pour tester l'application
# À utiliser APRÈS avoir exécuté install.sh

echo "=========================================="
echo "Démarrage du système de surveillance FM"
echo "=========================================="
echo ""

# Vérifier que l'installation a été faite
if [ ! -d "venv" ]; then
    echo "❌ L'environnement virtuel n'existe pas"
    echo "Veuillez d'abord exécuter: sudo ./install.sh"
    exit 1
fi

# Vérifier que la clé RTL-SDR est branchée
if ! lsusb | grep -q "RTL"; then
    echo "⚠️  Attention: Aucune clé RTL-SDR détectée"
    echo "Veuillez vérifier que votre clé est bien branchée"
    echo ""
    read -p "Continuer quand même ? (o/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Oo]$ ]]; then
        exit 1
    fi
fi

# Vérifier que config.json existe et a été modifié
if [ ! -f "config.json" ]; then
    echo "❌ Le fichier config.json n'existe pas"
    exit 1
fi

# Activer l'environnement virtuel
source venv/bin/activate

# Afficher l'IP locale
IP=$(hostname -I | awk '{print $1}')
echo "✅ Serveur web démarré"
echo ""
echo "🌐 Accès à l'interface web:"
echo "   Local:  http://localhost:5000"
echo "   Réseau: http://$IP:5000"
echo ""
echo "⏹️  Pour arrêter: Appuyez sur Ctrl+C"
echo ""
echo "=========================================="
echo ""

# Démarrer l'application
python3 app.py
