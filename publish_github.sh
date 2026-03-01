#!/bin/bash
# Script de publication FM Monitor v2.1.0 sur GitHub
# À exécuter depuis ~/fm-monitor

echo "🚀 Publication FM Monitor v2.1.0 sur GitHub"
echo ""

# Vérifier qu'on est dans le bon dossier
if [ ! -f "app.py" ]; then
    echo "❌ Erreur : Vous devez être dans le dossier ~/fm-monitor"
    exit 1
fi

echo "📋 Étape 1 : Ajout des nouveaux fichiers..."
git add .gitignore
git add license_manager.py
git add generate_license.py
git add test_license.py
git add templates/license.html
git add apply_network.sh
git add CHANGELOG.md

echo "✅ Nouveaux fichiers ajoutés"
echo ""

echo "📝 Étape 2 : Ajout des fichiers modifiés..."
git add app.py
git add monitor.py
git add email_alert.py
git add database.py
git add templates/stats.html
git add README.md

echo "✅ Fichiers modifiés ajoutés"
echo ""

echo "📚 Étape 3 : Ajout de la documentation..."
git add docs/

echo "✅ Documentation ajoutée"
echo ""

echo "💾 Étape 4 : Création du commit..."
git commit -m "v2.1.0 - Système de licences Lite/Full + Alertes intelligentes

Fonctionnalités majeures :
- Système de licences avec validation cryptographique
- Email de rétablissement du signal avec durée totale
- Historique des alertes groupé par paires
- Configuration réseau complète (eth0 + wlan0)
- Script apply_network.sh pour config automatique

Corrections importantes :
- Mot de passe WiFi écrasé lors de modifications (CRITICAL)
- Gain RTL-SDR non sauvegardé
- Email de rétablissement bloqué par cooldown
- DNS non appliqués correctement

Améliorations :
- Cooldown email intelligent (1 min / ignoré pour rétablissements)
- Templates email différenciés (rouge/vert)
- Support WiFi automatique au boot
- dhcpcd remplace NetworkManager
"

echo "✅ Commit créé"
echo ""

echo "🏷️  Étape 5 : Création du tag v2.1.0..."
git tag -a v2.1.0 -m "Version 2.1.0 - Licences Lite/Full et alertes intelligentes"

echo "✅ Tag créé"
echo ""

echo "🚀 Étape 6 : Push vers GitHub..."
echo "⚠️  Vous allez devoir entrer vos identifiants GitHub"
echo ""

# Push du code
git push origin main

# Push du tag
git push origin v2.1.0

echo ""
echo "🎉 Publication terminée !"
echo ""
echo "📋 Prochaines étapes :"
echo "1. Aller sur https://github.com/LyonelB/fm-monitor"
echo "2. Cliquer sur 'Releases' → 'Draft a new release'"
echo "3. Sélectionner le tag v2.1.0"
echo "4. Copier les Release Notes depuis PUBLICATION_GITHUB_ETAPES.md"
echo "5. Publier la release"
echo ""
echo "✅ FM Monitor v2.1.0 est maintenant sur GitHub !"
