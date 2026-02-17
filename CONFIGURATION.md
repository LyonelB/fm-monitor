# Configuration rapide - Système de surveillance FM

Ce guide vous aide à configurer rapidement votre système.

## 🎯 Configuration minimale en 5 étapes

### 1. Fréquence de votre radio

Modifier dans `config.json` :
```json
"frequency": "98.5M"
```

Remplacer `98.5` par la fréquence de votre radio (ex: 101.2M, 89.7M, etc.)

### 2. Configuration email pour Gmail

**Étapes pour Gmail :**

a) Activer la validation en deux étapes :
   - Aller sur https://myaccount.google.com/security
   - Activer "Validation en deux étapes"

b) Créer un mot de passe d'application :
   - Aller sur https://myaccount.google.com/apppasswords
   - Sélectionner "Autre (nom personnalisé)"
   - Entrer "FM Monitor"
   - Cliquer sur "Générer"
   - **Copier le mot de passe affiché** (16 caractères sans espaces)

c) Modifier `config.json` :
```json
"email": {
  "enabled": true,
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "use_tls": true,
  "sender_email": "votre.email@gmail.com",
  "sender_password": "le-mot-de-passe-généré",
  "recipient_emails": ["destinataire@example.com"],
  "cooldown_minutes": 30
}
```

### 3. Nom de votre station

```json
"station": {
  "name": "Radio Locale 98.5",
  "frequency_display": "98.5 MHz"
}
```

### 4. Seuils de détection (optionnel)

Par défaut, le système envoie une alerte si :
- Le niveau audio est inférieur à -50 dB
- Le silence dure plus de 30 secondes

Pour ajuster :
```json
"audio": {
  "silence_threshold": -45,    // Plus sensible
  "silence_duration": 60       // Attendre 1 minute
}
```

### 5. Gain de la clé RTL-SDR (optionnel)

Si le signal est trop faible ou trop fort :
```json
"rtl_sdr": {
  "gain": "auto"  // ou une valeur entre 0 et 50
}
```

## 📧 Autres fournisseurs d'email

### Outlook / Hotmail
```json
"smtp_server": "smtp.office365.com",
"smtp_port": 587,
"use_tls": true
```

### Yahoo
```json
"smtp_server": "smtp.mail.yahoo.com",
"smtp_port": 587,
"use_tls": true
```

### OVH
```json
"smtp_server": "ssl0.ovh.net",
"smtp_port": 587,
"use_tls": true
```

## ✅ Vérifier la configuration

Après avoir modifié `config.json`, tester :

```bash
# Démarrer l'application
./start.sh

# Ou avec systemd
sudo systemctl restart fm-monitor
```

Puis aller sur l'interface web et cliquer sur "Test Email" pour vérifier que les emails fonctionnent.

## ⚠️ Important

- Ne JAMAIS partager votre fichier `config.json` (il contient vos mots de passe)
- Utiliser toujours un mot de passe d'application (pas votre mot de passe principal)
- Les mots de passe d'application Gmail sont des codes de 16 caractères sans espaces

## 🆘 Problèmes fréquents

### "Erreur d'authentification SMTP"
→ Vérifier que vous utilisez un mot de passe d'application, pas votre mot de passe Gmail principal

### "Connection refused"
→ Vérifier le port SMTP (587 pour la plupart des fournisseurs)

### Pas de son dans le stream
→ Vérifier la fréquence dans config.json
→ Tester manuellement : `rtl_fm -f 98.5M -M fm -s 200k -r 48k - | aplay -r 48k -f S16_LE`
