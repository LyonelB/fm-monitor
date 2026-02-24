"""
Gestion de l'authentification - Version sécurisée avec Bcrypt
"""
from functools import wraps
from flask import session, redirect, url_for, jsonify, request
from flask_bcrypt import Bcrypt
import json
import logging

logger = logging.getLogger(__name__)
bcrypt = Bcrypt()

class Auth:
    def __init__(self, config_path='config.json'):
        """Initialise le système d'authentification"""
        self.config_path = config_path
        self.users = self.load_users()
    
    def load_users(self):
        """
        Charge les utilisateurs depuis config.json
        
        Format attendu dans config.json:
        {
            "auth": {
                "username": "admin",
                "password_hash": "$2b$12$..."  # Hash Bcrypt
            }
        }
        """
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            auth_config = config.get('auth', {})
            
            if 'username' in auth_config and 'password_hash' in auth_config:
                return {
                    auth_config['username']: auth_config['password_hash']
                }
            else:
                logger.warning("Aucune configuration d'authentification trouvée dans config.json")
                # Créer un utilisateur par défaut (admin/password) si aucun n'existe
                return self.create_default_user()
        
        except FileNotFoundError:
            logger.error(f"Fichier {self.config_path} non trouvé")
            return self.create_default_user()
        except json.JSONDecodeError:
            logger.error(f"Erreur de parsing du fichier {self.config_path}")
            return self.create_default_user()
    
    def create_default_user(self):
        """
        Crée un utilisateur par défaut (admin/password)
        ⚠️ À changer immédiatement après le premier login !
        """
        logger.warning("Création d'un utilisateur par défaut: admin/password")
        logger.warning("⚠️ CHANGEZ CE MOT DE PASSE IMMÉDIATEMENT !")
        
        # Hash de "password"
        default_hash = bcrypt.generate_password_hash('password').decode('utf-8')
        
        # Sauvegarder dans config.json
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        except:
            config = {}
        
        config['auth'] = {
            'username': 'admin',
            'password_hash': default_hash
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        return {'admin': default_hash}
    
    def verify_credentials(self, username, password):
        """
        Vérifie les identifiants de connexion avec Bcrypt
        
        Args:
            username: Nom d'utilisateur
            password: Mot de passe en clair
        
        Returns:
            bool: True si les identifiants sont corrects
        """
        if not username or not password:
            return False
        
        # Recharger les utilisateurs à chaque vérification
        # (pour prendre en compte les changements de mot de passe)
        self.users = self.load_users()
        
        if username in self.users:
            stored_hash = self.users[username]
            
            # Vérifier avec Bcrypt
            try:
                return bcrypt.check_password_hash(stored_hash, password)
            except Exception as e:
                logger.error(f"Erreur lors de la vérification du mot de passe: {e}")
                return False
        
        return False
    
    def login_required(self, f):
        """
        Décorateur pour protéger les routes nécessitant une authentification
        
        Usage:
            @app.route('/protected')
            @auth.login_required
            def protected_route():
                return "Protected content"
        """
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                # Si c'est une requête JSON (API), renvoyer 401
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
                # Sinon, rediriger vers la page de login
                return redirect(url_for('login', next=request.url))
            return f(*args, **kwargs)
        return decorated_function
    
    @staticmethod
    def hash_password(password):
        """
        Hashe un mot de passe avec Bcrypt
        
        Args:
            password: Mot de passe en clair
        
        Returns:
            str: Hash Bcrypt du mot de passe
        """
        return bcrypt.generate_password_hash(password).decode('utf-8')
    
    @staticmethod
    def check_password(password, password_hash):
        """
        Vérifie un mot de passe contre son hash
        
        Args:
            password: Mot de passe en clair
            password_hash: Hash Bcrypt
        
        Returns:
            bool: True si le mot de passe correspond
        """
        try:
            return bcrypt.check_password_hash(password_hash, password)
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du mot de passe: {e}")
            return False
