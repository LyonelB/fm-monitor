#!/usr/bin/env python3
r"""
patch_email_toggle_native.py
Toggle "alertes email actives" (live, sans redémarrage) — VERSION NATIVE.

Patche DEUX fichiers :

  email_alert.py
    - __init__            : self.alerts_enabled = email.alerts_enabled (défaut True)
    - send_alert          : bloque si coupé ET alert_type != "Test"
    - send_recovery_alert : bloque si coupé

  app.py
    - save_config         : persiste + applique en mémoire email.alerts_enabled
    - routes              : /api/email-alerts/status + /api/email-alerts/toggle

Aucun monkey-patch : le garde-fou vit dans EmailAlert (source unique de vérité,
insensible à une recréation de l'objet).

Chaque fichier : idempotent, validation AST, sauvegarde .bak.

/!\ Si tu as appliqué une version antérieure (monkey-patch) sur app.py :
    restaure d'abord app.py.bak, puis lance ce script.
"""
import ast
import sys
import shutil


# ════════════════════════════════════════════════════════════════════
#  email_alert.py
# ════════════════════════════════════════════════════════════════════
EA_FILE = "email_alert.py"
EA_MARKER = "self.alerts_enabled"

# -- __init__ : ajout de l'attribut ----------------------------------
EA_A1 = (
    "        self.cooldown = timedelta(minutes=self.config.get"
    "('cooldown_minutes', 1))  # 1 minute par défaut\n"
)
EA_R1 = EA_A1 + (
    "\n"
    "        # Toggle \"alertes actives\" (live, piloté par l'UI, sans redémarrage)\n"
    "        self.alerts_enabled = self.config.get('alerts_enabled', True)\n"
)

# -- send_alert : garde-fou en tête ----------------------------------
EA_A2 = (
    "            skip_cooldown: Si True, ignore le cooldown "
    "(pour les rétablissements)\n"
    "        \"\"\"\n"
    "        # Ignorer le cooldown si c'est un rétablissement OU si "
    "skip_cooldown=True\n"
)
EA_R2 = (
    "            skip_cooldown: Si True, ignore le cooldown "
    "(pour les rétablissements)\n"
    "        \"\"\"\n"
    "        # Garde-fou toggle : couper les alertes automatiques quand désactivé\n"
    "        # (l'email de test, alert_type=\"Test\", reste toujours autorisé)\n"
    "        if not getattr(self, 'alerts_enabled', True) and alert_type != \"Test\":\n"
    "            logger.info(f\"Alerte '{alert_type}' non envoyée "
    "(alertes coupées via toggle)\")\n"
    "            return False\n"
    "        # Ignorer le cooldown si c'est un rétablissement OU si "
    "skip_cooldown=True\n"
)

# -- send_recovery_alert : garde-fou en tête -------------------------
EA_A3 = (
    "        \"\"\"Envoie une alerte de rétablissement du signal\"\"\"\n"
    "        try:\n"
)
EA_R3 = (
    "        \"\"\"Envoie une alerte de rétablissement du signal\"\"\"\n"
    "        if not getattr(self, 'alerts_enabled', True):\n"
    "            logger.info(\"Alerte de rétablissement non envoyée "
    "(alertes coupées via toggle)\")\n"
    "            return False\n"
    "        try:\n"
)


# ════════════════════════════════════════════════════════════════════
#  app.py
# ════════════════════════════════════════════════════════════════════
APP_FILE = "app.py"
APP_MARKER = "email-alerts/toggle"

# -- save_config : persistance + live --------------------------------
APP_A1 = (
    "            if 'recipient_emails' in data['email']:\n"
    "                emails = data['email']['recipient_emails']\n"
    "                if isinstance(emails, str):\n"
    "                    emails = [e.strip() for e in emails.split(',') if e.strip()]\n"
    "                config['email']['recipient_emails'] = emails\n"
)
APP_R1 = APP_A1 + (
    "            if 'alerts_enabled' in data['email']:\n"
    "                enabled = bool(data['email']['alerts_enabled'])\n"
    "                config['email']['alerts_enabled'] = enabled\n"
    "                if monitor and getattr(monitor, 'email_alert', None):\n"
    "                    monitor.email_alert.alerts_enabled = enabled\n"
)

