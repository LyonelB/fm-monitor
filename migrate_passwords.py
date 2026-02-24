#!/usr/bin/env python3
"""
Script de migration des mots de passe SHA-256 vers Bcrypt
"""
import json
import sys
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

def migrate_passwords(config_path='config.json'):
    """
    Migre les mots de passe de SHA-256 vers Bcrypt
    """
    print("=" * 60)
    print("Migration des mots de passe vers Bcrypt")
    print("=" * 60)
    print()
    
    try:
        # Lire le fichier de configuration
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if 'auth' not in config:
            print("❌ Aucune configuration d'authentification trouvée")
            print("   Création d'un utilisateur par défaut : admin/password")
            
            # Créer un utilisateur par défaut
            default_hash = bcrypt.generate_password_hash('password').decode('utf-8')
            config['auth'] = {
                'username': 'admin',
                'password_hash': default_hash
            }
            
            # Sauvegarder
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ Utilisateur créé")
            print("   Username: admin")
            print("   Password: password")
            print()
            print("⚠️  CHANGEZ CE MOT DE PASSE IMMÉDIATEMENT via l'interface !")
            return
        
        password_hash = config['auth'].get('password_hash', '')
        
        # Détecter le type de hash
        if password_hash.startswith('$2b$') or password_hash.startswith('$2a$'):
            print("✅ Le mot de passe est déjà en Bcrypt")
            print("   Aucune migration nécessaire")
            return
        
        elif len(password_hash) == 64 and all(c in '0123456789abcdef' for c in password_hash):
            print("⚠️  Ancien hash SHA-256 détecté")
            print()
            print("Le mot de passe actuel utilise SHA-256 (non sécurisé).")
            print("Il doit être réinitialisé pour utiliser Bcrypt.")
            print()
            
            # Réinitialiser à "password"
            new_hash = bcrypt.generate_password_hash('password').decode('utf-8')
            config['auth']['password_hash'] = new_hash
            
            # Sauvegarder
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ Mot de passe réinitialisé")
            print()
            print("   Nouveau mot de passe temporaire : password")
            print()
            print("⚠️  CHANGEZ-LE IMMÉDIATEMENT via l'interface de configuration !")
            print("   (http://votre-ip:5000/config)")
            
        else:
            print("❓ Format de hash inconnu")
            print(f"   Hash actuel : {password_hash[:20]}...")
            print()
            print("Réinitialisation du mot de passe par sécurité...")
            
            new_hash = bcrypt.generate_password_hash('password').decode('utf-8')
            config['auth']['password_hash'] = new_hash
            
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ Mot de passe réinitialisé à : password")
            print("⚠️  CHANGEZ-LE IMMÉDIATEMENT !")
    
    except FileNotFoundError:
        print(f"❌ Fichier {config_path} non trouvé")
        sys.exit(1)
    
    except json.JSONDecodeError:
        print(f"❌ Erreur de parsing du fichier {config_path}")
        sys.exit(1)
    
    except Exception as e:
        print(f"❌ Erreur inattendue : {e}")
        sys.exit(1)
    
    print()
    print("=" * 60)
    print("Migration terminée")
    print("=" * 60)

if __name__ == '__main__':
    import os
    
    # Chercher config.json
    config_paths = [
        'config.json',
        'fm-monitor/config.json',
        os.path.expanduser('~/fm-monitor/config.json')
    ]
    
    config_path = None
    for path in config_paths:
        if os.path.exists(path):
            config_path = path
            break
    
    if config_path:
        print(f"Fichier de configuration trouvé : {config_path}")
        print()
        migrate_passwords(config_path)
    else:
        print("❌ Aucun fichier config.json trouvé")
        print()
        print("Chemins recherchés :")
        for path in config_paths:
            print(f"  - {path}")
