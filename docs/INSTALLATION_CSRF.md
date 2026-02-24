# 🛡️ Installation CSRF Protection - FM Monitor

## 🎯 Objectif

Protéger FM Monitor contre les attaques **CSRF** (Cross-Site Request Forgery).

**Qu'est-ce que CSRF ?**  
Une attaque où un site malveillant force votre navigateur à effectuer des actions non désirées sur FM Monitor (ex: changer la configuration, activer/désactiver des services).

**Durée** : 30-60 minutes

---

## 📦 Étape 1 : Installer Flask-WTF

```bash
cd ~/fm-monitor

# Activer le venv
source venv/bin/activate

# Installer Flask-WTF
pip install Flask-WTF==1.2.1

# Vérifier l'installation
python3 -c "from flask_wtf.csrf import CSRFProtect; print('✅ Flask-WTF installé')"

# Désactiver le venv
deactivate
```

**Résultat attendu** :
```
✅ Flask-WTF installé
```

---

## 🔄 Étape 2 : Mettre à jour app.py

```bash
cd ~/fm-monitor

# Sauvegarder l'ancien
cp app.py app_before_csrf.py

# Installer la nouvelle version avec CSRF
cp ~/Téléchargements/app_secure.py app.py

echo "✅ app.py mis à jour avec CSRF Protection"
```

---

## 📝 Étape 3 : Ajouter le token CSRF dans les templates

### Fichiers à modifier

Vous devez ajouter le token CSRF dans **tous les templates HTML** :

1. `templates/index.html` (Dashboard)
2. `templates/config.html` (Configuration)
3. `templates/stats.html` (Statistiques)
4. `templates/login.html` (Login)

---

### Modification 1 : Ajouter la balise meta dans le `<head>`

**Dans CHAQUE fichier HTML**, ajoutez cette ligne dans le `<head>` :

```html
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="csrf-token" content="{{ csrf_token() }}">  <!-- ← AJOUTER ICI -->
  <title>FM Monitor</title>
  <!-- ... -->
</head>
```

---

### Modification 2 : Fonction JavaScript pour récupérer le token

**Dans CHAQUE fichier HTML**, ajoutez cette fonction JavaScript :

```html
<script>
  // Fonction pour récupérer le token CSRF
  function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }
</script>
```

**Placez-la** juste avant la fermeture de `</body>` ou dans la section `<script>` existante.

---

### Modification 3 : Ajouter le token dans les requêtes AJAX

**Pour TOUTES les requêtes POST**, ajoutez le header `X-CSRFToken` :

#### Exemple : Dashboard (index.html)

**Cherchez toutes les requêtes POST** comme :

```javascript
// ❌ AVANT (sans CSRF)
fetch('/api/services/toggle', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({service, enabled})
})
```

**Remplacez par** :

```javascript
// ✅ APRÈS (avec CSRF)
const csrfToken = getCSRFToken();

fetch('/api/services/toggle', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': csrfToken  // ← AJOUTER CETTE LIGNE
  },
  body: JSON.stringify({service, enabled})
})
```

#### Exemple : Configuration (config.html)

```javascript
// ✅ Avec CSRF
async function saveConfig() {
  const csrfToken = getCSRFToken();
  
  const response = await fetch('/api/config/save', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken  // ← CSRF token
    },
    body: JSON.stringify(config)
  });
  // ...
}
```

#### Exemple : Login (login.html)

```javascript
// ✅ Avec CSRF
async function login() {
  const csrfToken = getCSRFToken();
  
  const response = await fetch('/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken  // ← CSRF token
    },
    body: JSON.stringify({username, password, remember})
  });
  // ...
}
```

---

## 📋 Checklist des modifications

Pour **chaque fichier HTML** :

- [ ] `templates/login.html`
  - [ ] Ajouter `<meta name="csrf-token" content="{{ csrf_token() }}">`
  - [ ] Ajouter fonction `getCSRFToken()`
  - [ ] Ajouter `X-CSRFToken` dans la requête de login

- [ ] `templates/index.html` (Dashboard)
  - [ ] Ajouter `<meta name="csrf-token" content="{{ csrf_token() }}">`
  - [ ] Ajouter fonction `getCSRFToken()`
  - [ ] Ajouter `X-CSRFToken` dans :
    - `/api/services/toggle`
    - `/api/restart`
    - `/api/rds/read_ps`
    - `/api/rds/read_rt`

- [ ] `templates/config.html`
  - [ ] Ajouter `<meta name="csrf-token" content="{{ csrf_token() }}">`
  - [ ] Ajouter fonction `getCSRFToken()`
  - [ ] Ajouter `X-CSRFToken` dans :
    - `/api/config/save`
    - `/api/test-email`

- [ ] `templates/stats.html`
  - [ ] Ajouter `<meta name="csrf-token" content="{{ csrf_token() }}">`
  - [ ] Pas de requêtes POST normalement (juste GET)

---

## 🚀 Étape 4 : Redémarrer le service

