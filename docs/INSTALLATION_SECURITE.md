# 🔒 Guide d'Installation - Phase 1 : Sécurité

## ✨ Ce qui va être installé

- ✅ **Bcrypt** : Hashage sécurisé des mots de passe (remplace SHA-256)
- ✅ **Rate Limiting** : Protection contre les attaques par force brute
- ✅ **Secret Key** : Clé secrète sécurisée pour les sessions
- ✅ **Dotenv** : Gestion des variables d'environnement

---

## 📦 Étape 1 : Installation des dépendances

```bash
cd ~/fm-monitor

# Installer les nouvelles dépendances
pip install flask-bcrypt==1.0.1 Flask-Limiter==3.5.0 python-dotenv==1.0.0 --break-system-packages

# Vérifier l'installation
python3 -c "import flask_bcrypt; import flask_limiter; import dotenv; print('✅ Toutes les dépendances sont installées')"
```

**Temps estimé** : 2-3 minutes

---

## 🔑 Étape 2 : Créer la Secret Key

```bash
cd ~/fm-monitor

# Générer une clé secrète aléatoire
python3 -c "import secrets; print(secrets.token_hex(32))"
```

**Résultat** : Vous obtiendrez une clé comme :
```
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

**Copiez cette clé** (vous en aurez besoin à l'étape suivante)

---

## 📝 Étape 3 : Créer le fichier .env

```bash
cd ~/fm-monitor

# Créer le fichier .env
nano .env
```

**Contenu du fichier .env** :
```bash
# FM Monitor - Variables d'environnement
# ⚠️ NE JAMAIS COMMITER CE FICHIER DANS GIT

# Clé secrète pour les sessions Flask (collez la clé générée ci-dessus)
SECRET_KEY=COLLEZ_VOTRE_CLE_SECRETE_ICI

# Environnement Flask
FLASK_ENV=production
```

**Remplacez** `COLLEZ_VOTRE_CLE_SECRETE_ICI` par la clé générée à l'étape 2.

**Sauvegarder** : `Ctrl+O`, `Enter`, `Ctrl+X`

---

## 🔄 Étape 4 : Sauvegarder les fichiers actuels

```bash
cd ~/fm-monitor

# Sauvegarder l'ancien app.py
cp app.py app_backup_$(date +%Y%m%d).py

# Sauvegarder l'ancien auth.py (si existe)
cp auth.py auth_backup_$(date +%Y%m%d).py 2>/dev/null || echo "Pas de auth.py existant"

echo "✅ Sauvegardes créées"
```

---

## 📥 Étape 5 : Installer les nouveaux fichiers

```bash
cd ~/fm-monitor

# Copier les nouveaux fichiers
cp ~/Téléchargements/app_secure.py app.py
cp ~/Téléchargements/auth_secure.py auth.py
cp ~/Téléchargements/migrate_passwords.py .
chmod +x migrate_passwords.py

echo "✅ Nouveaux fichiers installés"
```

---

## 🔐 Étape 6 : Migrer les mots de passe vers Bcrypt

```bash
cd ~/fm-monitor

# Exécuter le script de migration
python3 migrate_passwords.py
```

**Résultat attendu** :
```
============================================================
Migration des mots de passe vers Bcrypt
============================================================

Fichier de configuration trouvé : /home/graffiti/fm-monitor/config.json

⚠️  Ancien hash SHA-256 détecté

Le mot de passe actuel utilise SHA-256 (non sécurisé).
Il doit être réinitialisé pour utiliser Bcrypt.

✅ Mot de passe réinitialisé

   Nouveau mot de passe temporaire : password

