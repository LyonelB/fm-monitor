#!/usr/bin/env python3
"""
patch_tef_audio_spectrum.py

Ajoute un spectre audio FFT (0–20 kHz) à TEFAudioAnalyzer, pour alimenter
l'affichage du spectre audio dans le dashboard (mode TEF).

Réutilise la FFT déjà calculée dans _process() (pour le SNR) : coût CPU
quasi nul. Le spectre est décimé à ~256 points sur 0–20 kHz, converti en dB,
et publié sous la clé 'fft_spectrum' des résultats. La route existante
/api/mpx/spectrum le renverra automatiquement (elle lit monitor.mpx_analyzer,
qui EST le TEFAudioAnalyzer en mode TEF).

Modifs :
  1. __init__ : bornes du spectre (0–20 kHz), nombre de points, hz/point,
     et 'fft_spectrum':[] dans les résultats initiaux.
  2. _process : calcule le spectre dB décimé et le publie.
  3. reset : remet fft_spectrum à [].

Sécurités : .bak, validation AST, idempotent.
Aucune incidence sur le mode RTL-SDR (fichier propre au TEF).
"""

import ast
import shutil
import sys
from pathlib import Path

F = Path(__file__).resolve().parent / "tef_audio_analyzer.py"

# ── 1. __init__ : ajouter les paramètres spectre + clé résultat ───────────
INIT_OLD = """        self._noise_lo=int(15000/freq_res); self._noise_hi=int(23000/freq_res)
        self._results={'mpx_enabled':True,'deviation_peak':0.0,'deviation_rms':0.0,
            'mpx_power':-100.0,'pilot_level':-100.0,'pilot_present':False,
            'stereo_level':-100.0,'stereo_present':False,'rds_level':-100.0,
            'rds_rf_present':False,'level_left':-100.0,'level_right':-100.0,'snr':0.0}"""

INIT_NEW = """        self._noise_lo=int(15000/freq_res); self._noise_hi=int(23000/freq_res)
        # Spectre audio pour l'affichage : 0-20 kHz décimé en ~256 points.
        self._spec_freq_res=freq_res
        self._spec_hi=int(20000/freq_res)          # dernier bin utile (20 kHz)
        self._spec_points=256                       # points envoyés au front
        self.spectrum_hz_per_point=20000.0/self._spec_points
        self._results={'mpx_enabled':True,'deviation_peak':0.0,'deviation_rms':0.0,
            'mpx_power':-100.0,'pilot_level':-100.0,'pilot_present':False,
            'stereo_level':-100.0,'stereo_present':False,'rds_level':-100.0,
            'rds_rf_present':False,'level_left':-100.0,'level_right':-100.0,'snr':0.0,
            'fft_spectrum':[]}"""

# ── 2. _process : publier le spectre dB décimé ────────────────────────────
PROC_OLD = """            snr=float(np.clip(10.0*np.log10(sig/noise),0.0,80.0))
            with self._lock:
                self._results.update({'mpx_power':round(mpx_db,1),'level_left':round(l_db,1),
                    'level_right':round(r_db,1),'snr':round(snr,1),
                    'stereo_level':-100.0,'pilot_level':-100.0,'pilot_present':False,
                    'rds_level':-100.0,'rds_rf_present':False})"""

PROC_NEW = """            snr=float(np.clip(10.0*np.log10(sig/noise),0.0,80.0))
            # Spectre audio 0-20 kHz → dB, décimé en _spec_points pour le front.
            band=fft[:self._spec_hi]
            if len(band)>0:
                # Puissance → dB (référence pleine échelle), plancher -100 dB.
                power=band**2
                idx=np.linspace(0,len(power),self._spec_points+1).astype(int)
                decim=np.array([power[idx[k]:idx[k+1]].max() if idx[k+1]>idx[k] else 1e-20
                                for k in range(self._spec_points)])
                spec_db=10.0*np.log10(decim/(len(M)*0.5)**2+1e-12)
                spec_db=np.clip(spec_db,-100.0,0.0)
                fft_spectrum=[round(float(v),1) for v in spec_db]
            else:
                fft_spectrum=[]
            with self._lock:
                self._results.update({'mpx_power':round(mpx_db,1),'level_left':round(l_db,1),
                    'level_right':round(r_db,1),'snr':round(snr,1),
                    'stereo_level':-100.0,'pilot_level':-100.0,'pilot_present':False,
                    'rds_level':-100.0,'rds_rf_present':False,
                    'fft_spectrum':fft_spectrum})"""

# ── 3. reset : remettre fft_spectrum à [] ─────────────────────────────────
RESET_OLD = """                'level_left':-100.0,'level_right':-100.0,'snr':0.0})"""
RESET_NEW = """                'level_left':-100.0,'level_right':-100.0,'snr':0.0,'fft_spectrum':[]})"""


def main():
    if not F.exists():
        sys.exit(f"ERREUR : {F} introuvable. Lance depuis ~/fm-monitor.")
    src = F.read_text(encoding="utf-8")
    if "fft_spectrum" in src:
        sys.exit("Le patch semble déjà appliqué (fft_spectrum présent). Rien à faire.")

    patched = src
    for label, old, new in [
        ("init", INIT_OLD, INIT_NEW),
        ("_process", PROC_OLD, PROC_NEW),
        ("reset", RESET_OLD, RESET_NEW),
    ]:
        c = patched.count(old)
        if c == 0:
            sys.exit(f"ERREUR : fragment '{label}' introuvable. Aucune écriture.")
        if c > 1:
            sys.exit(f"ERREUR : fragment '{label}' trouvé {c} fois (ambigu). Aucune écriture.")
        patched = patched.replace(old, new, 1)

    try:
        ast.parse(patched)
    except SyntaxError as e:
        sys.exit(f"ERREUR : code patché invalide ({e}). Aucune écriture.")

    bak = F.with_suffix(".py.bak")
    shutil.copy2(F, bak)
    F.write_text(patched, encoding="utf-8")
    print(f"OK — tef_audio_analyzer.py patché. Sauvegarde : {bak.name}")
    print("Spectre audio 0-20 kHz (256 pts) publié sous 'fft_spectrum'.")


if __name__ == "__main__":
    main()