```bash
sudo systemctl restart fm-monitor

# Attendre 2 secondes
sleep 2

# Vérifier le statut
sudo systemctl status fm-monitor
```

---

## 🧪 Étape 5 : Tester la protection CSRF

### Test 1 : Requête sans token CSRF (doit échouer)

```bash
# Essayer de changer la config sans token CSRF
curl -X POST https://192.168.1.185:5000/api/config/save \
  -k \
  -H "Content-Type: application/json" \
  -H "Cookie: session=..." \
  -d '{}'
```

**Résultat attendu** :
```
400 Bad Request
The CSRF token is missing.
```

→ ✅ Protection CSRF active !

---

### Test 2 : Requête avec token CSRF (doit fonctionner)

```bash
# D'abord récupérer un token CSRF
TOKEN=$(curl -k -s https://192.168.1.185:5000/api/csrf-token | grep -o '"csrf_token":"[^"]*' | cut -d'"' -f4)

# Puis l'utiliser dans la requête
curl -X POST https://192.168.1.185:5000/api/config/save \
  -k \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $TOKEN" \
  -d '{}'
```

**Résultat attendu** :
```json
{"status": "success", ...}
```

→ ✅ Requête acceptée avec token !

---

### Test 3 : Vérifier dans le navigateur

1. Ouvrir https://192.168.1.185:5000
2. Ouvrir les **Outils de développement** (F12)
3. Onglet **Console**
4. Taper :

```javascript
getCSRFToken()
```

**Résultat attendu** :
```
"ImFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6..."
```

→ ✅ Token CSRF disponible !

---

### Test 4 : Tester une action (toggle service)

1. Dans le dashboard, activer/désactiver un service
2. Ouvrir **Outils de développement** → **Network**
3. Regarder la requête `/api/services/toggle`
4. Onglet **Headers**

**Vérifier** :
```
Request Headers:
  Content-Type: application/json
  X-CSRFToken: ImFiY2RlZmdoaWprbG1ub3BxcnN0dXZ3eHl6...
```

→ ✅ Token CSRF envoyé automatiquement !

---

## ⚠️ Problèmes courants

### Erreur : "The CSRF token is missing"

**Cause** : Le token CSRF n'est pas inclus dans la requête.

**Solution** :
1. Vérifiez que la balise meta est présente : `<meta name="csrf-token" content="{{ csrf_token() }}">`
2. Vérifiez que la fonction `getCSRFToken()` est définie
3. Vérifiez que le header `X-CSRFToken` est bien ajouté dans la requête

---

### Erreur : "The CSRF token is invalid"

**Cause** : Le token a expiré ou est incorrect.

**Solution** :
1. Rechargez la page pour obtenir un nouveau token
2. Vérifiez que vous utilisez le bon token (pas un token ancien)

---

### Les routes SSE/Streaming ne fonctionnent plus

**Cause** : Ces routes ne peuvent pas avoir de token CSRF.

**Solution** : Déjà fait dans app.py ! Les routes suivantes sont exemptées :
- `/stream.mp3` (streaming audio)
- `/api/stream/stats` (SSE)

---

### Le formulaire de login ne fonctionne plus

**Cause** : Token CSRF manquant dans le formulaire.

**Solution** : Vérifiez que vous avez bien `{{ csrf_token() }}` dans le template ou le header `X-CSRFToken` dans la requête AJAX.

---

## 📊 Niveau de sécurité final

### Avant CSRF
**Score : 8/10** ✅
- Bcrypt ✅
- Rate Limiting ✅
- Secret Key ✅
- HTTPS ✅
- CSRF ❌

### Après CSRF
**Score : 9/10** 🎉
- Bcrypt ✅
- Rate Limiting ✅
- Secret Key ✅
- HTTPS ✅
- **CSRF ✅**

**Protection complète contre** :
- ✅ Vol de mots de passe (Bcrypt)
- ✅ Attaques par force brute (Rate Limiting)
- ✅ Interception de communications (HTTPS)
- ✅ **Attaques CSRF (CSRF Protection)**

---

## 🎯 Prochaine étape : Système de licences

Maintenant que la sécurité est au maximum, vous pouvez passer au **système de licences** :

- Gratuit : Audio + VU-mètre uniquement
- Payant : Toutes les fonctionnalités
- Génération et validation de clés
- Protection des routes par licence

---

## 📝 Résumé des fichiers modifiés

**Backend** :
- ✅ `app.py` (CSRF Protection activée)

**Frontend** (à modifier manuellement) :
- ⏳ `templates/login.html`
- ⏳ `templates/index.html`
- ⏳ `templates/config.html`
- ⏳ `templates/stats.html`

**Je peux créer des versions modifiées de ces templates si vous voulez !**

---

## ✨ Félicitations !

Avec CSRF Protection, FM Monitor atteint un **niveau de sécurité professionnel** de **9/10** !

**Prêt pour la commercialisation** du point de vue sécurité ! 🚀🔒