# -- routes (insérées avant /api/mpx/spectrum) -----------------------
APP_A2 = "@app.route('/api/mpx/spectrum')\n"
APP_R2 = (
    "@app.route('/api/email-alerts/status')\n"
    "@auth.login_required\n"
    "def email_alerts_status():\n"
    "    \"\"\"Retourne l'etat des alertes email\"\"\"\n"
    "    try:\n"
    "        with open('config.json', 'r') as f:\n"
    "            enabled = json.load(f).get('email', {}).get('alerts_enabled', True)\n"
    "        return jsonify({'enabled': bool(enabled)})\n"
    "    except Exception as e:\n"
    "        return jsonify({'error': str(e)}), 500\n"
    "\n"
    "@app.route('/api/email-alerts/toggle', methods=['POST'])\n"
    "@auth.login_required\n"
    "@csrf.exempt\n"
    "def email_alerts_toggle():\n"
    "    \"\"\"Active ou coupe l'envoi des alertes email (live, sans redemarrage)\"\"\"\n"
    "    try:\n"
    "        data = request.get_json()\n"
    "        enable = bool(data.get('enable', True))\n"
    "        with open('config.json', 'r') as f:\n"
    "            config = json.load(f)\n"
    "        config.setdefault('email', {})['alerts_enabled'] = enable\n"
    "        with open('config.json', 'w') as f:\n"
    "            json.dump(config, f, indent=2)\n"
    "        # Application immediate en memoire (pas de redemarrage)\n"
    "        if monitor and getattr(monitor, 'email_alert', None):\n"
    "            monitor.email_alert.alerts_enabled = enable\n"
    "        logger.info(f\"Alertes email {'activees' if enable else 'coupees'}\")\n"
    "        return jsonify({'status': 'success', 'enabled': enable})\n"
    "    except Exception as e:\n"
    "        return jsonify({'status': 'error', 'message': str(e)}), 500\n"
    "\n"
    "@app.route('/api/mpx/spectrum')\n"
)


def patch_file(path, marker, subs):
    """Applique une liste de (ancre, remplacement) à un fichier.
    subs : list de tuples (nom, ancre, remplacement).
    Idempotent via marker, validation AST, sauvegarde .bak."""
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()

    if marker in src:
        print(f"  /!\\  {path} : déjà patché (marqueur '{marker}' présent), ignoré.")
        return False

    for name, anchor, repl in subs:
        if src.count(anchor) != 1:
            print(f"  x {path} : ancre '{name}' absente ou non unique "
                  f"(trouvée {src.count(anchor)}x). Fichier modifié ?")
            sys.exit(1)
        src = src.replace(anchor, repl, 1)

    try:
        ast.parse(src)
    except SyntaxError as e:
        print(f"  x {path} : erreur de syntaxe après patch : {e}")
        sys.exit(1)

    shutil.copyfile(path, path + ".bak")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(src)
    print(f"  ok {path} patché (sauvegarde : {path}.bak)")
    return True


def main():
    ea = patch_file(EA_FILE, EA_MARKER, [
        ("__init__", EA_A1, EA_R1),
        ("send_alert", EA_A2, EA_R2),
        ("send_recovery_alert", EA_A3, EA_R3),
    ])
    if ea:
        print("     - self.alerts_enabled (défaut True)")
        print("     - garde-fou send_alert (alert_type != 'Test')")
        print("     - garde-fou send_recovery_alert")

    app = patch_file(APP_FILE, APP_MARKER, [
        ("save_config", APP_A1, APP_R1),
        ("routes", APP_A2, APP_R2),
    ])
    if app:
        print("     - save_config persiste email.alerts_enabled")
        print("     - routes /api/email-alerts/status + /toggle")

    if not ea and not app:
        print("Rien à faire : les deux fichiers sont déjà patchés.")


if __name__ == '__main__':
    main()
