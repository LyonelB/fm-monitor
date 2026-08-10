#!/usr/bin/env python3
"""
patch_scan_fmdx.py — Corrige la détection du TEF Headless (FMDX.org) dans app.py.

Problème :
    scan_dongle() envoie un handshake PE5PVB (write b'x' + attente 'OK'/'T8'/'Ss').
    Le firmware FM-DX-Tuner (kkonradpl) du Headless Lite ne répond pas ces chaînes,
    donc le port /dev/ttyACM0 est ouvert, testé, puis rejeté → « aucun dongle ».

Correctif :
    Remplace la boucle de probe série par une détection déterministe VID:PID
    (1209:6687 = FMDX.org TEF668X Headless), confirmée via lsusb. Le probe série
    PE5PVB est conservé en fallback pour un éventuel TEF6686 CH340 sur ttyUSB*.

Sécurités : sauvegarde .bak, validation AST (compile) avant écriture.
"""

import ast
import shutil
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent / "app.py"

# --- Bloc original à remplacer (probe série PE5PVB) ---------------------------
OLD = """    # Scan TEF sur ttyUSB* et ttyACM*
    ports = sorted(glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*'))
    for port in ports:
        try:
            s = _serial.Serial(port, 115200, timeout=2)
            s.reset_input_buffer()
            s.write(b'x')
            import time; time.sleep(0.8)
            data = s.read(200).decode('ascii', errors='ignore')
            s.close()
            if 'OK' in data or 'T8' in data or 'Ss' in data:
                result['tef'].append(port)
        except Exception:
            pass"""

# --- Nouveau bloc : détection VID:PID + fallback série ------------------------
NEW = """    # Détection TEF Headless FMDX.org par VID:PID (déterministe).
    # 1209:6687 = FMDX.org TEF668X Headless (firmware FM-DX-Tuner, port CDC-ACM).
    import subprocess as _sp
    fmdx_present = False
    try:
        _lsusb = _sp.run(['lsusb'], capture_output=True, text=True, timeout=5)
        if '1209:6687' in (_lsusb.stdout + _lsusb.stderr):
            fmdx_present = True
    except Exception:
        pass
    # Associe le VID:PID à son /dev/ttyACM* (le firmware s'énumère en CDC-ACM).
    acm_ports = sorted(glob.glob('/dev/ttyACM*'))
    if fmdx_present:
        result['tef'].extend(acm_ports if acm_ports else ['/dev/ttyACM0'])
    # Fallback : probe série PE5PVB pour un TEF6686 CH340 sur ttyUSB* (ancien montage).
    usb_ports = sorted(glob.glob('/dev/ttyUSB*'))
    for port in usb_ports:
        try:
            s = _serial.Serial(port, 115200, timeout=2)
            s.reset_input_buffer()
            s.write(b'x')
            import time; time.sleep(0.8)
            data = s.read(200).decode('ascii', errors='ignore')
            s.close()
            if 'OK' in data or 'T8' in data or 'Ss' in data:
                result['tef'].append(port)
        except Exception:
            pass
    # Dédoublonnage en préservant l'ordre.
    result['tef'] = list(dict.fromkeys(result['tef']))"""


def main():
    if not APP.exists():
        sys.exit(f"ERREUR : {APP} introuvable. Lance le patch depuis ~/fm-monitor.")

    src = APP.read_text(encoding="utf-8")

    if OLD not in src:
        if "1209:6687" in src:
            sys.exit("Le patch semble déjà appliqué (1209:6687 présent). Rien à faire.")
        sys.exit(
            "ERREUR : bloc de probe attendu introuvable dans app.py.\n"
            "Le code a peut-être changé — vérifie scan_dongle() autour de la ligne 776."
        )

    patched = src.replace(OLD, NEW, 1)

    # Validation syntaxique avant d'écrire quoi que ce soit.
    try:
        ast.parse(patched)
    except SyntaxError as e:
        sys.exit(f"ERREUR : le code patché ne compile pas ({e}). Aucune écriture.")

    bak = APP.with_suffix(".py.bak")
    shutil.copy2(APP, bak)
    APP.write_text(patched, encoding="utf-8")
    print(f"OK — app.py patché. Sauvegarde : {bak.name}")
    print("Détection TEF désormais par VID:PID 1209:6687 (+ fallback ttyUSB PE5PVB).")


if __name__ == "__main__":
    main()
