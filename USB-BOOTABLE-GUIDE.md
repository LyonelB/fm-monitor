# 🔌 Clé USB Bootable - Système de Surveillance FM

Guide complet pour créer une clé USB bootable qui transforme n'importe quel PC en système de surveillance FM.

## 📋 Prérequis

### Matériel nécessaire
- **Clé USB** de minimum 16 GB (32 GB recommandé)
- **PC** pour créer la clé bootable
- **Clé RTL-SDR** pour la réception FM
- **PC cible** où vous allez booter (n'importe quel PC x86/64)

### Logiciels nécessaires
- **Rufus** (Windows) : https://rufus.ie
- **Balena Etcher** (Windows/Mac/Linux) : https://www.balena.io/etcher
- Ou **dd** (Linux)

## 🚀 Étape 1 : Télécharger Ubuntu Server

1. Télécharger **Ubuntu Server 22.04 LTS** ou **24.04 LTS**
   - Lien : https://ubuntu.com/download/server
   - Choisir la version **64-bit PC (AMD64)**
   - Taille : ~2.5 GB

**Pourquoi Ubuntu Server ?**
- ✅ Léger (pas d'interface graphique inutile)
- ✅ Stable et bien supporté
- ✅ Compatible avec tous les PC modernes
- ✅ Accès SSH facile pour administration à distance

## 🔧 Étape 2 : Créer la clé USB bootable

### Sous Windows (avec Rufus)

1. **Brancher la clé USB** (⚠️ tout sera effacé !)
2. **Lancer Rufus**
3. Configuration :
   - **Périphérique** : Sélectionner votre clé USB
   - **Type de démarrage** : Image disque (sélectionner l'ISO Ubuntu)
   - **Schéma de partition** : GPT
   - **Système de destination** : UEFI
   - **Système de fichiers** : FAT32
   - **Taille d'unité d'allocation** : 4096
4. Cliquer sur **DÉMARRER**
5. Si demandé, choisir **Mode ISO** (recommandé)
6. Attendre la fin (5-10 minutes)

### Sous Linux (avec dd)

```bash
# Identifier la clé USB
lsblk

# Démonter la clé si montée
sudo umount /dev/sdX*

# Créer la clé bootable (remplacer sdX par votre clé)
sudo dd if=ubuntu-22.04-live-server-amd64.iso of=/dev/sdX bs=4M status=progress
sudo sync
```

### Sous Mac (avec Balena Etcher)

1. Lancer Balena Etcher
2. **Flash from file** : Sélectionner l'ISO Ubuntu
3. **Select target** : Choisir la clé USB
4. **Flash!**

## 💾 Étape 3 : Installer Ubuntu sur la clé USB

### Démarrage depuis la clé USB

1. **Brancher la clé USB** sur le PC cible
2. **Redémarrer le PC**
3. **Appuyer sur la touche de boot** pendant le démarrage :
   - **Dell** : F12
   - **HP** : F9 ou Esc
   - **Lenovo** : F12 ou F8
   - **Asus** : F8 ou Esc
   - **Acer** : F12
   - **MSI** : F11
   - **Gigabyte** : F12
4. **Sélectionner la clé USB** dans le menu de boot

### Installation d'Ubuntu

1. **Langue** : Choisir votre langue
2. **Clavier** : Choisir la disposition du clavier
3. **Type d'installation** : Ubuntu Server
4. **Configuration réseau** : 
   - Si câble Ethernet : configuration automatique
   - Si WiFi : configurer manuellement
5. **Proxy** : Laisser vide (sauf si nécessaire)
6. **Miroir** : Laisser par défaut
7. **Configuration du stockage** : ⚠️ **IMPORTANT**
   - Choisir **Custom storage layout**
   - Sélectionner **UNIQUEMENT la clé USB** (pas le disque dur du PC !)
   - Vérifier la taille (doit correspondre à votre clé USB)
   - Confirmer
8. **Profil utilisateur** :
   - **Nom** : fmradio
   - **Nom du serveur** : fm-monitor
   - **Nom d'utilisateur** : fmradio
   - **Mot de passe** : (choisir un mot de passe fort)
9. **SSH** : ✅ Cocher "Install OpenSSH server"
10. **Featured Server Snaps** : Ne rien sélectionner
11. **Installation** : Confirmer et attendre (10-20 minutes)
12. **Redémarrer** : Retirer la clé USB quand demandé... puis **la remettre immédiatement** !

## 📦 Étape 4 : Installer le système de surveillance FM

### Se connecter au système

Après le redémarrage, vous verrez un écran de login :
```
fm-monitor login: fmradio
Password: [votre mot de passe]
```

### Transférer les fichiers

#### Option A : Via clé USB (plus simple)

1. Sur votre PC de travail :
   - Copier le fichier `fm-monitor.tar.gz` sur une **autre clé USB**
   - Copier aussi le script `usb-autoinstall.sh` (voir ci-dessous)

2. Sur le système FM (après boot sur la clé principale) :
```bash
# Brancher la clé USB avec les fichiers
# Identifier la clé
lsblk

# Monter la clé (exemple si c'est sdb1)
sudo mkdir -p /mnt/usb
sudo mount /dev/sdb1 /mnt/usb

# Copier les fichiers
cp /mnt/usb/fm-monitor.tar.gz ~/
cp /mnt/usb/usb-autoinstall.sh ~/

# Démonter
sudo umount /mnt/usb

# Extraire
tar -xzf fm-monitor.tar.gz
cd fm-monitor

# Lancer l'installation
sudo ./install.sh
```

#### Option B : Via réseau (si connexion Internet)

```bash
# Si vous avez mis le projet sur un serveur web ou GitHub
wget http://votre-serveur.com/fm-monitor.tar.gz
# Ou
git clone https://github.com/votre-repo/fm-monitor.git

cd fm-monitor
sudo ./install.sh
```

#### Option C : Via SSH depuis un autre PC

```bash
# Sur votre PC de travail
scp fm-monitor.tar.gz fmradio@[IP-du-systeme-FM]:~/

# Sur le système FM
tar -xzf fm-monitor.tar.gz
cd fm-monitor
sudo ./install.sh
```

## ⚙️ Étape 5 : Configuration

### Éditer la configuration

```bash
cd fm-monitor
nano config.json
```

Modifier au minimum :
- **frequency** : La fréquence de votre radio
- **email** : Vos paramètres SMTP et destinataires
- **station.name** : Le nom de votre station

Sauvegarder : `Ctrl+O` puis `Entrée`, Quitter : `Ctrl+X`

### Démarrer le service

```bash
sudo systemctl start fm-monitor
sudo systemctl enable fm-monitor
```

### Vérifier que ça fonctionne

```bash
# Voir le statut
sudo systemctl status fm-monitor

# Voir les logs
sudo journalctl -u fm-monitor -f

# Trouver l'IP pour accéder à l'interface web
hostname -I
```

Accéder à l'interface web : `http://[IP-affichée]:5000`

## 🎯 Utilisation quotidienne

### Démarrer le système

1. **Brancher** :
   - La clé USB bootable
   - La clé RTL-SDR
   - Le câble réseau (ou configurer WiFi)
2. **Allumer le PC**
3. **Sélectionner** la clé USB dans le menu de boot
4. **Attendre** ~1 minute (démarrage automatique)
5. **Accéder** à l'interface web depuis n'importe quel appareil sur le réseau

### Trouver l'IP du système

#### Depuis le PC lui-même
```bash
# Se connecter en local
# Login: fmradio
# Password: [votre mot de passe]

hostname -I
```

#### Depuis un autre PC sur le réseau
```bash
# Scanner le réseau (Linux/Mac)
nmap -sn 192.168.1.0/24 | grep fm-monitor

# Ou utiliser un outil comme "Advanced IP Scanner" (Windows)
```

### Arrêter proprement

```bash
# Se connecter en SSH ou en local
sudo shutdown -h now
```

Attendre que le PC s'éteigne complètement avant de débrancher.

## 🔐 Sécurité et bonnes pratiques

### Accès SSH sécurisé

```bash
# Changer le mot de passe par défaut
passwd

# Désactiver le login root par SSH (déjà fait par défaut)
sudo nano /etc/ssh/sshd_config
# Vérifier: PermitRootLogin no
```

### Pare-feu

```bash
# Installer et configurer UFW
sudo apt install ufw
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 5000/tcp  # Interface web
sudo ufw enable
sudo ufw status
```

### Mises à jour

```bash
# Mettre à jour le système régulièrement
sudo apt update
sudo apt upgrade -y
```

## 🌐 Accès depuis Internet (optionnel)

Si vous voulez accéder à votre système depuis l'extérieur :

### Option 1 : Port forwarding sur votre box

1. Aller dans l'interface de votre box/routeur
2. Configurer une redirection de port :
   - **Port externe** : 8080 (par exemple)
   - **Port interne** : 5000
   - **IP interne** : IP du système FM
3. Accéder via : `http://[votre-IP-publique]:8080`

### Option 2 : Tunnel SSH (plus sécurisé)

```bash
# Depuis un PC distant
ssh -L 5000:localhost:5000 fmradio@[IP-publique-de-votre-box]

# Puis accéder via
http://localhost:5000
```

### Option 3 : VPN Tailscale (recommandé)

```bash
# Sur le système FM
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Sur vos autres appareils, installer Tailscale
# Accès direct et sécurisé sans ouvrir de ports
```

## 🛠️ Dépannage

### Le PC ne boot pas sur la clé USB

- Vérifier que le **Secure Boot** est désactivé dans le BIOS
- Vérifier que le **mode UEFI** est activé (pas Legacy)
- Essayer de recréer la clé USB bootable

### Pas de connexion réseau

```bash
# Vérifier les interfaces
ip a

# Si WiFi, configurer avec netplan
sudo nano /etc/netplan/00-installer-config.yaml
```

Exemple de configuration WiFi :
```yaml
network:
  version: 2
  wifis:
    wlan0:
      dhcp4: true
      access-points:
        "NomDuWiFi":
          password: "MotDePasseWiFi"
```

Appliquer :
```bash
sudo netplan apply
```

### La clé RTL-SDR n'est pas détectée

```bash
# Vérifier que la clé est vue par le système
lsusb | grep RTL

# Vérifier les drivers
rtl_test
```

### Le service ne démarre pas

```bash
# Voir les erreurs
sudo journalctl -u fm-monitor -n 100

# Tester manuellement
cd ~/fm-monitor
source venv/bin/activate
python3 app.py
```

## 📊 Performances et optimisations

### Pour un PC ancien/lent

Réduire la charge CPU :
```json
// Dans config.json
"audio": {
  "check_interval": 10,  // Au lieu de 5
  "output_rate": "22050" // Au lieu de 44100
}
```

### Désactiver les services inutiles

```bash
# Désactiver les services non nécessaires
sudo systemctl disable bluetooth
sudo systemctl disable cups
sudo systemctl disable avahi-daemon
```

## 💡 Astuces

### Démarrage automatique sans saisir de mot de passe

**⚠️ À n'utiliser QUE si le PC est dans un lieu sécurisé !**

```bash
sudo systemctl edit getty@tty1
```

Ajouter :
```ini
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin fmradio --noclear %I $TERM
```

### IP fixe

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

Exemple :
```yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 192.168.1.100/24
      gateway4: 192.168.1.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 8.8.4.4
```

### Surveiller plusieurs fréquences

Créer plusieurs instances avec différents ports et fréquences !

## 🎬 Récapitulatif - Démarrage rapide

1. ✅ Créer clé USB bootable Ubuntu
2. ✅ Installer Ubuntu sur la clé
3. ✅ Copier et installer fm-monitor
4. ✅ Configurer config.json
5. ✅ Démarrer le service
6. ✅ Accéder à http://[IP]:5000
7. 🎉 Profiter !

---

**La clé USB est maintenant portable et peut transformer n'importe quel PC en système de surveillance FM !** 🚀
