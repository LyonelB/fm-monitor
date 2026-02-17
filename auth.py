#!/usr/bin/env python3
"""
Module d'authentification simple
"""
from functools import wraps
from flask import session, redirect, url_for, request
import hashlib
import json
import os

class Auth:
    def __init__(self, config_file='users.json'):
        self.config_file = config_file
        self.init_users()
    
    def init_users(self):
        """Crée le fichier users.json s'il n'existe pas"""
        if not os.path.exists(self.config_file):
            # Utilisateur par défaut: admin / admin123
            default_users = {
                'admin': self.hash_password('admin123')
            }
            with open(self.config_file, 'w') as f:
                json.dump(default_users, f, indent=2)
    
    def hash_password(self, password):
        """Hash un mot de passe avec SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_credentials(self, username, password):
        """Vérifie les identifiants"""
        try:
            with open(self.config_file, 'r') as f:
                users = json.load(f)
            
            if username in users:
                return users[username] == self.hash_password(password)
            return False
        except Exception as e:
            print(f"Erreur vérification: {e}")
            return False
    
    def login_required(self, f):
        """Décorateur pour protéger les routes"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session:
                return redirect(url_for('login', next=request.url))
            return f(*args, **kwargs)
        return decorated_function
