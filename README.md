# 📻 FM Monitor

Système de surveillance de signal FM avec RTL-SDR sur Raspberry Pi ou mini-PC Debian.

Surveille en continu une fréquence FM, affiche le niveau audio en temps réel, lit les données RDS, envoie des alertes email en cas de perte de signal, et propose un player audio intégré.

---

## ✨ Fonctionnalités

- **VU-mètre temps réel** — 200 barres, précision 0.01 dBFS, via Server-Sent Events
- **Player audio intégré** — écoute du flux FM directement dans le navigateur
- **RDS** — lecture du Program Service (PS) et RadioText (RT), mode auto (toutes les 10s) ou désactivé
- **Alertes email** — notification automatique en cas de perte de signal (seuil et durée configurables)
- **Historique 24h** — graphique du niveau audio, stocké en SQLite
- **Watchdog** — relance automatique de rtl_fm en cas de crash
- **Panneau de contrôle** — activation/désactivation individuelle de chaque service depuis le dashboard
- **Interface web** — dashboard Material Design, authentification, responsive

---

## 🖥️ Compatibilité

| Matériel | Statut |
|---|---|
| Raspberry Pi 3B+ | ✅ Testé |
| Raspberry Pi 4 | ✅ Compatible |
| Mini-PC Debian x86_64 | ✅ Compatible |

**OS recommandé :** Debian 12 (Bookworm) ou Raspberry Pi OS 64-bit

---

## 📦 Prérequis matériel

- Clé RTL-SDR (RTL2832U)
- Antenne FM adaptée (connecteur SMA)
- Connexion réseau (Ethernet ou WiFi)

---

## 🚀 Installation rapide

```bash
git clone https://github.com/VOTRE_COMPTE/fm-monitor.git
cd fm-monitor
chmod +x install.sh
sudo ./install.sh
```

L'installateur effectue automatiquement :
1. Mise à jour du système
2. Installation des dépendances système (`rtl-sdr`, `sox`, `redsea`, `python3-venv`)
3. Création de l'environnement virtuel Python
4. Installation des dépendances Python
5. Création du fichier de configuration depuis le template
6. Installation et démarrage du service systemd

---

## ⚙️ Configuration

```bash
nano config.json
```

### Paramètres principaux

```json
{
  "station": {
    "name": "Nom de la station",
    "frequency": "88.6M"
  },
  "rtl_sdr": {
    "frequency": "88.6M",
    "sample_rate": "171k",
    "gain": "45",
    "ppm_error": "0"
  },
  "audio": {
    "output_rate": "44100",
    "silence_threshold": -30.0,
    "silence_duration": 15
  },
  "email": {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "votre@gmail.com",
    "sender_password": "votre_mot_de_passe_app",
    "recipient_emails": ["destinataire@exemple.com"],
    "cooldown_minutes": 30
  }
}
```

### Paramètres RTL-SDR

| Paramètre | Description | Valeur exemple |
|---|---|---|
| `frequency` | Fréquence FM à surveiller | `88.6M` |
| `gain` | Gain du tuner (0–49.6 ou `auto`) | `45` |
| `ppm_error` | Correction d'erreur PPM de la clé | `0` |
| `sample_rate` | Taux d'échantillonnage (**171k requis pour RDS**) | `171k` |

### Email avec Gmail

Pour utiliser Gmail, créez un **mot de passe d'application** :
1. Activez la validation en 2 étapes sur votre compte Google
2. Allez dans Compte Google → Sécurité → Mots de passe des applications
3. Générez un mot de passe pour "Autre (nom personnalisé)"
4. Utilisez ce mot de passe dans `sender_password`

---

## 🌐 Accès à l'interface

Une fois installé, ouvrez dans votre navigateur :

```
http://IP_DE_LA_MACHINE:5000
```

**Identifiants par défaut :**
- Login : `admin`
- Mot de passe : `admin123`

> ⚠️ Changez le mot de passe dès la première connexion dans `auth.py` (ligne `USERS`).

---

## 🎛️ Panneau de contrôle des services

Depuis le dashboard, activez/désactivez chaque service individuellement :

| Service | Description | Recommandé |
|---|---|---|
| **VU-mètre** | Calcul RMS et affichage temps réel | Selon besoin |
| **Player Audio** | Streaming MP3 dans le navigateur | Selon besoin |
| **Watchdog** | Relance automatique rtl_fm si crash | ✅ Toujours |
| **RDS Auto** | Lecture PS/RT automatique toutes les 10s | Optionnel |
| **Historique 24h** | Enregistrement SQLite des niveaux | Recommandé |

> 💡 Sur Raspberry Pi 3, activez les services selon vos besoins. VU-mètre + Player Audio + Historique fonctionnent bien ensemble.

---

## 📁 Structure du projet

```
fm-monitor/
├── app.py                  # Serveur Flask (routes API, SSE, streaming audio)
├── monitor.py              # Moteur de surveillance (RTL-SDR, RMS, RDS, watchdog)
├── database.py             # Gestion SQLite (niveaux audio, historique alertes)
├── email_alert.py          # Envoi d'alertes email SMTP
├── auth.py                 # Authentification sessions Flask
├── config.json             # Configuration active (à créer depuis .example)
├── config.json.example     # Template de configuration (sans données sensibles)
├── requirements.txt        # Dépendances Python
├── install.sh              # Script d'installation automatique
├── fm-monitor.service      # Fichier service systemd
└── templates/
    ├── index.html          # Dashboard principal avec panneau de contrôle
    ├── config.html         # Page de configuration
    ├── stats.html          # Page statistiques et historique alertes
    └── login.html          # Page de connexion
```

---

## 🔧 Gestion du service

```bash
sudo systemctl start fm-monitor      # Démarrer
sudo systemctl stop fm-monitor       # Arrêter
sudo systemctl restart fm-monitor    # Redémarrer
sudo systemctl status fm-monitor     # Statut
sudo journalctl -u fm-monitor -f     # Logs en temps réel
```

---

## 🔍 Dépannage

**RTL-SDR non détecté**
```bash
lsusb | grep RTL
rtl_test -t
```

**Pas de son dans le player**
```bash
ls -la /tmp/fm_stream.mp3
# Si absent, vérifiez les logs
sudo journalctl -u fm-monitor -f
```

**Erreur "usb_open error" / clé déjà utilisée**
```bash
sudo pkill -9 rtl_fm
sudo systemctl restart fm-monitor
```

**VU-mètre qui se fige**
Désactivez le service **Historique 24h** et/ou **RDS Auto** depuis le dashboard.

**Blacklist du module DVB par défaut**
Sur certains systèmes, le module DVB entre en conflit avec rtl-sdr :
```bash
echo 'blacklist dvb_usb_rtl28xxu' | sudo tee /etc/modprobe.d/blacklist-rtl.conf
sudo reboot
```

---

## 📜 Licence

MIT License — libre d'utilisation, de modification et de distribution.

---

## 🙏 Crédits et dépendances

- [rtl-sdr](https://osmocom.org/projects/rtl-sdr) — driver RTL-SDR
- [redsea](https://github.com/windytan/redsea) — décodeur RDS
- [sox](http://sox.sourceforge.net/) — traitement et encodage audio
- [Flask](https://flask.palletsprojects.com/) — serveur web Python
- [numpy](https://numpy.org/) — calcul RMS
- [Material Dashboard](https://www.creative-tim.com/product/material-dashboard) — interface UI
