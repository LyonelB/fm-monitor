#!/usr/bin/env python3
"""
Générateur de licences FM Monitor (Version Full)
Usage: python3 generate_license.py [email]
"""
import sys
import json
from datetime import datetime
from license_manager import LicenseManager

def generate_license(email=None):
    """Génère une nouvelle licence"""
    lm = LicenseManager()
    
    # Générer la clé
    license_key = lm.generate_license_key(email)
    
    # Créer l'enregistrement
    license_record = {
        "license_key": license_key,
        "email": email,
        "generated_at": datetime.now().isoformat(),
        "status": "active"
    }
    
    # Sauvegarder dans un fichier de licences générées
    licenses_file = "generated_licenses.json"
    try:
        with open(licenses_file, 'r') as f:
            licenses = json.load(f)
    except:
        licenses = []
    
    licenses.append(license_record)
    
    with open(licenses_file, 'w') as f:
        json.dump(licenses, f, indent=2)
    
    return license_key, license_record

def main():
    """Point d'entrée principal"""
    email = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("=" * 60)
    print("  FM Monitor - Générateur de licences Full")
    print("=" * 60)
    print()
    
    if not email:
        email = input("Email du client (optionnel, Entrée pour ignorer): ").strip()
        if not email:
            email = None
    
    print()
    print("Génération de la licence Full...")
    
    license_key, record = generate_license(email)
    
    print()
    print("✅ Licence Full générée avec succès !")
    print()
    print("─" * 60)
    print(f"  Clé de licence: {license_key}")
    if email:
        print(f"  Email: {email}")
    print(f"  Générée le: {record['generated_at']}")
    print("─" * 60)
    print()
    print("📧 À envoyer au client:")
    print()
    print(f"  Votre clé de licence FM Monitor Full:")
    print(f"  {license_key}")
    print()
    if email:
        print(f"  Email associé: {email}")
    print()
    print("  Pour activer:")
    print("  1. Connectez-vous à FM Monitor")
    print("  2. Allez dans Configuration > Licence")
    print("  3. Entrez votre clé de licence")
    if email:
        print(f"  4. Entrez l'email: {email}")
    print("  5. Cliquez sur Activer")
    print()
    print("─" * 60)
    print()
    print(f"💾 Licence sauvegardée dans: generated_licenses.json")
    print()

if __name__ == '__main__':
    main()
