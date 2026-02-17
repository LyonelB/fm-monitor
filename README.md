# 📻 Système de Surveillance FM Radio

Système de surveillance et de diffusion en streaming d'une radio FM utilisant une clé RTL-SDR, avec alertes email automatiques en cas de panne.

## 🎯 Fonctionnalités

- ✅ **Réception FM** via clé RTL-SDR
- 🌐 **Streaming web** - Écouter la radio depuis n'importe où
- 📧 **Alertes email** automatiques en cas de panne
- 📊 **Interface web** moderne et responsive
- 📈 **Monitoring en temps réel** du niveau audio
- 🔄 **Détection automatique** des pannes (silence, perte de signal)
- 📱 **Compatible** Raspberry Pi et mini-PC Linux
- ⚡ **Service systemd** pour démarrage automatique

## 📋 Prérequis

### Matériel
- Raspberry Pi (3/4/5) ou mini-PC sous Linux
- Clé RTL-SDR (RTL2832U)
- Connexion Internet (pour les alertes email)
- Antenne FM adaptée

### Logiciels
- Système d'exploitation : Raspberry Pi OS, Ubuntu, Debian
- Python 3.7+
- rtl-sdr
- sox

## 🚀 Installation

### 1. Cloner ou télécharger le projet

```bash
git clone https://github.com/votre-repo/fm-monitor.git
cd fm-monitor
```

Ou décompresser l'archive téléchargée.

### 2. Brancher la clé RTL-SDR

Connecter la clé RTL-SDR à un port USB de votre appareil.

### 3. Exécuter le script d'installation

```bash
sudo ./install.sh
```

Ce script va :
- Installer toutes les dépendances système
- Configurer Python et l'environnement virtuel
- Configurer les règles udev pour RTL-SDR
- Créer le service systemd

### 4. Tester la clé RTL-SDR

```bash
rtl_test
```

Vous devriez voir des informations sur votre clé. Appuyez sur `Ctrl+C` pour arrêter.

## ⚙️ Configuration

### Éditer config.json

Ouvrir le fichier `config.json` et modifier les paramètres :

#### 1. Fréquence FM

```json
"rtl_sdr": {
  "frequency": "98.5M",  // Fréquence de votre radio (format: XXX.XM)
  "sample_rate": "200k",
  "device_index": 0,
  "gain": "auto",
  "ppm_error": 0
}
```

#### 2. Paramètres audio

```json
"audio": {
  "output_rate": "44100",
  "channels": 1,
  "silence_threshold": -50,      // Niveau en dB considéré comme silence
  "silence_duration": 30,        // Durée de silence avant alerte (secondes)
  "check_interval": 5            // Intervalle de vérification (secondes)
}
```

#### 3. Configuration email

Pour Gmail, vous devez créer un **mot de passe d'application** :
1. Aller sur https://myaccount.google.com/security
2. Activer la validation en deux étapes
3. Créer un mot de passe d'application
4. Utiliser ce mot de passe dans la configuration

```json
"email": {
  "enabled": true,
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "use_tls": true,
  "sender_email": "votre.email@gmail.com",
  "sender_password": "votre_mot_de_passe_application",
  "recipient_emails": ["destinataire@example.com"],
  "cooldown_minutes": 30  // Délai minimum entre deux alertes
}
```

**Autres fournisseurs d'email :**

- **Outlook/Hotmail** : smtp.office365.com, port 587
- **Yahoo** : smtp.mail.yahoo.com, port 587
- **OVH** : ssl0.ovh.net, port 587

#### 4. Informations de la station

```json
"station": {
  "name": "Ma Radio FM",
  "frequency_display": "98.5 MHz"
}
```

## 🎬 Démarrage

### Démarrage manuel (pour tester)

```bash
source venv/bin/activate
python3 app.py
```

Accéder à l'interface web : `http://[IP-de-votre-appareil]:5000`

### Démarrage avec systemd (recommandé)

```bash
# Démarrer le service
sudo systemctl start fm-monitor

# Activer le démarrage automatique au boot
sudo systemctl enable fm-monitor

# Vérifier le statut
sudo systemctl status fm-monitor

# Voir les logs en temps réel
sudo journalctl -u fm-monitor -f
```

### Commandes utiles

```bash
# Arrêter le service
sudo systemctl stop fm-monitor

# Redémarrer le service
sudo systemctl restart fm-monitor

# Désactiver le démarrage automatique
sudo systemctl disable fm-monitor

# Recharger la configuration après modification
sudo systemctl daemon-reload
sudo systemctl restart fm-monitor
```

## 🌐 Interface Web

### Accès

Une fois le service démarré, accéder à l'interface web :

```
http://[IP-de-votre-appareil]:5000
```

Pour trouver l'IP de votre appareil :

```bash
hostname -I
```

### Fonctionnalités de l'interface

1. **Lecteur Audio** - Écouter le stream en direct
2. **État du Signal** - Visualisation en temps réel
3. **Niveau Audio** - Barre de niveau avec valeur en dB
4. **Statistiques** - Uptime, alertes, etc.
5. **Contrôles** - Démarrer/Arrêter/Redémarrer le monitoring
6. **Test Email** - Vérifier la configuration des alertes

