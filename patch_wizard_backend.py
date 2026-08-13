#!/usr/bin/env python3
"""
patch_wizard_backend.py

Ajoute le support du wizard de première connexion dans app.py :

  1. before_request : redirige vers /setup tant que setup.completed est faux
     (utilisateur connecté, route non-technique). N'altère PAS la logique de
     timeout de session existante.
  2. Route /setup : sert le wizard (templates/setup.html).
  3. save_config étendu :
     - clé 'tef' (enabled, serial_port) → choix de la source ;
     - clés SMTP (smtp_server, smtp_port) dans 'email' ;
     - flag 'setup' (completed) ;
     - needs_restart déclenché aussi par un changement de source (tef.enabled),
       avec rechargement de monitor.tef_config → bascule de source LIVE.

Ne touche pas au chemin RTL-SDR existant (extensions uniquement).
Sécurités : .bak, validation AST, idempotent.
"""

import ast, shutil, sys
from pathlib import Path

APP = Path(__file__).resolve().parent / "app.py"

# ═══════════════════════════════════════════════════════════════════════
# 1. before_request : insérer la redirection wizard.
#    On insère juste APRÈS la mise à jour de last_active (fin de la fonction).
# ═══════════════════════════════════════════════════════════════════════
OLD_BEFORE = """        session['last_active'] = datetime.now(timezone.utc).isoformat()

# Instance globale du moniteur
monitor = None"""

NEW_BEFORE = """        session['last_active'] = datetime.now(timezone.utc).isoformat()

    # ── Redirection vers le wizard de première connexion ──────────────────
    # Tant que la configuration initiale n'est pas terminée, on force /setup.
    if session.get('logged_in') and request.endpoint not in (
        'setup_wizard', 'save_config', 'scan_dongle', 'get_config_full',
        'login', 'logout', 'static'
    ):
        try:
            with open('config.json', 'r') as _f:
                _cfg = json.load(_f)
            if not _cfg.get('setup', {}).get('completed', True):
                # Ne rediriger que les pages HTML, pas les appels API/JSON.
                if not request.path.startswith('/api/') and not request.is_json:
                    return redirect(url_for('setup_wizard'))
        except Exception:
            pass

# Instance globale du moniteur
monitor = None"""

# ═══════════════════════════════════════════════════════════════════════
# 2. Route /setup : insérer juste après la route index().
# ═══════════════════════════════════════════════════════════════════════
OLD_INDEX = """def index():
    \"\"\"Page d'accueil avec le dashboard\"\"\"
    return render_template('index.html')"""

NEW_INDEX = """def index():
    \"\"\"Page d'accueil avec le dashboard\"\"\"
    return render_template('index.html')

@app.route('/setup')
@auth.login_required
def setup_wizard():
    \"\"\"Assistant de première connexion.\"\"\"
    return render_template('setup.html')"""

# ═══════════════════════════════════════════════════════════════════════
# 3a. save_config : gérer 'tef', SMTP, et 'setup' — inséré avant l'écriture
#     du fichier (juste avant "# Sauvegarder le fichier config.json").
# ═══════════════════════════════════════════════════════════════════════
OLD_SAVE_TAIL = """        # Sauvegarder le fichier config.json
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)"""

NEW_SAVE_TAIL = """        # Configuration de la source (TEF vs RTL-SDR) — pour le wizard
        if 'tef' in data:
            if 'tef' not in config:
                config['tef'] = {}
            if 'enabled' in data['tef']:
                config['tef']['enabled'] = bool(data['tef']['enabled'])
            if 'serial_port' in data['tef']:
                config['tef']['serial_port'] = data['tef']['serial_port']
            if 'alsa_device' in data['tef']:
                config['tef']['alsa_device'] = data['tef']['alsa_device']

        # Champs SMTP (structure email complète attendue par email_alert.py)
        if 'email' in data:
            if 'smtp_server' in data['email']:
                config['email']['smtp_server'] = data['email']['smtp_server']
            if 'smtp_port' in data['email']:
                config['email']['smtp_port'] = int(data['email']['smtp_port'])

        # Flag de fin du wizard
        if 'setup' in data:
            if 'setup' not in config:
                config['setup'] = {}
            if 'completed' in data['setup']:
                config['setup']['completed'] = bool(data['setup']['completed'])

        # Sauvegarder le fichier config.json
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)"""

# ═══════════════════════════════════════════════════════════════════════
# 3b. needs_restart : déclencher aussi sur changement de source (tef.enabled),
#     et recharger tef_config au redémarrage.
# ═══════════════════════════════════════════════════════════════════════
OLD_RESTART = """        # Redémarrer le monitoring si la fréquence ou le gain a changé
        needs_restart = ('rtl_sdr' in data and
                        ('frequency' in data['rtl_sdr'] or 'gain' in data['rtl_sdr']))
        if needs_restart and monitor:
            logger.info("Fréquence/gain modifié - redémarrage du monitoring")
            monitor.stop()
            time.sleep(2)
            monitor.config = config
            monitor.rtl_config = config['rtl_sdr']
            monitor.audio_config = config['audio']
            monitor.start()"""

NEW_RESTART = """        # Redémarrer le monitoring si la fréquence, le gain OU la source a changé.
        needs_restart = (
            ('rtl_sdr' in data and ('frequency' in data['rtl_sdr'] or 'gain' in data['rtl_sdr']))
            or ('station' in data and 'frequency' in data['station'])
            or ('tef' in data and 'enabled' in data['tef'])
        )
        if needs_restart and monitor:
            logger.info("Config source/fréquence modifiée - redémarrage du monitoring")
            monitor.stop()
            time.sleep(2)
            monitor.config = config
            monitor.rtl_config = config['rtl_sdr']
            monitor.audio_config = config['audio']
            # Recharger la config TEF pour une bascule de source à chaud.
            if 'tef' in config:
                monitor.tef_config = config['tef']
                monitor.use_tef = config['tef'].get('enabled', False)
            monitor.start()"""


FRAGMENTS = [
    ("before_request redirection", OLD_BEFORE, NEW_BEFORE),
    ("route /setup", OLD_INDEX, NEW_INDEX),
    ("save_config tef/smtp/setup", OLD_SAVE_TAIL, NEW_SAVE_TAIL),
    ("needs_restart source", OLD_RESTART, NEW_RESTART),
]


def main():
    if not APP.exists():
        sys.exit(f"ERREUR : {APP} introuvable.")
    src = APP.read_text(encoding="utf-8")
    if "setup_wizard" in src:
        sys.exit("Le patch semble déjà appliqué (setup_wizard présent). Rien à faire.")

    patched = src
    for label, old, new in FRAGMENTS:
        c = patched.count(old)
        if c == 0:
            sys.exit(f"ERREUR : fragment '{label}' introuvable. Aucune écriture.")
        if c > 1:
            sys.exit(f"ERREUR : fragment '{label}' trouvé {c} fois (ambigu). Aucune écriture.")
        patched = patched.replace(old, new, 1)

    try:
        ast.parse(patched)
    except SyntaxError as e:
        sys.exit(f"ERREUR : app.py patché ne compile pas ({e}). Aucune écriture.")

    bak = APP.with_suffix(".py.bak")
    shutil.copy2(APP, bak)
    APP.write_text(patched, encoding="utf-8")
    print(f"OK — app.py patché. Sauvegarde : {bak.name}")
    print("Wizard : redirection /setup, route setup, save_config étendu (tef/smtp/setup).")


if __name__ == "__main__":
    main()
