# 📻 FM Monitor

**Système de surveillance radio FM en temps réel pour Raspberry Pi**

Surveillez votre émetteur FM 24/7 avec alertes automatiques en cas de perte de signal, interface web moderne et sécurisée.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-3%2F4%2F5-red.svg)](https://www.raspberrypi.org/)

---

## ✨ Fonctionnalités

### 🎯 Monitoring en temps réel
- **Surveillance continue** du signal FM (24/7)
- **Détection automatique** des pertes de signal
- **VU-mètre** en direct (-60 dB à 0 dB)
- **Historique** des événements

### 📡 Décodage RDS
- **PS** (Programme Service) - Nom de la station
- **RT** (RadioText) - Texte défilant
- **PI** (Programme Identification)
- Décodage en temps réel avec `redsea`

### 📧 Alertes email
- **Email automatique** lors de perte de signal (>15s)
- **Email de rétablissement** quand le signal revient
- Support **Gmail** et autres SMTP
- Multiples destinataires

### 🎵 Streaming audio
- **Stream MP3** 128 kbps en direct
- **Player intégré** dans l'interface
- Latence minimale (~2 secondes)

### 📊 Statistiques
- **Historique** complet des alertes
- **Graphiques** de niveau audio
- **Logs système** en temps réel
- **Uptime** et métriques

### 🔒 Sécurité
- **HTTPS/TLS** (certificat SSL)
- **Authentification** Bcrypt
- **Rate limiting** (anti force-brute)
- **CSRF Protection**
- **Score sécurité : 9/10**

### 🌐 Interface moderne
- **Dashboard** responsive (Tailwind CSS)
- Compatible **mobile/tablette/desktop**
- **Thème sombre** pour la sidebar
- **Temps réel** (Server-Sent Events)

---

## 🚀 Installation rapide

### Une seule commande !

```bash
curl -sSL https://raw.githubusercontent.com/LyonelB/fm-monitor/main/install.sh | bash
```

**C'est tout !** ⏱️ Durée : 5-10 minutes

### Prérequis
- Raspberry Pi 3, 4 ou 5
- Raspberry Pi OS (Debian/Ubuntu)
- Dongle RTL-SDR (RTL2832U)
- Connexion Internet

---

## 📖 Documentation

### Guides d'installation
- [Installation simple](docs/INSTALLATION_SIMPLE.md) - Guide pas à pas
- [Installation manuelle](docs/INSTALLATION_MANUELLE.md) - Configuration avancée
- [Configuration RTL-SDR](docs/RTL-SDR.md) - Paramétrage du dongle

### Configuration
- [Configuration réseau](docs/NETWORK.md) - WiFi, IP fixe
- [Alertes email](docs/EMAIL.md) - Configuration Gmail/SMTP
- [Certificat SSL](docs/SSL.md) - HTTPS personnalisé

### Administration
- [Service systemd](docs/SYSTEMD.md) - Gestion du service
- [Mise à jour](docs/UPDATE.md) - Procédure de mise à jour
- [Sauvegardes](docs/BACKUP.md) - Stratégie de backup

### Développement
- [Architecture](docs/ARCHITECTURE.md) - Structure du code
- [API](docs/API.md) - Documentation API REST
- [Contribuer](CONTRIBUTING.md) - Guide de contribution

---

## 🛠️ Configuration rapide

### 1. Accéder à l'interface

```
https://IP_DU_RASPBERRY:5000
```

**Identifiants par défaut** :
- Username: `admin`
- Password: `password`

⚠️ **Changez le mot de passe immédiatement !**

### 2. Configurer la fréquence

**Configuration** → **Fréquence de monitoring** → Exemple : `88.6M`

### 3. Configurer les alertes email

**Configuration** → **Alertes email** :
- Email expéditeur : `votre.email@gmail.com`
- Mot de passe : [Mot de passe d'application Gmail](https://support.google.com/accounts/answer/185833)
- Destinataires : `alerte1@email.com, alerte2@email.com`

Cliquez sur **Tester** puis **Enregistrer**

---

## 🔧 Commandes utiles

```bash
# Gérer le service
sudo systemctl start fm-monitor      # Démarrer
sudo systemctl stop fm-monitor       # Arrêter
sudo systemctl restart fm-monitor    # Redémarrer
sudo systemctl status fm-monitor     # Statut

# Logs
sudo journalctl -u fm-monitor -f     # Logs en temps réel
sudo journalctl -u fm-monitor -n 100 # 100 dernières lignes

# Mise à jour
cd ~/fm-monitor
./update.sh                          # Script automatique
```

---

## 📸 Captures d'écran

### Dashboard
![Dashboard](docs/screenshots/dashboard.png)

### Configuration
![Configuration](docs/screenshots/configuration.png)

### Statistiques
![Statistiques](docs/screenshots/statistiques.png)

---

## 🏗️ Architecture technique

### Backend
- **Python 3.9+** - Langage principal
- **Flask 3.0** - Framework web
- **RTL-SDR** - Réception radio
- **Sox/Lame** - Traitement audio
- **Redsea** - Décodage RDS

### Frontend
- **Tailwind CSS** - Framework CSS
- **Vanilla JavaScript** - Pas de framework lourd
- **Server-Sent Events** - Mise à jour temps réel
- **Fetch API** - Communication AJAX

### Sécurité
- **Bcrypt** - Hashage mots de passe
- **Flask-Limiter** - Rate limiting
- **Flask-WTF** - Protection CSRF
- **OpenSSL** - Certificats SSL

---

## 📊 Spécifications techniques

| Composant | Valeur |
|-----------|--------|
| **Fréquence** | 87.5 - 108.0 MHz |
| **Sample rate** | 1.14 MHz |
| **Audio bitrate** | 128 kbps MP3 |
| **Seuil silence** | -40 dBFS (configurable) |
| **Durée alerte** | 15 secondes (configurable) |
| **Latence audio** | ~2 secondes |
| **CPU usage** | 2-4% (Raspberry Pi 4) |
| **RAM usage** | ~150 MB |

---

## 🤝 Contribuer

Les contributions sont les bienvenues ! Voir [CONTRIBUTING.md](CONTRIBUTING.md)

### Développement local

```bash
# Cloner le repo
git clone https://github.com/LyonelB/fm-monitor.git
cd fm-monitor

# Environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Dépendances
pip install -r requirements.txt

# Lancer en mode dev
python3 app.py
```

---

## 📝 Changelog

Voir [CHANGELOG.md](CHANGELOG.md) pour l'historique des versions.

### Version actuelle : 2.0.0

**Nouvelles fonctionnalités** :
- ✅ Interface Tailwind CSS moderne
- ✅ Sécurité renforcée (Bcrypt, HTTPS, CSRF)
- ✅ Configuration réseau (WiFi, IP fixe)
- ✅ Optimisations performances (-50% CPU)

---

## 📄 Licence

Ce projet est sous licence MIT. Voir [LICENSE](LICENSE) pour plus de détails.

---

## 👨‍💻 Auteur

**Lyonel B.**
- GitHub: [@LyonelB](https://github.com/LyonelB)
- Email: lyonel@fm-monitor.com

---

## 🙏 Remerciements

- [RTL-SDR](https://www.rtl-sdr.com/) - Logiciel SDR
- [Redsea](https://github.com/windytan/redsea) - Décodeur RDS
- [Flask](https://flask.palletsprojects.com/) - Framework web
- [Tailwind CSS](https://tailwindcss.com/) - Framework CSS

---

## 📞 Support

- **Documentation** : [Wiki](https://github.com/LyonelB/fm-monitor/wiki)
- **Issues** : [GitHub Issues](https://github.com/LyonelB/fm-monitor/issues)
- **Discussions** : [GitHub Discussions](https://github.com/LyonelB/fm-monitor/discussions)

---

## ⭐ Star History

Si vous aimez ce projet, n'hésitez pas à lui donner une étoile ! ⭐

[![Star History Chart](https://api.star-history.com/svg?repos=LyonelB/fm-monitor&type=Date)](https://star-history.com/#LyonelB/fm-monitor&Date)

---

**FM Monitor** - Surveillance radio FM professionnelle pour Raspberry Pi 📻
