import subprocess
import threading
import json
import time
import os
import numpy as np
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# État global pour stocker les données affichées sur le Web
state = {
    "level": -90.0,
    "ps": "RECHERCHE...",
    "rt": "Attente de données RDS...",
}

def master_monitor():
    """
    Lance une seule instance de rtl_fm pour éviter les conflits USB.
    Utilise 'tee' pour envoyer le flux à redsea et au calcul du vumètre simultanément.
    """
    # Nettoyage des processus qui pourraient bloquer la clé SDR
    os.system("pkill -9 rtl_fm")
    os.system("pkill -9 redsea")
    time.sleep(1)

    # Commande maître : 
    # 1. Capture en 171k (indispensable pour le RDS)
    # 2. tee duplique le flux : 
    #    - Un bras vers redsea qui écrit le JSON dans /tmp/rds_output.json
    #    - Un bras vers stdout pour le calcul du vumètre en Python
    cmd = (
        "stdbuf -o0 rtl_fm -f 88.6M -M wbfm -s 171k -r 171k -A fast | "
        "tee >(stdbuf -oL redsea -p > /tmp/rds_output.json) | "
        "cat"
    )
    
    # Lancement du processus (nécessite bash pour la syntaxe >() )
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, executable='/bin/bash')

    def rds_reader():
        """Thread qui lit les dernières lignes JSON produites par redsea"""
        while not os.path.exists("/tmp/rds_output.json"):
            time.sleep(0.5)
            
        # On utilise tail pour lire uniquement les nouvelles lignes
        with subprocess.Popen(["tail", "-f", "-n", "1", "/tmp/rds_output.json"], 
                             stdout=subprocess.PIPE, text=True) as tail_proc:
            for line in tail_proc.stdout:
                try:
                    data = json.loads(line)
                    # Mise à jour du Program Service (Nom de la radio)
                    if 'ps' in data: 
                        state['ps'] = str(data['ps']).strip()
                    # Mise à jour du RadioText (Titre, Artiste, etc.)
                    if 'radiotext' in data: 
                        state['rt'] = str(data['radiotext']).strip()
                    elif 'partial_radiotext' in data:
                        state['rt'] = str(data['partial_radiotext']).strip() + "..."
                except:
                    continue

    # Lancement du thread de lecture RDS
    threading.Thread(target=rds_reader, daemon=True).start()

    # Boucle principale : Calcul du vumètre sur le flux de sortie de 'tee'
    while True:
        # Lecture de 2048 samples (4096 octets car 16-bit)
        raw_data = proc.stdout.read(4096)
        if not raw_data:
            break
        
        samples = np.frombuffer(raw_data, dtype=np.int16)
        if len(samples) > 0:
            # Calcul RMS et conversion en dBFS
            rms = np.sqrt(np.mean(np.square(samples.astype(np.float32))))
            db = 20 * np.log10(rms / 32768.0) if rms > 0 else -90.0
            # Conversion forcée en float Python standard pour éviter l'erreur JSON
            state["level"] = float(db)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    return jsonify(state)

# Template HTML intégré
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>MONITEUR RDS & AUDIO</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@700&family=Roboto:wght@400;900&display=swap" rel="stylesheet">
    <style>
        body { background: #0a0a0b; color: #fff; font-family: 'Roboto', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .card { width: 90%; max-width: 850px; background: #111; padding: 40px; border-radius: 25px; border: 1px solid #222; box-shadow: 0 30px 60px rgba(0,0,0,0.5); }
        .label { color: #444; text-transform: uppercase; font-size: 12px; font-weight: 900; letter-spacing: 2px; }
        .ps { font-family: 'Roboto Mono'; font-size: 110px; color: #00ff66; margin-bottom: 20px; line-height: 1; text-shadow: 0 0 20px rgba(0,255,102,0.2); }
        .rt { font-size: 22px; color: #ffcc00; background: rgba(255,204,0,0.05); padding: 20px; border-radius: 12px; min-height: 1.5em; border-left: 6px solid #ffcc00; margin-bottom: 30px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .vu-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 10px; }
        .db-val { font-family: 'Roboto Mono'; font-size: 40px; color: #00ff66; }
        .vu-container { height: 50px; background: #000; border-radius: 8px; border: 1px solid #333; padding: 5px; }
        #vu-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #00ff66 75%, #ffcc00 90%, #ff4d4d 100%); transition: width 0.05s linear; }
    </style>
</head>
<body>
    <div class="card">
        <div class="label">Station (PS)</div>
        <div class="ps" id="ps">ATTENTE...</div>
        
        <div class="label">RadioText (RT)</div>
        <div class="rt" id="rt">Initialisation du flux...</div>
        
        <div class="vu-header">
            <div class="label">Peak Level</div>
            <div class="db-val" id="db-val">-90.00 dBFS</div>
        </div>
        <div class="vu-container"><div id="vu-fill"></div></div>
    </div>
    <script>
        async function update() {
            try {
                const res = await fetch('/api/data');
                const d = await res.json();
                document.getElementById('ps').innerText = d.ps;
                document.getElementById('rt').innerText = d.rt;
                document.getElementById('db-val').innerText = d.level.toFixed(2);
                
                // Calcul du pourcentage pour le vumètre (-60dB à 0dB)
                let pct = ((d.level + 60) / 60) * 100;
                document.getElementById('vu-fill').style.width = Math.min(100, Math.max(0, pct)) + "%";
                
                // Couleur dynamique selon le niveau
                const val = document.getElementById('db-val');
                if(d.level > -6) val.style.color = "#ff4d4d";
                else if(d.level > -18) val.style.color = "#ffcc00";
                else val.style.color = "#00ff66";
            } catch(e) {}
        }
        setInterval(update, 50);
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    # Démarrage du thread SDR
    threading.Thread(target=master_monitor, daemon=True).start()
    # Lancement du serveur Web
    app.run(host='0.0.0.0', port=5001, debug=False)
