#!/bin/bash
# Script pour ajouter automatiquement CSRF Protection aux templates HTML

echo "=========================================="
echo "Ajout de CSRF Protection aux templates"
echo "=========================================="
echo ""

TEMPLATES_DIR="$HOME/fm-monitor/templates"
BACKUP_DIR="$HOME/fm-monitor/templates_backup_csrf_$(date +%Y%m%d_%H%M%S)"

# Créer un backup
echo "1. Sauvegarde des templates actuels..."
mkdir -p "$BACKUP_DIR"
cp -r "$TEMPLATES_DIR"/* "$BACKUP_DIR/"
echo "✅ Backup créé dans : $BACKUP_DIR"
echo ""

# Fonction pour ajouter la balise meta CSRF
add_csrf_meta() {
    local file=$1
    echo "   Traitement de $file..."
    
    # Vérifier si la balise meta CSRF existe déjà
    if grep -q 'name="csrf-token"' "$file"; then
        echo "   ⚠️  Balise meta CSRF déjà présente, ignoré"
        return
    fi
    
    # Ajouter la balise meta après la balise viewport
    sed -i '/<meta name="viewport"/a \  <meta name="csrf-token" content="{{ csrf_token() }}">' "$file"
    echo "   ✅ Balise meta CSRF ajoutée"
}

# Fonction pour ajouter la fonction getCSRFToken
add_csrf_function() {
    local file=$1
    
    # Vérifier si la fonction existe déjà
    if grep -q 'function getCSRFToken' "$file"; then
        echo "   ⚠️  Fonction getCSRFToken déjà présente, ignoré"
        return
    fi
    
    # Trouver la première balise <script> et ajouter la fonction après
    # Si pas de <script>, ajouter avant </body>
    if grep -q '<script>' "$file"; then
        sed -i '0,/<script>/s/<script>/<script>\n    \/\/ Fonction pour récupérer le token CSRF\n    function getCSRFToken() {\n      const meta = document.querySelector('\''meta[name="csrf-token"]'\'');\n      return meta ? meta.content : '\'''\'';\n    }\n/' "$file"
        echo "   ✅ Fonction getCSRFToken ajoutée"
    else
        sed -i 's|</body>|  <script>\n    // Fonction pour récupérer le token CSRF\n    function getCSRFToken() {\n      const meta = document.querySelector('\''meta[name="csrf-token"]'\'');\n      return meta ? meta.content : '\'''\'';\n    }\n  </script>\n</body>|' "$file"
        echo "   ✅ Fonction getCSRFToken ajoutée (nouvelle balise script créée)"
    fi
}

echo "2. Ajout des balises meta CSRF..."
for file in "$TEMPLATES_DIR"/*.html; do
    if [ -f "$file" ]; then
        add_csrf_meta "$file"
    fi
done
echo ""

echo "3. Ajout de la fonction getCSRFToken()..."
for file in "$TEMPLATES_DIR"/*.html; do
    if [ -f "$file" ]; then
        add_csrf_function "$file"
    fi
done
echo ""

echo "=========================================="
echo "✅ CSRF Protection ajoutée aux templates"
echo "=========================================="
echo ""
echo "⚠️  IMPORTANT :"
echo "   Les balises meta et la fonction JavaScript ont été ajoutées."
echo "   Vous devez MANUELLEMENT ajouter 'X-CSRFToken' dans les headers"
echo "   de toutes les requêtes POST fetch()."
echo ""
echo "   Exemple :"
echo "   fetch('/api/config/save', {"
echo "     method: 'POST',"
echo "     headers: {"
echo "       'Content-Type': 'application/json',"
echo "       'X-CSRFToken': getCSRFToken()  // ← AJOUTER CETTE LIGNE"
echo "     },"
echo "     body: JSON.stringify(data)"
echo "   })"
echo ""
echo "📁 Backup des templates originaux : $BACKUP_DIR"
echo ""
