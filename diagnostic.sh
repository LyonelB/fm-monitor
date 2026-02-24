#!/bin/bash
# Script de diagnostic FM Monitor

echo "=========================================="
echo "Diagnostic FM Monitor"
echo "=========================================="
echo ""

echo "1. Statut du service :"
sudo systemctl status fm-monitor --no-pager | head -20
echo ""

echo "2. Dernières erreurs (50 lignes) :"
sudo journalctl -u fm-monitor -n 50 --no-pager
echo ""

echo "3. Test des imports Python :"
cd ~/fm-monitor
python3 << 'EOF'
try:
    print("  - Importing flask... ", end="")
    from flask import Flask
    print("✅")
except Exception as e:
    print(f"❌ {e}")

try:
    print("  - Importing flask_bcrypt... ", end="")
    from flask_bcrypt import Bcrypt
    print("✅")
except Exception as e:
    print(f"❌ {e}")

try:
    print("  - Importing flask_limiter... ", end="")
    from flask_limiter import Limiter
    print("✅")
except Exception as e:
    print(f"❌ {e}")

try:
    print("  - Importing dotenv... ", end="")
    from dotenv import load_dotenv
    print("✅")
except Exception as e:
    print(f"❌ {e}")

try:
    print("  - Importing monitor... ", end="")
    from monitor import FMMonitor
    print("✅")
except Exception as e:
    print(f"❌ {e}")

try:
    print("  - Importing auth... ", end="")
    from auth import Auth
    print("✅")
except Exception as e:
    print(f"❌ {e}")
EOF

echo ""
echo "4. Fichier .env :"
if [ -f ~/fm-monitor/.env ]; then
    echo "  ✅ Fichier .env existe"
    echo "  Contenu (SECRET_KEY masqué) :"
    cat ~/fm-monitor/.env | sed 's/SECRET_KEY=.*/SECRET_KEY=***MASQUE***/g'
else
    echo "  ❌ Fichier .env manquant !"
fi

echo ""
echo "=========================================="
echo "Fin du diagnostic"
echo "=========================================="
