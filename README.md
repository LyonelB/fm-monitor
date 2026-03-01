# 🎙️ FM Monitor

![Version](https://img.shields.io/badge/version-0.3.1-blue.svg)
![Python](https://img.shields.io/badge/python-3.13-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

**Système professionnel de monitoring de stations de radio FM** basé sur Raspberry Pi et RTL-SDR avec streaming Icecast2, décodage RDS temps réel, et interface web moderne.

---

## ✨ Fonctionnalités principales

### 🎵 Streaming Audio Professionnel (v0.3.1)
- **Serveur Icecast2 HTTPS** : Streaming stable 24/7 sans corruption
- **Multi-auditeurs** : Jusqu'à 100 auditeurs simultanés
- **Qualité broadcast** : MP3 128 kbps stéréo
- **Reconnexion automatique** : Gestion intelligente des déconnexions

### 📻 Monitoring Radio
- **Décodage RDS en temps réel** : Titre, artiste, station (PI, PS, RT)
- **VU-mètre temps réel** : Visualisation du niveau audio
- **Détection de silence** : Alertes automatiques
- **Historique audio** : Graphiques des 60 dernières minutes

### 🔔 Surveillance et Alertes
- **Watchdog intelligent** : Surveillance continue du signal
- **Alertes email** : Notifications en cas de problème
- **Dashboard temps réel** : Interface web responsive
- **Statistiques détaillées** : Temps d'écoute, coupures, qualité signal

### 🔐 Système de Licences (v0.3.1)
- **Lite (gratuit)** : Streaming + VU-mètre
- **Full Trial (30 jours)** : Toutes fonctionnalités
- **Full Permanent** : Licence à vie avec RDS, Watchdog, Alertes

---

## 🚀 Installation rapide

### Prérequis

**Hardware**
- Raspberry Pi 3/4/5 (4GB RAM recommandé)
- RTL-SDR USB (RTL-SDR Blog V3/V4 recommandé)
- Antenne FM (dipôle ou télescopique)
- Carte microSD 32GB minimum
- Alimentation stable 5V/3A

**Système**
- Raspberry Pi OS (Debian Bookworm/Trixie)
- Python 3.13+
- 2GB espace disque libre

### Installation automatique

```bash
# 1. Cloner le dépôt
git clone https://github.com/LyonelB/fm-monitor.git
cd fm-monitor

# 2. Lancer l'installation
chmod +x install.sh
sudo ./install.sh

# 3. Configurer
cp config.json.example config.json
nano config.json  # Éditer la fréquence, gain, etc.

# 4. Démarrer
sudo systemctl start fm-monitor
sudo systemctl enable fm-monitor
```

### Accès à l'interface

**Dashboard** : `https://[IP-RASPBERRY]:5000`

**Login par défaut** :
- Username: `admin`
- Password: `admin` (⚠️ À changer immédiatement)

---

## 📖 Installation Icecast2 (v0.3.1)

Le streaming professionnel nécessite Icecast2 :

```bash
# 1. Installer Icecast2 et ffmpeg
sudo apt update
sudo apt install -y icecast2 ffmpeg

# 2. Configurer Icecast (voir docs/)
sudo systemctl enable icecast2
sudo systemctl start icecast2

# 3. Le stream sera disponible sur :
# HTTP:  http://[IP]:8000/fmmonitor
# HTTPS: https://[IP]:8443/fmmonitor
```

**Documentation complète** : Voir `docs/INSTALLATION_ICECAST2.md`

---

## 🎛️ Configuration

### Fichier `config.json`

```json
{
  "frequency": "88.6",
  "gain": "40",
  "ppm_error": "0",
  "output_rate": "44100",
  "silence_threshold": "-40",
  "silence_duration": "30",
  "watchdog_enabled": true,
  "email_alerts": {
    "enabled": false,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "from_email": "votre@email.com",
    "to_email": "destination@email.com",
    "password": "votre_mot_de_passe"
  }
}
```

### Paramètres principaux

| Paramètre | Description | Valeur par défaut |
|---|---|---|
| `frequency` | Fréquence FM en MHz | `88.6` |
| `gain` | Gain RTL-SDR (0-50) | `40` |
| `ppm_error` | Correction PPM | `0` |
| `silence_threshold` | Seuil silence en dB | `-40` |
| `watchdog_enabled` | Surveillance active | `true` |

---

## 🎨 Interface Web

### Dashboard Principal
- 📊 **Stats temps réel** : Signal, RDS, uptime
- 🎵 **Player intégré** : Écoute directe du stream
- 📈 **Graphiques** : Historique niveau audio
- 🟢 **Status services** : RDS, Watchdog, Alertes

### Pages disponibles
- `/` - Dashboard principal
- `/config` - Configuration système
- `/stats` - Statistiques détaillées
- `/license` - Gestion licences

---

## 🔧 Architecture Technique

### Pipeline Audio (v0.3.1)

```
Antenne FM → RTL-SDR USB
              ↓
          rtl_fm (démodulation FM)
              ↓
          ┌───┴───┐
          ↓       ↓
       redsea   ffmpeg (encodage MP3)
      (RDS)         ↓
                Icecast2 HTTPS
                    ↓
              Flask Proxy (/stream.mp3)
                    ↓
              Player Web (Dashboard)
```

### Stack Technique

**Backend**
- Python 3.13
- Flask 3.1.0
- SQLite (base de données)
- Icecast2 (streaming server)

**Frontend**
- HTML5 + JavaScript vanilla
- Tailwind CSS
- Chart.js (graphiques)
- SSE (Server-Sent Events)

**Audio**
- rtl_fm (démodulation)
- ffmpeg (encodage)
- redsea (décodage RDS)
- Icecast2 (diffusion)

---

## 📦 Dépendances

### Paquets système

```bash
sudo apt install -y \
  rtl-sdr \
  sox \
  ffmpeg \
  icecast2 \
  redsea \
  python3-pip \
  python3-venv
```

### Modules Python

Voir `requirements.txt` :
- Flask (serveur web)
- Flask-HTTPAuth (authentification)
- Flask-Limiter (rate limiting)
- bcrypt (hashage mots de passe)
- requests (proxy HTTP)

---

## 🔐 Sécurité

### HTTPS Obligatoire

FM Monitor utilise HTTPS par défaut avec des certificats auto-signés. Pour un certificat valide :

```bash
# Let's Encrypt (si domaine public)
sudo certbot certonly --standalone -d votre-domaine.com

# Copier les certificats
sudo cp /etc/letsencrypt/live/votre-domaine.com/fullchain.pem cert.pem
sudo cp /etc/letsencrypt/live/votre-domaine.com/privkey.pem key.pem
```

### Authentification

- **HTTP Basic Auth** : Login/password sur toutes les pages
- **CSRF Protection** : Tokens CSRF sur formulaires
- **Rate Limiting** : 50 requêtes/heure (routes sensibles)

### Système de Licences

- Clés cryptographiques HMAC SHA-256
- Une clé = un email unique
- Anti-partage (activation unique)
- Traçabilité complète

---

## 🐛 Dépannage

### Le stream ne fonctionne pas

```bash
# Vérifier Icecast
sudo systemctl status icecast2

# Vérifier le mountpoint
curl -I http://localhost:8000/fmmonitor

# Voir les logs
sudo journalctl -u fm-monitor -f
```

### Pas de son / Son métallique

```bash
# Vérifier le gain RTL-SDR
rtl_test -t

# Tester la fréquence
rtl_fm -f 88.6M -M wbfm -s 171k - | play -r 171k -t raw -e s -b 16 -c 1 -V1 -
```

### RDS ne décode pas

```bash
# Vérifier redsea
echo "" | redsea -p

# Voir les logs RDS
cat /tmp/rds_output.json
```

### Erreurs 429 (Too Many Requests)

Routes fréquentes déjà exemptées du rate limiting. Si problème persiste, vérifier `app.py` ligne 190+.

---

## 📊 Performances

### Raspberry Pi 3
- CPU : ~15-25%
- RAM : ~200-300 MB
- Bande passante : ~0.5 Mbps (par auditeur)

### Raspberry Pi 4/5
- CPU : ~8-15%
- RAM : ~200-300 MB
- Multi-streaming possible (plusieurs fréquences)

---

## 🗺️ Roadmap

### v0.4.0 (Q2 2026)
- [ ] Filtres audio ffmpeg (compresseur, égaliseur)
- [ ] Support DAB+ (via rtl_tcp)
- [ ] Dashboard multi-stations
- [ ] Export données CSV/JSON
- [ ] API REST publique

### v0.5.0 (Q3 2026)
- [ ] Mobile app (iOS/Android)
- [ ] Reconnaissance musicale (Shazam-like)
- [ ] Détection publicités
- [ ] Enregistrement programmé

### Idées futures
- [ ] Support SDRplay, HackRF
- [ ] Machine Learning (détection genres)
- [ ] Cloud streaming (AWS/Azure)

---

## 🤝 Contribution

Les contributions sont les bienvenues !

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

**Guidelines** :
- Code Python PEP 8
- Tests unitaires si possible
- Documentation claire
- Pas de fichiers sensibles (licences, certificats)

---

## 📄 Licence

Ce projet est sous licence MIT - voir `LICENSE` pour détails.

**IMPORTANT** : Le système de génération de licences (`generate_license.py`, `license_manager.py`) n'est **pas** inclus dans ce dépôt pour des raisons de sécurité commerciale.

---

## 🙏 Remerciements

- **rtl-sdr** : https://osmocom.org/projects/rtl-sdr
- **redsea** : https://github.com/windytan/redsea
- **Icecast** : https://icecast.org/
- **Flask** : https://flask.palletsprojects.com/
- **Tailwind CSS** : https://tailwindcss.com/

---

## 📞 Support

- **Issues** : [GitHub Issues](https://github.com/LyonelB/fm-monitor/issues)
- **Discussions** : [GitHub Discussions](https://github.com/LyonelB/fm-monitor/discussions)
- **Email** : support@fm-monitor.com

---

## 🌟 Star History

Si ce projet vous est utile, n'hésitez pas à lui donner une ⭐ !

---

**Développé avec ❤️ par la communauté radio**

Dernière mise à jour : 1er mars 2026