⚠️  CHANGEZ-LE IMMÉDIATEMENT via l'interface de configuration !
   (http://votre-ip:5000/config)

============================================================
Migration terminée
============================================================
```

**Important** : Le mot de passe a été réinitialisé à `password` pour des raisons de sécurité. Vous DEVEZ le changer via l'interface.

---

## 🚀 Étape 7 : Redémarrer le service

```bash
sudo systemctl restart fm-monitor

# Vérifier que le service a démarré
sudo systemctl status fm-monitor
```

**Résultat attendu** :
```
● fm-monitor.service - FM Monitor Service
   Active: active (running) since ...
```

**Vérifier les logs** :
```bash
sudo journalctl -u fm-monitor -n 50
```

**Vous devriez voir** :
- ✅ "Démarrage du serveur Flask sur 0.0.0.0:5000"
- ✅ Pas d'erreurs d'import

---

## ✅ Étape 8 : Tester la sécurité

### Test 1 : Connexion avec le nouveau système

```bash
# Accéder à l'interface
http://192.168.1.185:5000/login
```

**Identifiants** :
- Username : `admin` (ou votre ancien username)
- Password : `password`

**Résultat** :
- ✅ Connexion réussie
- ✅ Redirection vers le dashboard

---

### Test 2 : Changer le mot de passe

1. Aller sur http://192.168.1.185:5000/config
2. Scroller jusqu'à "Gestion des identifiants de connexion"
3. Remplir :
   - Nouveau mot de passe : `votre-nouveau-mot-de-passe-securise`
   - Confirmer : `votre-nouveau-mot-de-passe-securise`
4. Cliquer "Enregistrer"

**Résultat** :
- ✅ Configuration sauvegardée
- ✅ Se reconnecter avec le nouveau mot de passe

---

### Test 3 : Rate Limiting (protection force brute)

```bash
# Tenter 10 connexions rapides avec un mauvais mot de passe
for i in {1..10}; do
  curl -X POST http://192.168.1.185:5000/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"wrong"}' \
    -w "\nTentative $i: %{http_code}\n"
  sleep 0.5
done
```

**Résultat attendu** :
```
Tentative 1: 401
Tentative 2: 401
Tentative 3: 401
Tentative 4: 401
Tentative 5: 401
Tentative 6: 429  ← Rate limit activé !
Tentative 7: 429
Tentative 8: 429
Tentative 9: 429
Tentative 10: 429
```

**Code 429** = "Too Many Requests" = Protection active ✅

---

### Test 4 : Vérifier le hash Bcrypt

```bash
cd ~/fm-monitor

# Afficher le hash du mot de passe
cat config.json | grep -A2 '"auth"'
```

**Résultat attendu** :
```json
"auth": {
  "username": "admin",
  "password_hash": "$2b$12$abcd1234..."
}
```

**Le hash doit commencer par** `$2b$` ou `$2a$` (Bcrypt) ✅

---

## 📊 Récapitulatif de sécurité

### Avant (VULNÉRABLE)
- ❌ SHA-256 : Rapide à casser (force brute)
- ❌ Secret key hardcodée dans le code
- ❌ Pas de rate limiting
- ❌ Attaque par force brute possible

### Après (SÉCURISÉ)
- ✅ **Bcrypt** : Très lent = résistant au force brute
- ✅ **Secret key** unique et sécurisée (.env)
- ✅ **Rate limiting** : Max 5 tentatives/minute
- ✅ **Logs** de toutes les tentatives de connexion

---

## 🛡️ Niveau de sécurité

**Score avant** : 2/10 ⚠️  
**Score après** : 7/10 ✅

**Reste à faire** (Phase 2) :
- HTTPS/SSL (chiffrement des communications)
- CSRF Protection (sécurité des formulaires)

---

## ⚠️ Important

1. **Changez le mot de passe par défaut** immédiatement
2. **Ne partagez jamais le fichier .env**
3. **Ne committez jamais .env dans Git**
4. **Utilisez un mot de passe fort** (12+ caractères)

---

## 🔍 Dépannage

### Erreur : "No module named 'flask_bcrypt'"

```bash
pip install flask-bcrypt --break-system-packages
sudo systemctl restart fm-monitor
```

### Erreur : "No module named 'dotenv'"

```bash
pip install python-dotenv --break-system-packages
sudo systemctl restart fm-monitor
```

### Service ne démarre pas

```bash
# Voir les erreurs
sudo journalctl -u fm-monitor -n 100

# Vérifier les imports
cd ~/fm-monitor
python3 -c "import flask_bcrypt; import flask_limiter; import dotenv"
```

### Mot de passe oublié

```bash
cd ~/fm-monitor
python3 migrate_passwords.py
# Réinitialise à : admin / password
```

---

## 📞 Support

En cas de problème :
1. Vérifier les logs : `sudo journalctl -u fm-monitor -n 100`
2. Tester les imports Python
3. Vérifier que .env existe et contient SECRET_KEY
4. Restaurer la sauvegarde si nécessaire : `cp app_backup_*.py app.py`

---

## ✨ Prochaines étapes

Après avoir validé que tout fonctionne :
- [ ] Phase 2 : HTTPS/SSL (chiffrement)
- [ ] Phase 3 : CSRF Protection
- [ ] Phase 4 : Système de licences

**Félicitations ! Votre FM Monitor est maintenant beaucoup plus sécurisé !** 🎉
