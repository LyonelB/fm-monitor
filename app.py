#!/usr/bin/env python3
"""
Application Flask pour le monitoring FM - Version sécurisée complète
"""
from flask import Flask, render_template, Response, jsonify, request, session, redirect, url_for
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf
import logging
import time
import json
import subprocess
import os
from dotenv import load_dotenv
from monitor import FMMonitor
from auth import Auth

# Charger les variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Secret key depuis variable d'environnement (ou génération aléatoire)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(32).hex()

# Configuration Bcrypt pour hashage sécurisé des mots de passe
bcrypt = Bcrypt(app)

# Configuration CSRF Protection
csrf = CSRFProtect(app)

# Configuration Rate Limiting pour protection contre les attaques
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

auth = Auth()

# Instance globale du moniteur
monitor = None

# Cache pour les stats (évite les verrous excessifs)
stats_cache = {'data': None, 'timestamp': 0}

def generate_stats_sse():
    """Générateur SSE qui pousse les stats toutes les 50ms"""
    import json
    while True:
        try:
            if monitor:
                data = monitor.get_stats()
                yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.05)
        except GeneratorExit:
            break
        except Exception as e:
            logger.error(f"Erreur SSE: {e}")
            time.sleep(0.1)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")  # Maximum 5 tentatives de connexion par minute
def login():
    """Page de connexion - Sécurisée avec rate limiting"""
    if request.method == 'POST':
        # Supporter à la fois JSON et form data
        if request.is_json:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            remember = data.get('remember', False)
        else:
            username = request.form.get('username')
            password = request.form.get('password')
            remember = request.form.get('remember') == 'on'

        if auth.verify_credentials(username, password):
            session['logged_in'] = True
            session['username'] = username

            if remember:
                session.permanent = True

            logger.info(f"Connexion réussie pour {username}")

            # Réponse JSON pour la nouvelle page
            if request.is_json:
                next_page = request.args.get('next', '/')
                return jsonify({
                    'status': 'success',
                    'message': 'Connexion réussie',
                    'redirect': next_page
                })
            # Réponse classique pour ancienne page
            else:
                next_page = request.args.get('next', '/')
                return redirect(next_page)
        else:
            logger.warning(f"Tentative de connexion échouée pour {username}")

            # Réponse JSON pour la nouvelle page
            if request.is_json:
                return jsonify({
                    'status': 'error',
                    'message': 'Nom d\'utilisateur ou mot de passe incorrect'
                }), 401
            # Réponse classique pour ancienne page
            else:
                return render_template('login.html', error='Identifiants incorrects')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Déconnexion"""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"Déconnexion de {username}")
    return redirect(url_for('login'))

@app.route('/api/csrf-token')
def get_csrf_token():
    """Retourne un token CSRF pour les requêtes AJAX"""
    return jsonify({'csrf_token': generate_csrf()})

@app.route('/')
@auth.login_required
def index():
    """Page d'accueil avec le dashboard"""
    return render_template('index.html')

@app.route('/config')
@auth.login_required
def config():
    """Page de configuration"""
    return render_template('config.html')

@app.route('/stats')
@auth.login_required
def stats():
    """Page des statistiques"""
    return render_template('stats.html')

@app.route('/api/stats')
@limiter.exempt
def get_stats():
    """Récupère les statistiques avec cache 100ms"""
    now = time.time()
    if stats_cache['data'] and (now - stats_cache['timestamp']) < 0.1:
        return jsonify(stats_cache['data'])

    if monitor:
        data = monitor.get_stats()
        stats_cache['data'] = data
        stats_cache['timestamp'] = now
        return jsonify(data)

    return jsonify({'error': 'Monitor not initialized'}), 503

