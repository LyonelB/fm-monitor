#!/bin/bash
# Script de nettoyage avant publication GitHub v0.3.1
# Supprime les fichiers sensibles et les backups

set -e

echo "🧹 Nettoyage du dépôt FM Monitor avant publication..."
echo ""

# Vérifier qu'on est dans le bon dossier
if [ ! -f "app.py" ] || [ ! -f "monitor.py" ]; then
    echo "❌ Erreur : Ce script doit être exécuté depuis ~/fm-monitor"
    exit 1
fi

echo "📍 Dossier actuel : $(pwd)"
echo ""

# Sauvegarder les fichiers sensibles dans un dossier privé
BACKUP_DIR="$HOME/fm-monitor-private-backup-$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

echo "💾 Sauvegarde des fichiers sensibles dans $BACKUP_DIR..."

# Sauvegarder fichiers sensibles
cp -v cert.pem key.pem "$BACKUP_DIR/" 2>/dev/null || true
cp -v license.json licenses_db.json generated_licenses.json "$BACKUP_DIR/" 2>/dev/null || true
cp -v generate_license.py license_manager.py "$BACKUP_DIR/" 2>/dev/null || true
cp -v config.json .env "$BACKUP_DIR/" 2>/dev/null || true
cp -v fm_monitor.db "$BACKUP_DIR/" 2>/dev/null || true

echo ""
echo "🗑️  Suppression des fichiers à ne pas publier..."

# Supprimer fichiers sensibles
rm -vf cert.pem key.pem 2>/dev/null || true
rm -vf license.json licenses_db.json generated_licenses.json 2>/dev/null || true
rm -vf generate_license.py license_manager.py 2>/dev/null || true
rm -vf license_*.backup generate_license_*.backup license_manager_*.backup 2>/dev/null || true
rm -vf .env 2>/dev/null || true
rm -vf fm_monitor.db 2>/dev/null || true
rm -vf network_apply.log 2>/dev/null || true

echo ""
echo "🗑️  Suppression des backups..."

# Supprimer backups
rm -vf *.backup *.old *.bak 2>/dev/null || true
rm -vf app.py.before_* monitor.py.before_* 2>/dev/null || true
rm -vf app_backup_*.py app_before_*.py monitor_backup.py 2>/dev/null || true
rm -vf config.html 2>/dev/null || true
rm -vf README.old.md CONFIGURATION.md 2>/dev/null || true

echo ""
echo "🗑️  Suppression des scripts temporaires..."

# Supprimer scripts temporaires
rm -vf activate_license_protections.py 2>/dev/null || true
rm -vf add_csrf_to_templates.sh add_licence_link.py add_protections.py 2>/dev/null || true
rm -vf apply_network.sh apply_network_v1_backup.sh 2>/dev/null || true
rm -vf migrate_to_icecast.py migrate_passwords.py 2>/dev/null || true
rm -vf test_license.py test_network_setup.sh 2>/dev/null || true
rm -vf diagnostic.sh 2>/dev/null || true
rm -vf install_tailwind.sh 2>/dev/null || true

echo ""
echo "🗑️  Suppression des dossiers temporaires..."

# Supprimer dossiers temporaires
rm -rvf templates_backup_* 2>/dev/null || true
rm -rvf "{templates,static" 2>/dev/null || true
rm -rvf __pycache__ 2>/dev/null || true
rm -rvf logs 2>/dev/null || true

echo ""
echo "📊 Taille du dépôt après nettoyage :"
du -sh .

echo ""
echo "✅ Nettoyage terminé !"
echo ""
echo "📦 Fichiers sauvegardés dans : $BACKUP_DIR"
echo ""
echo "⚠️  IMPORTANT : Vérifiez avec 'git status' avant de commit !"
echo ""
echo "Prochaines étapes :"
echo "  1. git status                    # Vérifier les changements"
echo "  2. git add .                     # Ajouter les fichiers"
echo "  3. git commit -m 'v0.3.1'        # Commiter"
echo "  4. git tag v0.3.1                # Créer le tag"
echo "  5. git push origin main --tags   # Publier"
echo ""
