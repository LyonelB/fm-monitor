# Changelog

All notable changes to FM Monitor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-02-26

### Added
- ✨ Système de licences Lite/Full avec validation cryptographique
  - Version Lite (gratuite) : Streaming audio + VU-mètre
  - Version Full (payante) : RDS + Alertes + Stats + Config réseau
  - Interface d'activation sur `/license`
  - Décorateur `@license_required()` pour protéger les routes
  - Générateur de clés admin (`generate_license.py`)
  - Suite de tests complète (`test_license.py`)
- ✨ Email de rétablissement du signal avec durée totale
- ✨ Historique des alertes groupé par paires (perte + retour) sur une ligne
- ✨ Configuration réseau complète (eth0 + wlan0)
- ✨ Script `apply_network.sh` pour appliquer la config réseau automatiquement
- 📊 API `/api/alerts/history/grouped` pour les alertes groupées
- 📝 Documentation complète du système de licences

### Fixed
- 🐛 **CRITICAL**: Mot de passe WiFi écrasé lors de modification de config
- 🐛 Gain RTL-SDR non sauvegardé correctement
- 🐛 Email de rétablissement bloqué par cooldown
- 🐛 Durée des alertes toujours affichée à 15s au lieu de la durée réelle
- 🐛 DNS non appliqués correctement sur le système
- 🐛 Problèmes de résolution DNS sur Raspberry Pi (apt update)
- 🐛 WiFi ne se connecte pas automatiquement au boot

### Changed
- 🔧 Cooldown email réduit de 30 min → 1 min pour les pertes de signal
- 🔧 Cooldown ignoré pour les emails de rétablissement
- 🔧 Terminologie : "Gratuit/Premium" → "Lite/Full" (plus professionnel)
- 🔧 Templates email : Style visuel différencié (rouge pour perte, vert pour rétablissement)
- 🔧 dhcpcd remplace NetworkManager comme gestionnaire réseau par défaut
- 🔧 `wpa_supplicant-wlan0.conf` créé automatiquement

### Security
- 🔒 Validation cryptographique des licences (HMAC SHA-256)
- 🔒 Mot de passe WiFi préservé dans config.json (ne s'écrase plus)
- 🔒 Clés de licence impossibles à deviner ou craquer

## [2.0.0] - 2026-02-23

### Added
- ✨ Interface web moderne avec Tailwind CSS
- ✨ Authentification sécurisée avec Bcrypt
- ✨ Protection CSRF
- ✨ Rate limiting
- ✨ Support HTTPS avec certificats SSL
- ✨ VU-mètre temps réel
- ✨ Décodage RDS (PS, RT, PI)
- ✨ Alertes email
- ✨ Base de données SQLite pour l'historique
- ✨ Streaming audio MP3
- ✨ Configuration via interface web
- 📊 Page statistiques avec graphiques
- 📝 Service systemd pour démarrage automatique

### Changed
- 🔧 Architecture complètement refaite
- 🔧 Python 3 avec Flask
- 🔧 Un seul processus rtl_fm avec tee pour RDS + Audio + RMS

### Security
- 🔒 Hashage Bcrypt pour les mots de passe
- 🔒 Protection CSRF
- 🔒 Rate limiting (50/heure)
- 🔒 HTTPS par défaut

## [1.0.0] - 2024-XX-XX

### Added
- 🎉 Version initiale
- 📻 Surveillance FM basique avec RTL-SDR
- 📧 Alertes email simples
- 📊 Monitoring du niveau audio

---

## Types de changements

- `Added` : Nouvelles fonctionnalités
- `Changed` : Modifications de fonctionnalités existantes
- `Deprecated` : Fonctionnalités obsolètes (à supprimer prochainement)
- `Removed` : Fonctionnalités supprimées
- `Fixed` : Corrections de bugs
- `Security` : Corrections de vulnérabilités de sécurité

## Légende des emojis

- ✨ Nouvelle fonctionnalité
- 🐛 Correction de bug
- 🔧 Amélioration
- 📊 API
- 📝 Documentation
- 🔒 Sécurité
- ⚡ Performance
- 🎨 UI/UX
