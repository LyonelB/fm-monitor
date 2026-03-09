# 📻 FM Monitor

![Version](https://img.shields.io/badge/version-0.3.2-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%20%7C%20Linux-lightgrey.svg)

**Système open source de monitoring de stations de radio FM** basé sur Raspberry Pi / Linux et RTL-SDR, avec streaming Icecast2, décodage RDS temps réel, alertes email et interface web moderne.

---

## ✨ Fonctionnalités

### 📡 Réception & Analyse
- **Réception FM** via dongle RTL-SDR (V3, V4, compatibles RTL2832U)
- **VU-mètre temps réel** avec historique audio 24h
- **Détection de silence / perte de signal** configurable
- **Mesure de modulation** FM

### 📻 Décodage RDS
- **PS** (Programme Service) — nom de la station (8 car.)
- **RT** (RadioText) — titre/artiste en cours (64 car.) — RT complet uniquement
- **PI Code** — identifiant unique hexadécimal de la station
- **Logo station** — récupération automatique via [Radio Browser](https://www.radio-browser.info)

### 🔊 Streaming Audio
- **Serveur Icecast2** : streaming stable 24/7
- **Qualité broadcast** : MP3 128 kbps
- **Multi-auditeurs** : jusqu'à 100 connexions simultanées
- **Proxy Flask HTTPS** : écoute directement depuis le dashboard

### 🔔 Alertes & Surveillance
- **Alertes email** automatiques (perte signal + rétablissement)
- **Watchdog** : relance automatique en cas de crash
- **Historique** des alertes et niveaux audio en base SQLite

### 🌐 Interface Web
- Dashboard temps réel (SSE)
- Configuration complète via interface web
- Statistiques et historique
- Page documentation (FM, MPX, RDS, dongles)
- Responsive — accessible depuis smartphone et tablette

---

## 🔧 Matériel compatible

| Dongle | Puce | Notes |
|--------|------|-------|
| RTL-SDR Blog V3 | RTL2832U + R820T2 | Drivers standard |
| **RTL-SDR Blog V4** | RTL2832U + R828D | **Recommandé** — TCXO 1ppm, meilleure sensibilité. Nécessite le [fork officiel](https://github.com/rtlsdrblog/rtl-sdr-blog) |
| Nooelec NESDR SMArt | RTL2832U + R820T2 | Compatible standard |
| Autres RTL2832U | RTL2832U | Généralement compatibles |

### Installation drivers RTL-SDR Blog V4

```bash
# Bloquer le driver noyau générique
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtl.conf
sudo modprobe -r dvb_usb_rtl28xxu 2>/dev/null

# Compiler le fork officiel
sudo apt install -y git cmake libusb-1.0-0-dev build-essential pkg-config
git clone https://github.com/rtlsdrblog/rtl-sdr-blog
cd rtl-sdr-blog && mkdir build && cd build
cmake .. -DINSTALL_UDEV_RULES=ON
make -j$(nproc) && sudo make install && sudo ldconfig

# Règles udev
sudo cp ~/rtl-sdr-blog/rtl-sdr.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger

# Test
rtl_test -t
```

---

## 🚀 Installation

### ⚡ Installation automatique (recommandée)

> ⚠️ **Bonne pratique** : avant d'exécuter un script distant, inspectez-le :
> ```bash
> curl -sSL https://raw.githubusercontent.com/LyonelB/fm-monitor/main/install.sh -o install.sh
> less install.sh
> bash install.sh
> ```

Ou directement si vous faites confiance à la source :
```bash
curl -sSL https://raw.githubusercontent.com/LyonelB/fm-monitor/main/install.sh | bash
```

Le script installe automatiquement toutes les dépendances, compile redsea, configure Icecast2, génère les certificats SSL et démarre le service.

**Durée : ~10-15 minutes** (compilation de redsea incluse)

---

### 🔧 Installation manuelle

### Prérequis système

- Raspberry Pi 3/4/5 ou mini-PC Linux (Debian 12 / Ubuntu 22.04+)
- Python 3.11+
- `rtl_fm`, `redsea`, `ffmpeg`, `icecast2`

### 1. Cloner le dépôt

```bash
git clone https://github.com/LyonelB/fm-monitor.git
cd fm-monitor
```

### 2. Installer les dépendances

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configurer

Copier et éditer le fichier de configuration :

```bash
cp config.json.example config.json
nano config.json
```

Paramètres clés :

```json
{
  "station": {
    "name": "Ma Radio FM",
    "frequency": "98.5M"
  },
  "rtl_sdr": {
    "frequency": "98.5M",
    "gain": "40"
  },
  "email": {
    "enabled": true,
    "sender_email": "votre@gmail.com",
    "sender_password": "mot_de_passe_application",
    "recipient_emails": ["alerte@exemple.com"]
  }
}
```

> **Gmail** : utilisez un [mot de passe d'application](https://myaccount.google.com/apppasswords), pas votre mot de passe habituel.

### 4. Générer les certificats SSL

```bash
bash generate_ssl.sh
```

### 5. Configurer Icecast2

```bash
sudo apt install -y icecast2
```

Éditer `/etc/icecast2/icecast.xml` et définir le mot de passe source : `fmmonitor2026`

### 6. Créer le service systemd

```bash
sudo nano /etc/systemd/system/fm-monitor.service
```

```ini
[Unit]
Description=FM Monitor
After=network.target icecast2.service

[Service]
Type=simple
User=votre_user
WorkingDirectory=/home/votre_user/fm-monitor
ExecStart=/home/votre_user/fm-monitor/venv/bin/python3 app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable fm-monitor
sudo systemctl start fm-monitor
```

### 7. Accéder au dashboard

```
https://[IP-de-votre-appareil]:5000
```

---

## 📂 Structure du projet

```
fm-monitor/
├── app.py              # Application Flask (routes, API)
├── monitor.py          # Moteur de monitoring RTL-SDR / RDS
├── email_alert.py      # Alertes email
├── auth.py             # Authentification
├── database.py         # Base SQLite (historique, alertes)
├── requirements.txt    # Dépendances Python
├── install.sh          # Script d'installation
├── config.json.example # Exemple de configuration
├── templates/
│   ├── index.html      # Dashboard principal
│   ├── config.html     # Page configuration
│   ├── stats.html      # Statistiques
│   ├── about.html      # Documentation FM/RDS
│   └── login.html      # Authentification
└── static/             # Assets CSS/JS
```

---

## 📖 Documentation

La page **À propos** intégrée dans l'interface explique :
- Le fonctionnement de la diffusion FM et du signal MPX
- Le système RDS (PS, RT, PI Code)
- Radio Browser et la résolution de logo
- Les dongles compatibles et leur installation

---

## 🛠️ Dépannage

### Le dongle n'est pas détecté

```bash
lsusb | grep -i realtek
rtl_test -t
```

Si `usb_claim_interface error -6` : le driver noyau a pris le contrôle. Appliquer le blacklist (voir section V4 ci-dessus).

### Pas de signal audio

Vérifier la fréquence et le gain dans `config.json`. Tester manuellement :

```bash
rtl_fm -f 98.5M -M wbfm -s 171k -r 44100 - | aplay -r 44100 -f S16_LE
```

### Les emails ne partent pas

1. Vérifier la config SMTP dans l'interface Configuration
2. Utiliser le bouton **Test Email** dans le dashboard
3. Consulter les logs : `journalctl -u fm-monitor -f`

### Le RDS n'apparaît pas

Le RT complet prend ~20-60 secondes à se stabiliser. Vérifier que `redsea` est installé :

```bash
which redsea
tail -f /tmp/rds_output.json
```

---

## 🗺️ Roadmap

- [x] v0.3.1 — Streaming Icecast2 professionnel, SSL, CSRF
- [x] v0.3.2 — Open source, RTL-SDR Blog V4, logo Radio Browser, page documentation
- [ ] v0.3.3 — Monitoring RDS (présence, stabilité), script install automatique
- [ ] v0.4.x — Support TEF6686 (Headless TEF Lite) — démodulation stéréo hardware, RDS natif

---

## 📄 Licence

MIT — libre d'utilisation, modification et distribution.

---

## 🙏 Crédits

- [RTL-SDR Blog](https://www.rtl-sdr.com) — drivers et matériel
- [redsea](https://github.com/windytan/redsea) — décodeur RDS
- [Radio Browser](https://www.radio-browser.info) — base de données stations
- [Icecast2](https://icecast.org) — serveur de streaming
