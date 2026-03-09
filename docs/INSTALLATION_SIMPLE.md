# 🚀 Installation FM Monitor - Guide Simple

## 📋 Prérequis

- **Raspberry Pi** (3, 4, ou 5)
- **Raspberry Pi OS** (anciennement Raspbian)
- **Dongle RTL-SDR** (RTL2832U)
- **Connexion Internet**

---

## ⚡ Installation en une commande

```bash
curl -sSL https://raw.githubusercontent.com/LyonelB/fm-monitor/main/install.sh | bash
```

**C'est tout !** Le script fait tout automatiquement. ⏱️ **Durée : 5-10 minutes**

---

## 📝 Ce que le script fait

1. ✅ Vérifie le système (Raspberry Pi OS)
2. ✅ Installe les dépendances (RTL-SDR, Sox, Python, etc.)
3. ✅ Clone FM Monitor depuis GitHub
4. ✅ Crée l'environnement virtuel Python
5. ✅ Installe les packages Python (Flask, Numpy, etc.)
6. ✅ Génère le certificat SSL (HTTPS)
7. ✅ Configure le service systemd
8. ✅ Configure les permissions RTL-SDR
9. ✅ Crée la configuration par défaut
10. ✅ Démarre FM Monitor

---

## 🎯 Après l'installation

### Accéder à l'interface

```
https://IP_DU_RASPBERRY:5000
```

**Exemple** : `https://192.168.1.185:5000`

**Note** : Le navigateur affichera un avertissement (certificat auto-signé). C'est normal !
→ Cliquez sur "Avancé" puis "Continuer"

---

### Identifiants par défaut

```
Username: admin
Password: password
```

**⚠️ CHANGEZ LE MOT DE PASSE IMMÉDIATEMENT !**

→ Allez dans **Configuration** → **Gestion des identifiants**

---

## 🔧 Commandes utiles

### Gérer le service

```bash
# Démarrer
sudo systemctl start fm-monitor

# Arrêter
sudo systemctl stop fm-monitor

# Redémarrer
sudo systemctl restart fm-monitor

# Statut
sudo systemctl status fm-monitor

# Activer au démarrage
sudo systemctl enable fm-monitor

# Désactiver au démarrage
sudo systemctl disable fm-monitor
```

### Voir les logs

```bash
# Logs en temps réel
sudo journalctl -u fm-monitor -f

# 100 dernières lignes
sudo journalctl -u fm-monitor -n 100

# Logs depuis aujourd'hui
sudo journalctl -u fm-monitor --since today
```

### Mettre à jour

```bash
cd ~/fm-monitor
git pull
sudo systemctl restart fm-monitor
```

---

## 📍 Emplacements importants

```
~/fm-monitor/          # Répertoire principal
├── app.py            # Application Flask
├── monitor.py        # Logique de monitoring
├── auth.py           # Authentification
├── config.json       # Configuration
├── .env              # Secret key
├── cert.pem          # Certificat SSL
├── key.pem           # Clé privée SSL
├── templates/        # Pages HTML
└── venv/             # Environnement Python
```

---

## 🛠️ Configuration

### Modifier la fréquence

1. Allez sur `https://IP:5000/config`
2. Changez la **Fréquence de monitoring**
3. Cliquez sur **Enregistrer**

### Configurer les alertes email

1. Allez sur `https://IP:5000/config`
2. Remplissez :
   - Email expéditeur (Gmail conseillé)
   - Mot de passe d'application Gmail
   - Emails destinataires
3. Cliquez sur **Tester l'email**
4. Si OK, cliquez sur **Enregistrer**

**Pour Gmail** : Utilisez un [mot de passe d'application](https://support.google.com/accounts/answer/185833)

---

## 🐛 Dépannage

### Le service ne démarre pas

```bash
# Voir les erreurs
sudo journalctl -u fm-monitor -n 50

# Vérifier les permissions
ls -la ~/fm-monitor/

# Tester manuellement
cd ~/fm-monitor
source venv/bin/activate
python3 app.py
```

---

### RTL-SDR non détecté

```bash
# Vérifier que le dongle est branché
lsusb | grep RTL

# Tester RTL-SDR
rtl_test -t

# Vérifier les permissions
groups  # Devrait contenir 'plugdev'

# Si absent, ajouter et redémarrer
sudo usermod -a -G plugdev $USER
sudo reboot
```

---

### Erreur "Address already in use"

```bash
# Vérifier quel processus utilise le port 5000
sudo lsof -i :5000

# Arrêter l'ancien processus
sudo systemctl stop fm-monitor

# Redémarrer
sudo systemctl start fm-monitor
```

---

### Certificat SSL invalide

**C'est normal !** Le certificat est auto-signé.

**Dans le navigateur** :
1. Cliquez sur "Avancé"
2. Cliquez sur "Continuer vers le site"
3. ✅ Connexion sécurisée établie

---

## 🔄 Désinstallation

```bash
# Arrêter le service
sudo systemctl stop fm-monitor
sudo systemctl disable fm-monitor

# Supprimer le service
sudo rm /etc/systemd/system/fm-monitor.service
sudo systemctl daemon-reload

# Supprimer les fichiers
rm -rf ~/fm-monitor

# (Optionnel) Supprimer les paquets
sudo apt remove rtl-sdr sox lame
```

---

## 📞 Support

- **Documentation** : [GitHub Wiki](https://github.com/LyonelB/fm-monitor/wiki)
- **Issues** : [GitHub Issues](https://github.com/LyonelB/fm-monitor/issues)

---

## ✨ Installation réussie !

Vous avez maintenant :
- ✅ FM Monitor installé et fonctionnel
- ✅ Service systemd configuré
- ✅ Certificat SSL (HTTPS)
- ✅ Démarrage automatique au boot

**Profitez de votre monitoring FM !** 🎉📻
