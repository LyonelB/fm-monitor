#!/usr/bin/env python3
"""
patch_tef_three_alerts.py

Restructure la détection de perte de signal en MODE TEF uniquement.

Contexte (établi par mesures sur TEF Lite SE / firmware FM-DX-Tuner) :
  - Le champ dBf ne distingue pas antenne présente/absente (plancher ~46 dBf
    par couplage). Le seuil `signal_threshold_dbf` est donc inexploitable.
  - En revanche, le firmware n'émet des trames `Ss` QUE lorsqu'il capte un
    signal : ~15 trames/s en réception normale, ~0 sur une fréquence vide.
  - Le DÉBIT de trames `Ss` est donc le vrai détecteur de présence signal.

Ce que fait le patch :
  1. _on_tef_signal : horodate chaque trame `Ss` dans une fenêtre glissante
     (self.tef_ss_times) et consolide le doublon de bloc stats_lock.
  2. Bloc 1 (détection perte signal), branche TEF (else) UNIQUEMENT :
     remplace `signal_lost = not self.signal_ok` par un comptage de trames :
     perte si moins de `signal_frame_min` trames sur `signal_frame_window` s.
     >>> La branche RTL-SDR (if not self.use_tef) n'est PAS modifiée. <<<
  3. Bloc 2 (modulation TEF) : retire la dépendance `self.signal_ok and`
     pour rendre la surveillance modulation indépendante.
  4. __init__ : ajoute les paramètres config TEF signal_frame_window (30)
     et signal_frame_min (5).

Sécurités : sauvegarde .bak, validation AST (compile) avant écriture,
idempotent (ne réapplique pas si déjà patché).

⚠ Le chemin RTL-SDR reste strictement inchangé.
"""

import ast
import shutil
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent / "monitor.py"

# ─────────────────────────────────────────────────────────────────────────
# Fragment 1 — init des paramètres de fenêtre (ajouté après rt_timeout)
# ─────────────────────────────────────────────────────────────────────────
INIT_ANCHOR = (
    "        self.rt_timeout = int(self.audio_config.get('rt_timeout', 300))"
    "  # 5 min par défaut"
)
INIT_ADD = """
        # Détection présence signal en mode TEF : débit de trames Ss.
        # Le firmware n'émet des trames Ss que s'il capte un signal.
        self.tef_ss_times = []  # horodatages des trames Ss (fenêtre glissante)
        self.signal_frame_window = int(self.tef_config.get('signal_frame_window', 30))
        self.signal_frame_min = int(self.tef_config.get('signal_frame_min', 5))"""

# ─────────────────────────────────────────────────────────────────────────
# Fragment 2 — _on_tef_signal : consolidation + horodatage
# On remplace les DEUX blocs stats_lock consécutifs par un seul, et on
# ajoute l'enregistrement du timestamp de la trame.
# ─────────────────────────────────────────────────────────────────────────
OLD_ONSIGNAL = """        signal_ok  = dbf >= threshold
        with self.stats_lock:
            self.stats['current_level']    = dbf
            self.stats['signal_dbf']       = dbf
            self.stats['snr']              = snr
            self.stats['multipath']        = multipath
            self.stats['freq_offset']      = offset
            self.stats['modulation_active'] = signal_ok
        self.signal_ok = signal_ok
        # Normalisation pour le VU-mètre du dashboard (qui attend -100..0 dBFS)
        # On mappe dBf (0..60) vers (-60..0) : valeur_display = dBf - 60
        with self.stats_lock:
            self.stats['current_level']     = dbf - 60.0
            self.stats['signal_dbf']        = dbf
            self.stats['snr']               = snr
            self.stats['multipath']         = multipath
            self.stats['freq_offset']       = offset
            self.stats['modulation_active'] = signal_ok"""

