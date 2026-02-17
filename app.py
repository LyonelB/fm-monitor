#!/usr/bin/env python3
"""
Application Flask pour le monitoring FM
"""
from flask import Flask, render_template, Response, jsonify, request, session, redirect, url_for
import logging
import time
import json
from monitor import FMMonitor
from auth import Auth

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'fm-monitor-secret-key-changez-moi-en-production'
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
def login():
    """Page de connexion"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if auth.verify_credentials(username, password):
            session['logged_in'] = True
            session['username'] = username
            next_page = request.args.get('next', '/')
            logger.info(f"Connexion réussie pour {username}")
            return redirect(next_page)
        else:
            logger.warning(f"Tentative de connexion échouée pour {username}")
            return render_template('login.html', error='Identifiants incorrects')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Déconnexion"""
    username = session.get('username', 'unknown')
    session.clear()
    logger.info(f"Déconnexion de {username}")
    return redirect(url_for('login'))

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

@app.route('/stream.mp3')
@auth.login_required
def stream():
    """Stream audio en direct"""
    def generate():
        logger.info("Client connecté au stream audio")
        try:
            while True:
                if monitor and monitor.running:
                    chunk = monitor.get_audio_chunk()
                    if chunk:
                        yield chunk
                    else:
                        time.sleep(0.05)
                else:
                    break
        except GeneratorExit:
            logger.info("Client déconnecté du stream audio")
        except Exception as e:
            logger.error(f"Erreur de streaming: {e}")

    response = Response(
        generate(),
        mimetype='audio/mpeg',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Content-Type-Options': 'nosniff'
        }
    )
    return response

@app.route('/api/stats')
@auth.login_required
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
@auth.login_required
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
@auth.login_required
def get_services_status():
    """Retourne l'état de tous les services"""
    if monitor:
        return jsonify({'status': 'success', 'services': monitor.get_services_status()})
    return jsonify({'status': 'error', 'message': 'Monitor not initialized'}), 503

@app.route('/api/services/toggle', methods=['POST'])
@auth.login_required
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
@auth.login_required
def get_config_full():
    """Retourne la configuration complète"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
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

        if 'frequency' in data:
            config['rtl_sdr']['frequency'] = data['frequency']
            config['station']['frequency'] = data['frequency']

        if 'station_name' in data:
            config['station']['name'] = data['station_name']

        if 'gain' in data:
            gain = data['gain'].strip()
            if gain != 'auto' and gain != '':
                try:
                    gain_float = float(gain)
                    if gain_float < 0 or gain_float > 49.6:
                        return jsonify({'status': 'error', 'message': 'Le gain doit être entre 0 et 49.6 ou "auto"'}), 400
                except ValueError:
                    return jsonify({'status': 'error', 'message': 'Gain invalide'}), 400
            config['rtl_sdr']['gain'] = gain

        if 'silence_threshold' in data:
            config['audio']['silence_threshold'] = float(data['silence_threshold'])

        if 'silence_duration' in data:
            config['audio']['silence_duration'] = int(data['silence_duration'])

        if 'sender_email' in data:
            config['email']['sender_email'] = data['sender_email']

        if 'sender_password' in data:
            config['email']['sender_password'] = data['sender_password']

        if 'recipient_emails' in data:
            emails = data['recipient_emails']
            if isinstance(emails, str):
                emails = [e.strip() for e in emails.split(',') if e.strip()]
            config['email']['recipient_emails'] = emails

        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)

        logger.info("Configuration sauvegardée avec succès")
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

if __name__ == '__main__':
    try:
        monitor = FMMonitor('config.json')
        monitor.start()

        logger.info("Démarrage du serveur Flask sur 0.0.0.0:5000")
        app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("Arrêt demandé par l'utilisateur")
        if monitor:
            monitor.stop()
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        if monitor:
            monitor.stop()
