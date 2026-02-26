#!/usr/bin/env python3
"""
Module de gestion des licences FM Monitor
Version Lite / Full
"""
import hashlib
import hmac
import secrets
import json
import os
from datetime import datetime

class LicenseManager:
    """Gestionnaire de licences FM Monitor"""
    
    # Clé secrète pour la génération/validation des licences
    # À générer de manière unique pour chaque installation du serveur de licences
    SECRET_KEY = "FM_MONITOR_LICENSE_SECRET_2024"  # À changer en production
    
    LICENSE_FILE = "license.json"
    
    def __init__(self):
        self.license_data = self._load_license()
    
    def _load_license(self):
        """Charge les données de licence depuis le fichier"""
        if os.path.exists(self.LICENSE_FILE):
            try:
                with open(self.LICENSE_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "license_key": None,
            "is_full": False,
            "activated_at": None,
            "email": None
        }
    
    def _save_license(self):
        """Sauvegarde les données de licence"""
        with open(self.LICENSE_FILE, 'w') as f:
            json.dump(self.license_data, f, indent=2)
    
    def generate_license_key(self, email=None):
        """
        Génère une nouvelle clé de licence
        Format: FMMON-XXXXX-XXXXX-XXXXX-XXXXX
        """
        # Générer 4 blocs de 5 caractères alphanumériques
        blocks = []
        for i in range(4):
            # Générer un bloc aléatoire
            block = secrets.token_hex(3).upper()[:5]
            blocks.append(block)
        
        # Concaténer les blocs
        license_base = '-'.join(blocks)
        
        # Calculer le checksum pour validation
        checksum = self._calculate_checksum(license_base, email)
        
        # Format final: FMMON-XXXXX-XXXXX-XXXXX-XXXXX
        license_key = f"FMMON-{license_base}-{checksum}"
        
        return license_key
    
    def _calculate_checksum(self, license_base, email=None):
        """Calcule le checksum de validation"""
        data = f"{license_base}:{email or ''}:{self.SECRET_KEY}"
        hash_obj = hashlib.sha256(data.encode())
        # Prendre les 5 premiers caractères du hash
        return hash_obj.hexdigest()[:5].upper()
    
    def validate_license_key(self, license_key, email=None):
        """
        Valide une clé de licence
        Retourne True si la licence est valide
        """
        if not license_key:
            return False
        
        # Vérifier le format
        parts = license_key.split('-')
        if len(parts) != 6:  # FMMON + 4 blocs + checksum
            return False
        
        if parts[0] != "FMMON":
            return False
        
        # Reconstruire la base de la licence
        license_base = '-'.join(parts[1:5])
        provided_checksum = parts[5]
        
        # Calculer le checksum attendu
        expected_checksum = self._calculate_checksum(license_base, email)
        
        # Vérifier le checksum
        return hmac.compare_digest(provided_checksum, expected_checksum)
    
    def activate_license(self, license_key, email=None):
        """
        Active une licence
        Retourne (success: bool, message: str)
        """
        if not self.validate_license_key(license_key, email):
            return False, "Clé de licence invalide"
        
        # Enregistrer la licence
        self.license_data = {
            "license_key": license_key,
            "is_full": True,
            "activated_at": datetime.now().isoformat(),
            "email": email
        }
        self._save_license()
        
        return True, "Licence Full activée avec succès !"
    
    def deactivate_license(self):
        """Désactive la licence"""
        self.license_data = {
            "license_key": None,
            "is_full": False,
            "activated_at": None,
            "email": None
        }
        self._save_license()
    
    def is_full(self):
        """Vérifie si l'utilisateur a une licence Full active"""
        return self.license_data.get("is_full", False)
    
    def get_license_status(self):
        """Retourne le statut de la licence"""
        if self.is_full():
            return {
                "status": "full",
                "license_key": self.license_data.get("license_key"),
                "activated_at": self.license_data.get("activated_at"),
                "email": self.license_data.get("email")
            }
        else:
            return {
                "status": "lite",
                "license_key": None,
                "activated_at": None,
                "email": None
            }
    
    def get_available_features(self):
        """Retourne la liste des fonctionnalités disponibles"""
        if self.is_full():
            return {
                "audio": True,
                "vu_meter": True,
                "rds": True,
                "alerts": True,
                "statistics": True,
                "history": True,
                "network_config": True
            }
        else:
            return {
                "audio": True,
                "vu_meter": True,
                "rds": False,
                "alerts": False,
                "statistics": False,
                "history": False,
                "network_config": False
            }


# Instance globale du gestionnaire de licences
license_manager = LicenseManager()


def license_required(feature):
    """
    Décorateur pour protéger les routes qui nécessitent une licence Full
    
    Usage:
        @app.route('/api/rds')
        @license_required('rds')
        def get_rds():
            ...
    """
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            features = license_manager.get_available_features()
            if not features.get(feature, False):
                from flask import jsonify
                return jsonify({
                    'status': 'error',
                    'message': 'Cette fonctionnalité nécessite une licence Full',
                    'feature': feature,
                    'required_license': 'full'
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


if __name__ == '__main__':
    # Tests
    lm = LicenseManager()
    
    # Générer une licence
    license_key = lm.generate_license_key("test@example.com")
    print(f"Licence générée: {license_key}")
    
    # Valider la licence
    is_valid = lm.validate_license_key(license_key, "test@example.com")
    print(f"Licence valide: {is_valid}")
    
    # Activer la licence
    success, message = lm.activate_license(license_key, "test@example.com")
    print(f"Activation: {success} - {message}")
    
    # Vérifier le statut
    status = lm.get_license_status()
    print(f"Statut: {status}")
    
    # Fonctionnalités disponibles
    features = lm.get_available_features()
    print(f"Fonctionnalités: {features}")