@app.route('/api/stream/stats')
@limiter.exempt  # Exemption rate limiting pour SSE continu
@csrf.exempt  # Exemption CSRF pour SSE (Server-Sent Events)
def stream_stats():
    """SSE : pousse les stats en continu vers le navigateur"""
    return Response(
        generate_stats_sse(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@app.route('/api/services/status')
@limiter.exempt
def get_services_status():
    """Retourne l'état de tous les services"""
    if monitor:
        return jsonify({'status': 'success', 'services': monitor.get_services_status()})
    return jsonify({'status': 'error', 'message': 'Monitor not initialized'}), 503

@app.route('/api/services/toggle', methods=['POST'])
def toggle_service():
    """Active ou désactive un service"""
    try:
        data = request.get_json()
        service = data.get('service')
        enabled = data.get('enabled')

        if service is None or enabled is None:
            return jsonify({'status': 'error', 'message': 'Paramètres manquants'}), 400

        if monitor:
            success = monitor.toggle_service(service, enabled)
            if success:
                return jsonify({
                    'status': 'success',
                    'service': service,
                    'enabled': enabled,
                    'services': monitor.get_services_status()
                })
            else:
                return jsonify({'status': 'error', 'message': f'Service inconnu: {service}'}), 400

        return jsonify({'status': 'error', 'message': 'Monitor not initialized'}), 503

    except Exception as e:
        logger.error(f"Erreur toggle service: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/config/full')
def get_config_full():
    """Retourne la configuration complète (mot de passe masqué)"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        # Masquer le mot de passe email
        if 'email' in config and 'sender_password' in config['email']:
            config['email']['sender_password'] = '********'
        return jsonify(config)
    except Exception as e:
        logger.error(f"Erreur lors de la lecture de la config: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/save', methods=['POST'])
@auth.login_required
def save_config():
    """Sauvegarde la configuration"""
    try:
        data = request.get_json()

        with open('config.json', 'r') as f:
            config = json.load(f)

        # Configuration station
        if 'station' in data:
            if 'name' in data['station']:
                config['station']['name'] = data['station']['name']
            if 'frequency' in data['station']:
                config['station']['frequency'] = data['station']['frequency']
                config['station']['frequency_display'] = data['station']['frequency']

        # Configuration RTL-SDR
        if 'rtl_sdr' in data:
            if 'frequency' in data['rtl_sdr']:
                config['rtl_sdr']['frequency'] = data['rtl_sdr']['frequency']

            if 'gain' in data['rtl_sdr']:
                gain = str(data['rtl_sdr']['gain']).strip()
                if gain == '0':
                    gain = 'auto'
                config['rtl_sdr']['gain'] = gain
                logger.info(f"Gain modifié: {gain}")

        # Configuration audio
        if 'audio' in data:
            if 'silence_threshold' in data['audio']:
                config['audio']['silence_threshold'] = float(data['audio']['silence_threshold'])
            if 'silence_duration' in data['audio']:
                config['audio']['silence_duration'] = int(data['audio']['silence_duration'])

        # Configuration email
        if 'email' in data:
            if 'sender_email' in data['email']:
                config['email']['sender_email'] = data['email']['sender_email']
            if 'sender_password' in data['email']:
                config['email']['sender_password'] = data['email']['sender_password']
            if 'recipient_emails' in data['email']:
                emails = data['email']['recipient_emails']
                if isinstance(emails, str):
                    emails = [e.strip() for e in emails.split(',') if e.strip()]
                config['email']['recipient_emails'] = emails

        # Configuration des identifiants de connexion (avec Bcrypt)
        if 'auth' in data:
            if 'auth' not in config:
                config['auth'] = {}

            auth_data = data['auth']

            # Modifier le nom d'utilisateur si fourni
            if 'username' in auth_data and auth_data['username']:
                old_username = config['auth'].get('username', 'unknown')
                config['auth']['username'] = auth_data['username']
                logger.info(f"Nom d'utilisateur modifié: {old_username} → {auth_data['username']}")

            # Modifier le mot de passe si fourni (hashage avec Bcrypt)
            if 'password' in auth_data and auth_data['password']:
                # Hasher le mot de passe avec Bcrypt (SÉCURISÉ)
                password_hash = bcrypt.generate_password_hash(auth_data['password']).decode('utf-8')
                config['auth']['password_hash'] = password_hash
                logger.info("Mot de passe modifié et hashé avec Bcrypt")

                # Recharger l'instance Auth avec les nouveaux identifiants
                global auth
                auth = Auth()

        # Configuration réseau (nouveau)
        if 'network' in data:
            if 'network' not in config:
                config['network'] = {}

            network_data = data['network']
            config['network']['mode'] = network_data.get('mode', 'dhcp')
            config['network']['ip'] = network_data.get('ip', '')
            config['network']['netmask'] = network_data.get('netmask', '')
            config['network']['gateway'] = network_data.get('gateway', '')
            config['network']['dns'] = network_data.get('dns', '')
            config['network']['wifi_ssid'] = network_data.get('wifi_ssid', '')

            # Ne pas écraser le mot de passe WiFi s'il est vide (sécurité)
            wifi_password = network_data.get('wifi_password', '')
            if wifi_password and wifi_password.strip():
                config['network']['wifi_password'] = wifi_password
                logger.info("Mot de passe WiFi mis à jour")

        # Sauvegarder le fichier config.json
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)

        logger.info("Configuration sauvegardée avec succès")

        # Redémarrer le monitoring si la fréquence ou le gain a changé
        needs_restart = ('rtl_sdr' in data and
                        ('frequency' in data['rtl_sdr'] or 'gain' in data['rtl_sdr']))
        if needs_restart and monitor:
            logger.info("Fréquence/gain modifié - redémarrage du monitoring")
            monitor.stop()
            time.sleep(2)
            monitor.config = config
            monitor.rtl_config = config['rtl_sdr']
            monitor.audio_config = config['audio']
            monitor.start()

        # Appliquer la configuration réseau si elle a été modifiée
        if 'network' in data:
            try:
                import os
                script_path = os.path.join(os.path.dirname(__file__), 'apply_network.sh')

                logger.info(f"Application de la configuration réseau via {script_path}")

                result = subprocess.run(
                    ['sudo', script_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if result.returncode == 0:
                    logger.info("Configuration réseau appliquée avec succès")
                    logger.info(result.stdout)
                else:
                    logger.error(f"Erreur lors de l'application de la config réseau: {result.stderr}")
                    # Ne pas faire échouer la sauvegarde si l'application réseau échoue

            except subprocess.TimeoutExpired:
                logger.error("Timeout lors de l'application de la configuration réseau (30s)")
            except Exception as e:
                logger.error(f"Erreur lors de l'application de la config réseau: {str(e)}")

        return jsonify({'status': 'success', 'message': 'Configuration enregistrée'})

    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de la config: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/presets')
@auth.login_required
def get_presets():
    """Retourne la liste des presets"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        return jsonify(config.get('presets', []))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs')
@auth.login_required
def get_logs():
    """Récupère les derniers logs système"""
    try:
        import subprocess
        result = subprocess.run(
            ['journalctl', '-u', 'fm-monitor', '-n', '100', '--no-pager'],
            capture_output=True,
            text=True
        )
        return jsonify({'logs': result.stdout})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-email', methods=['POST'])
@auth.login_required
def test_email():
    """Envoie un email de test"""
    try:
        if monitor and monitor.email_alert:
            success = monitor.email_alert.send_alert(
                alert_type="Test",
                details="Ceci est un email de test depuis FM Monitor."
            )
            if success:
                return jsonify({'status': 'success', 'message': 'Email envoyé'})
            else:
                return jsonify({'status': 'error', 'message': "Erreur d'envoi"}), 500
        return jsonify({'status': 'error', 'message': 'Monitor not initialized'}), 503
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/audio/history')
@auth.login_required
@limiter.exempt  # Exemption rate limiting pour historique appelé fréquemment
def get_audio_history():
    """Récupère l'historique des niveaux audio (24h)"""
    try:
        if monitor and hasattr(monitor, 'db'):
            history = monitor.db.get_audio_history(hours=24)
            return jsonify({'status': 'success', 'data': history})
        return jsonify({'status': 'error', 'message': 'Database not available'}), 503
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/alerts/history')
@auth.login_required
def get_alerts_history():
    """Récupère l'historique des alertes"""
    try:
        if monitor and hasattr(monitor, 'db'):
            alerts = monitor.db.get_alerts_history(limit=50)
            return jsonify({'status': 'success', 'data': alerts})
        return jsonify({'status': 'error', 'message': 'Database not available'}), 503
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/alerts/history/grouped')
@auth.login_required
def get_alerts_history_grouped():
    """Récupère l'historique des alertes groupées par paires"""
    try:
        if monitor and hasattr(monitor, 'db'):
            alerts = monitor.db.get_alerts_history_grouped(limit=50)
            return jsonify({'status': 'success', 'data': alerts})
        return jsonify({'status': 'error', 'message': 'Database not available'}), 503
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/restart', methods=['POST'])
@auth.login_required
def restart_monitoring():
    """Redémarre le monitoring"""
    global monitor
    try:
        if monitor:
            logger.info("Redémarrage du monitoring demandé")
            monitor.stop()
            time.sleep(2)
            monitor.start()
            return jsonify({'status': 'success', 'message': 'Monitoring redémarré'})
        return jsonify({'status': 'error', 'message': 'Monitor not initialized'}), 503
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/rds/read_ps', methods=['POST'])
@auth.login_required
def read_rds_ps():
    """Lecture ponctuelle PS et RT"""
    try:
        monitor.read_rds_once(duration=10)
        return jsonify({
            'status': 'success',
            'ps': monitor.stats.get('ps', '-'),
            'rt': monitor.stats.get('rt', '-')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/rds/read_rt', methods=['POST'])
@auth.login_required
def read_rds_rt():
    """Lecture ponctuelle du RadioText"""
    try:
        monitor.read_rds_once(duration=10)
        return jsonify({'status': 'success', 'rt': monitor.stats.get('rt', 'Non disponible')})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# =============================================
# PAGE À PROPOS
# =============================================

@app.route('/about')
@auth.login_required
def about_page():
    """Page de documentation"""
    return render_template('about.html')

@app.route('/stream.mp3')
@limiter.exempt  # Exemption rate limiting pour le stream audio
def proxy_stream():
    """Proxifie le stream Icecast HTTPS via Flask"""
    import requests

    def generate():
        try:
            # Connexion au stream Icecast en HTTPS (verify=False car certificat auto-signé)
            with requests.get('http://localhost:8000/fmmonitor', stream=True, timeout=5) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
        except Exception as e:
            logger.error(f"Erreur proxy stream: {e}")

    return app.response_class(
        generate(),
        mimetype='audio/mpeg',
        headers={
            'Cache-Control': 'no-cache, no-store',
            'X-Content-Type-Options': 'nosniff',
            'Access-Control-Allow-Origin': '*'
        }
    )

if __name__ == '__main__':
    try:
        monitor = FMMonitor('config.json')
        monitor.start()

        # Détection automatique du SSL
        ssl_context = None
        cert_file = 'cert.pem'
        key_file = 'key.pem'

        if os.path.exists(cert_file) and os.path.exists(key_file):
            ssl_context = (cert_file, key_file)
            logger.info("✅ Certificats SSL détectés - HTTPS activé")
            logger.info(f"Démarrage du serveur Flask en HTTPS sur https://0.0.0.0:5000")
        else:
            logger.info("⚠️  Certificats SSL non trouvés - HTTP non sécurisé")
            logger.info("   Pour activer HTTPS, générez les certificats avec: ./generate_ssl.sh")
            logger.info(f"Démarrage du serveur Flask en HTTP sur http://0.0.0.0:5000")

        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True,
            ssl_context=ssl_context
        )
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
        if monitor:
            monitor.stop()
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        if monitor:
            monitor.stop()
