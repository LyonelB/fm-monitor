#!/bin/bash

# Script d'installation de Tailwind CSS en local pour FM Monitor
# Ce script télécharge le CLI standalone de Tailwind et compile le CSS

set -e

echo "========================================"
echo "Installation de Tailwind CSS en local"
echo "========================================"
echo ""

# Vérifier qu'on est dans le bon répertoire
if [ ! -f "app.py" ]; then
    echo "❌ Erreur: Ce script doit être exécuté depuis ~/fm-monitor"
    echo "   Utilisez: cd ~/fm-monitor && bash install_tailwind.sh"
    exit 1
fi

echo "✓ Répertoire FM Monitor détecté"
echo ""

# Créer les dossiers nécessaires
echo "📁 Création des dossiers..."
mkdir -p static/css
mkdir -p static/js

# Télécharger le CLI standalone de Tailwind
echo "⬇️  Téléchargement de Tailwind CLI..."
cd static
if [ -f "tailwindcss" ]; then
    echo "   Tailwind CLI déjà présent, suppression..."
    rm tailwindcss
fi

curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-arm64
chmod +x tailwindcss-linux-arm64
mv tailwindcss-linux-arm64 tailwindcss
echo "✓ Tailwind CLI téléchargé"
echo ""

# Retour au répertoire principal
cd ..

# Créer le fichier de configuration Tailwind
echo "⚙️  Création de tailwind.config.js..."
cat > tailwind.config.js << 'EOF'
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
EOF
echo "✓ tailwind.config.js créé"
echo ""

# Créer le fichier CSS source
echo "📝 Création de input.css..."
cat > static/css/input.css << 'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;
EOF
echo "✓ input.css créé"
echo ""

# Compiler Tailwind
echo "🔨 Compilation de Tailwind CSS..."
./static/tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.css --minify
echo "✓ Tailwind compilé avec succès"
echo ""

# Mettre à jour les templates HTML
echo "🔄 Mise à jour des fichiers HTML..."

# Fonction pour remplacer le CDN par le CSS local dans un fichier
update_html_file() {
    local file=$1
    if [ -f "$file" ]; then
        # Vérifier si le fichier contient le CDN
        if grep -q "cdn.tailwindcss.com" "$file"; then
            # Créer une backup
            cp "$file" "${file}.backup"
            
            # Remplacer le CDN par le CSS local
            sed -i 's|<script src="https://cdn.tailwindcss.com"></script>|<link href="/static/css/tailwind.css" rel="stylesheet">|g' "$file"
            
            echo "   ✓ $file mis à jour"
        else
            echo "   ℹ️  $file n'utilise pas le CDN Tailwind"
        fi
    fi
}

# Mettre à jour les 3 fichiers
update_html_file "templates/index.html"
update_html_file "templates/config.html"
update_html_file "templates/stats.html"

echo ""
echo "========================================"
echo "✅ Installation terminée avec succès !"
echo "========================================"
echo ""
echo "📋 Résumé:"
echo "   • Tailwind CLI: ./static/tailwindcss"
echo "   • CSS compilé: ./static/css/tailwind.css"
echo "   • Templates mis à jour (backup créés)"
echo ""
echo "🔄 Redémarrez FM Monitor:"
echo "   sudo systemctl restart fm-monitor"
echo ""
echo "🔧 Pour recompiler après modification des templates:"
echo "   ./static/tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.css --minify"
echo ""
echo "👁️  Mode watch (recompilation automatique):"
echo "   ./static/tailwindcss -i ./static/css/input.css -o ./static/css/tailwind.css --watch"
echo ""