## 📧 Système d'Alertes

### Types d'alertes envoyées

1. **Perte du signal FM** - Silence prolongé détecté
2. **Rétablissement du signal** - Le signal est revenu

### Exemple d'email d'alerte

```
⚠️ ALERTE - Ma Radio FM - Perte du signal FM

Station: Ma Radio FM
Fréquence: 98.5 MHz
Type d'alerte: Perte du signal FM
Date et heure: 09/02/2026 14:30:15

Détails:
Silence détecté depuis 35 secondes.
Niveau audio: -62.3 dB (seuil: -50 dB)
```

### Cooldown

Un système de cooldown empêche l'envoi d'alertes trop fréquentes. Par défaut, un délai de 30 minutes est appliqué entre deux alertes.

## 🔧 Dépannage

### La clé RTL-SDR n'est pas détectée

```bash
# Vérifier que la clé est reconnue
lsusb | grep RTL

# Tester la clé
rtl_test

# Vérifier les permissions
ls -la /dev/bus/usb/
```

### Aucun son dans le stream

1. Vérifier la fréquence dans `config.json`
2. Tester la réception manuellement :

```bash
rtl_fm -f 98.5M -M fm -s 200k -r 48k - | aplay -r 48k -f S16_LE
```

3. Vérifier l'antenne

### Les emails ne sont pas envoyés

1. Vérifier les logs :

```bash
sudo journalctl -u fm-monitor -f
```

2. Tester l'envoi d'email via l'interface web (bouton "Test Email")

3. Vérifier la configuration SMTP dans `config.json`

4. Pour Gmail, vérifier que vous utilisez bien un mot de passe d'application

### Le service ne démarre pas

```bash
# Voir les erreurs
sudo journalctl -u fm-monitor -n 50

# Vérifier la configuration
sudo systemctl status fm-monitor

# Tester manuellement
cd /chemin/vers/fm-monitor
source venv/bin/activate
python3 app.py
```

### Niveau audio toujours trop faible

Ajuster le gain de la clé RTL-SDR dans `config.json` :

```json
"gain": "40"  // Valeur entre 0 et 50
```

Ou laisser en mode automatique :

```json
"gain": "auto"
```

## 📊 Logs

### Localisation

Les logs sont stockés dans :
- Fichier : `logs/fm-monitor.log`
- Systemd : `journalctl -u fm-monitor`

### Voir les logs en direct

```bash
# Logs du service
sudo journalctl -u fm-monitor -f

# Logs du fichier
tail -f logs/fm-monitor.log
```

## 🔒 Sécurité

### Accès distant

Pour accéder au système depuis Internet :

1. **Configuration du routeur** - Rediriger le port 5000 vers l'IP locale
2. **Pare-feu** - Autoriser le port 5000
3. **HTTPS** - Recommandé pour un accès sécurisé (utiliser nginx avec Let's Encrypt)

### Mot de passe email

**⚠️ IMPORTANT** : Ne jamais partager ou commiter le fichier `config.json` contenant vos identifiants email !

Ajouter au `.gitignore` :

```
config.json
logs/
*.log
```

## 📱 Accès Mobile

L'interface web est responsive et fonctionne parfaitement sur smartphone et tablette.

## 🔄 Mise à jour

Pour mettre à jour le système :

```bash
# Arrêter le service
sudo systemctl stop fm-monitor

# Mettre à jour les fichiers
git pull  # ou télécharger la nouvelle version

# Mettre à jour les dépendances Python
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Redémarrer le service
sudo systemctl start fm-monitor
```

## 🛠️ Configuration Avancée

### Changer le port web

Dans `config.json` :

```json
"web": {
  "host": "0.0.0.0",
  "port": 8080  // Nouveau port
}
```

Ne pas oublier de redémarrer le service.

### Utiliser plusieurs clés RTL-SDR

Modifier `device_index` dans `config.json` :

```json
"device_index": 1  // Deuxième clé
```

### Ajuster la sensibilité de détection

```json
"silence_threshold": -40,  // Plus sensible (détecte plus facilement)
"silence_duration": 60     // Attend 60 secondes avant alerte
```

## 📄 Structure du Projet

```
fm-monitor/
├── app.py              # Application Flask principale
├── monitor.py          # Module de surveillance FM
├── email_alert.py      # Gestion des alertes email
├── config.json         # Configuration
├── requirements.txt    # Dépendances Python
├── install.sh          # Script d'installation
├── README.md           # Documentation
├── templates/
│   └── index.html      # Interface web
├── logs/               # Fichiers de logs
└── venv/               # Environnement virtuel Python
```

## 🤝 Support

Pour toute question ou problème :

1. Vérifier les logs
2. Consulter la section Dépannage
3. Ouvrir une issue sur GitHub

## 📜 Licence

Ce projet est sous licence MIT.

## 🙏 Remerciements

- Projet RTL-SDR
- Communauté Raspberry Pi
- Flask Framework

---

**Développé avec ❤️ pour la surveillance radio FM**