NEW_ONSIGNAL = """        signal_ok  = dbf >= threshold
        # Présence signal : on horodate chaque trame Ss (fenêtre glissante).
        # C'est le vrai détecteur de présence (le dBf seul n'est pas fiable).
        now = time.time()
        self.tef_ss_times.append(now)
        cutoff = now - self.signal_frame_window
        self.tef_ss_times = [t for t in self.tef_ss_times if t >= cutoff]
        # Normalisation pour le VU-mètre du dashboard (qui attend -100..0 dBFS)
        # On mappe dBf (0..60) vers (-60..0) : valeur_display = dBf - 60
        with self.stats_lock:
            self.stats['current_level']     = dbf - 60.0
            self.stats['signal_dbf']        = dbf
            self.stats['snr']               = snr
            self.stats['multipath']         = multipath
            self.stats['freq_offset']       = offset
            self.stats['modulation_active'] = signal_ok
        self.signal_ok = signal_ok"""

# ─────────────────────────────────────────────────────────────────────────
# Fragment 3 — Bloc 1 : détection perte signal, branche TEF (else) seule.
# On NE touche PAS à la branche `if not self.use_tef:` (RTL-SDR).
# ─────────────────────────────────────────────────────────────────────────
OLD_SIGNAL_LOST = """                else:
                    signal_lost = not self.signal_ok

                if signal_lost:"""

NEW_SIGNAL_LOST = """                else:
                    # Mode TEF : présence signal = débit de trames Ss.
                    # Le firmware n'émet des trames que s'il capte un signal ;
                    # moins de signal_frame_min trames sur la fenêtre = perte.
                    now = time.time()
                    cutoff = now - self.signal_frame_window
                    recent_ss = [t for t in self.tef_ss_times if t >= cutoff]
                    signal_lost = len(recent_ss) < self.signal_frame_min

                if signal_lost:"""

# ─────────────────────────────────────────────────────────────────────────
# Fragment 4 — Bloc 2 : modulation TEF indépendante (retrait de signal_ok).
# ─────────────────────────────────────────────────────────────────────────
OLD_MODULATION = """                    no_modulation = (
                        self.signal_ok and
                        mpx_power < self.tef_modulation_threshold and
                        mpx_power > -100.0  # -100 = pas encore de données
                    )"""

NEW_MODULATION = """                    no_modulation = (
                        mpx_power < self.tef_modulation_threshold and
                        mpx_power > -100.0  # -100 = pas encore de données
                    )"""


FRAGMENTS = [
    ("init paramètres fenêtre", INIT_ANCHOR, INIT_ANCHOR + INIT_ADD),
    ("_on_tef_signal", OLD_ONSIGNAL, NEW_ONSIGNAL),
    ("bloc 1 détection TEF", OLD_SIGNAL_LOST, NEW_SIGNAL_LOST),
    ("bloc 2 modulation", OLD_MODULATION, NEW_MODULATION),
]


def main():
    if not APP.exists():
        sys.exit(f"ERREUR : {APP} introuvable. Lance le patch depuis ~/fm-monitor.")

    src = APP.read_text(encoding="utf-8")

    if "tef_ss_times" in src:
        sys.exit("Le patch semble déjà appliqué (tef_ss_times présent). Rien à faire.")

    patched = src
    for label, old, new in FRAGMENTS:
        count = patched.count(old)
        if count == 0:
            sys.exit(
                f"ERREUR : fragment '{label}' introuvable dans monitor.py.\n"
                f"Le code a peut-être changé — aucune écriture effectuée."
            )
        if count > 1:
            sys.exit(
                f"ERREUR : fragment '{label}' trouvé {count} fois (ambigu).\n"
                f"Aucune écriture effectuée."
            )
        patched = patched.replace(old, new, 1)

    # Validation syntaxique avant d'écrire quoi que ce soit.
    try:
        ast.parse(patched)
    except SyntaxError as e:
        sys.exit(f"ERREUR : le code patché ne compile pas ({e}). Aucune écriture.")

    bak = APP.with_suffix(".py.bak")
    shutil.copy2(APP, bak)
    APP.write_text(patched, encoding="utf-8")
    print(f"OK — monitor.py patché. Sauvegarde : {bak.name}")
    print("Mode TEF : présence signal via débit de trames Ss "
          "(< {min} trames / {win}s).".format(min="signal_frame_min",
                                               win="signal_frame_window"))
    print("Modulation TEF désormais indépendante. RTL-SDR inchangé.")


if __name__ == "__main__":
    main()
