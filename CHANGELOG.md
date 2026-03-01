# Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [0.3.1] - 2026-03-01

### 🎉 Fonctionnalités majeures

#### Streaming Icecast2 professionnel
- **Remplacement du streaming par fichier** : Migration de sox > /tmp/fm_stream.mp3 vers ffmpeg > Icecast2 HTTPS
- **Serveur Icecast2** : Configuration HTTPS avec certificats SSL
- **Proxy Flask** : Route `/stream.mp3` proxifie Icecast pour éviter Mixed Content
- **Stabilité 24/7** : Élimination des corruptions audio après plusieurs heures de fonctionnement
- **Multi-auditeurs** : Support de jusqu'à 100 auditeurs simultanés
- **Reconnexion automatique** : Le stream se reconnecte automatiquement en cas de coupure

#### Système de licences v3
- **Trois niveaux de licence** :
  - **Lite (gratuit)** : Streaming et VU-mètre uniquement
  - **Full Trial (30 jours)** : Toutes fonctionnalités pendant 30 jours
  - **Full Permanent (199€)** : Toutes fonctionnalités à vie
- **Clés uniques** : Chaque licence générée est unique avec HMAC SHA-256
- **Association email** : Chaque clé est liée à une adresse email unique
- **Anti-partage** : Une clé ne peut être activée qu'une seule fois
- **Multi-licences** : Un email peut avoir plusieurs licences (ex: 3 Raspberry Pi)
- **Base de données** : Traçabilité complète dans `licenses_db.json`
- **Interface d'activation** : Page `/license` pour activer et gérer les licences

### ✨ Améliorations

#### Interface utilisateur
- **Masquage frontend** : Fonctionnalités Full grisées et désactivées en mode Lite
- **Badges visuels** : Indicateurs "Full" sur les fonctionnalités premium
- **Messages CTA** : Call-to-action pour upgrade vers Trial ou Permanent
- **Sidebar cohérente** : Design unifié sur toutes les pages (Dashboard, Config, Stats, Licence)

#### Performance et stabilité
- **Rate limiting optimisé** : Exemption pour routes appelées fréquemment
  - `/stream.mp3` : Stream audio continu
  - `/api/stats` : Appelée toutes les 10 secondes
  - `/api/services/status` : Appelée toutes les 5 secondes
  - `/api/stream/stats` : SSE (Server-Sent Events) continu
  - `/api/audio/history` : Historique temps réel
- **Gestion mémoire** : Optimisation du streaming pour éviter les fuites mémoire
- **Reconnexion ffmpeg** : Gestion automatique des déconnexions Icecast

#### Sécurité
- **Certificats SSL** : Support complet HTTPS pour Icecast et Flask
- **CORS configuré** : Headers Access-Control-Allow-Origin pour le streaming
- **Validation cryptographique** : HMAC SHA-256 pour les clés de licence
- **Protection backend** : Décorateur `@license_required()` sur les routes premium

### 🔧 Corrections

#### Streaming audio
- **Corruption après plusieurs heures** : Résolu via migration vers Icecast2
- **Son métallique** : Éliminé grâce au streaming professionnel
- **Décalage 40s** : Réduit drastiquement avec Icecast
- **Glitchs audio** : Supprimés avec pipeline ffmpeg optimisé

#### Interface web
- **Mixed Content errors** : Résolu via proxy Flask HTTPS
- **Erreurs 429 (Too Many Requests)** : Routes fréquentes exemptées du rate limiting
- **Parsing JSON** : Gestion correcte des erreurs de rate limiting
- **SSE déconnexions** : Connexion Server-Sent Events stabilisée
- **Cadres verts services** : Affichage correct du statut des services

#### Backend
- **IndentationError** : Correction du fichier monitor.py corrompu
- **Module requests manquant** : Ajout à requirements.txt
- **Certificats Icecast** : Configuration bundle.pem pour compatibilité
- **Redirections /login** : Routes publiques correctement configurées

### 🛠️ Technique

#### Architecture
- **Pipeline audio** :
  ```
  RTL-SDR → rtl_fm → ffmpeg → Icecast2 HTTPS (port 8443)
                                    ↓
                              Flask proxy (/stream.mp3)
                                    ↓
                              Player Dashboard (HTTPS port 5000)
  ```
- **Streaming** :
  - Format : MP3 128 kbps
  - Codec : libmp3lame
  - Channels : Stéréo (2)
  - Sample rate : 44100 Hz
  
#### Dépendances ajoutées
- `requests>=2.32.0` : Pour le proxy stream Icecast

#### Configuration Icecast
- Port HTTP : 8000
- Port HTTPS : 8443
- Mountpoint : `/fmmonitor`
- Certificats : Bundle cert + key
- CORS : Activé (`Access-Control-Allow-Origin: *`)

### 📚 Documentation

#### Nouveaux guides
- Guide installation Icecast2 professionnel
- Migration monitor.py vers Icecast
- Système de licences complet
- Design cohérent interface

#### Fichiers de configuration
- Configuration serveur Icecast2
- Version monitor.py avec streaming Icecast
- Templates licence avec email

### 🔒 Sécurité et confidentialité

**Fichiers exclus de GitHub** (sensibles) :
- Générateur de clés (contient SECRET_KEY)
- Gestionnaire avec SECRET_KEY
- Base de données des licences
- Licence active
- Certificats SSL
- Configuration personnelle
- Bases de données

### ⚠️ Breaking Changes

- **Streaming** : Nécessite maintenant Icecast2 installé et configuré
- **Dépendances** : Module `requests` obligatoire
- **Port HTTPS** : Icecast écoute sur 8443 (configurable)
- **Certificats** : Bundle cert+key nécessaire pour Icecast HTTPS

### 🔄 Migration depuis v0.2.x

1. Installer Icecast2 : `sudo apt install icecast2 ffmpeg`
2. Configurer certificats SSL bundle
3. Modifier monitor.py pour streaming Icecast
4. Installer requests : `pip install requests`
5. Redémarrer services

---

## [0.2.0] - 2026-02-26

### Ajouté
- Système de licences Lite/Full
- Protection routes API avec `@license_required()`
- Interface de gestion des licences
- CSRF protection sur toutes les routes
- SSL/HTTPS avec certificats auto-signés

### Modifié
- Migration vers HTTPS obligatoire
- Amélioration interface Dashboard
- Optimisation performances base de données

### Corrigé
- Fuites mémoire lors du streaming
- Erreurs CSRF sur formulaires
- Problèmes de permissions fichiers

---

## [0.1.0] - 2026-02-15

### Ajouté
- Streaming audio FM via RTL-SDR
- Décodage RDS en temps réel
- VU-mètre temps réel
- Détection de silence
- Watchdog de surveillance
- Alertes email
- Historique audio
- Configuration réseau WiFi
- Dashboard web responsive
- Base de données SQLite
- Authentification HTTP Basic

### Technique
- Flask + Python 3.13
- RTL-SDR via rtl_fm
- Décodage RDS avec redsea
- Conversion audio avec sox
- Interface Tailwind CSS

---

[0.3.1]: https://github.com/LyonelB/fm-monitor/compare/v0.2.0...v0.3.1
[0.2.0]: https://github.com/LyonelB/fm-monitor/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/LyonelB/fm-monitor/releases/tag/v0.1.0
