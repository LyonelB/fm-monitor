#!/usr/bin/env python3
"""
patch_hide_mpx_spectrum_tef.py

Masque le bloc « Spectre MPX » de la colonne gauche (sous Signal RF) quand le
mode TEF est actif — il est vide en TEF (plus de MPX brut), le spectre audio
étant désormais affiché dans le panneau de droite.

Modifs (templates/index.html uniquement) :
  1. Donne l'id #mpx-spectrum-block au conteneur du spectre MPX gauche.
  2. Dans updateAnalysisPanel : masque ce bloc en TEF, l'affiche en RTL-SDR.

Le masquage en display:none fait remonter naturellement le player.
Mode RTL-SDR inchangé (le bloc reste visible). Idempotent, .bak.
"""

import sys
import shutil
from pathlib import Path

IDX = Path(__file__).resolve().parent / "templates" / "index.html"

OLD_BLOCK = """          <!-- Spectre MPX -->
          <div class="mb-3">"""
NEW_BLOCK = """          <!-- Spectre MPX (masqué en mode TEF) -->
          <div id="mpx-spectrum-block" class="mb-3">"""

OLD_JS = """      if (isTEF) {
        if (pMpx) pMpx.classList.add('hidden');
        if (pAud) pAud.classList.remove('hidden');
        updateAudioTEF(stats);
      } else {
        if (pAud) pAud.classList.add('hidden');
        if (pMpx) pMpx.classList.remove('hidden');
        updateMPX(stats);
      }"""
NEW_JS = """      const specBlock = document.getElementById('mpx-spectrum-block');
      if (isTEF) {
        if (pMpx) pMpx.classList.add('hidden');
        if (pAud) pAud.classList.remove('hidden');
        if (specBlock) specBlock.classList.add('hidden');
        updateAudioTEF(stats);
      } else {
        if (pAud) pAud.classList.add('hidden');
        if (pMpx) pMpx.classList.remove('hidden');
        if (specBlock) specBlock.classList.remove('hidden');
        updateMPX(stats);
      }"""


def main():
    if not IDX.exists():
        sys.exit(f"ERREUR : {IDX} introuvable.")
    src = IDX.read_text(encoding="utf-8")
    if "mpx-spectrum-block" in src:
        sys.exit("Le patch semble déjà appliqué (mpx-spectrum-block présent). Rien à faire.")

    patched = src
    for label, old, new in [("bloc spectre", OLD_BLOCK, NEW_BLOCK), ("logique JS", OLD_JS, NEW_JS)]:
        c = patched.count(old)
        if c == 0:
            sys.exit(f"ERREUR : fragment '{label}' introuvable (le patch front a-t-il été appliqué ?). Aucune écriture.")
        if c > 1:
            sys.exit(f"ERREUR : fragment '{label}' trouvé {c} fois (ambigu). Aucune écriture.")
        patched = patched.replace(old, new, 1)

    # Cohérence : div toujours équilibrés
    if patched.count("<div") != patched.count("</div>"):
        sys.exit("ERREUR : déséquilibre des balises div après patch. Aucune écriture.")

    bak = IDX.with_suffix(".html.bak")
    shutil.copy2(IDX, bak)
    IDX.write_text(patched, encoding="utf-8")
    print(f"OK — index.html patché. Sauvegarde : {bak.name}")
    print("Bloc Spectre MPX (gauche) masqué en mode TEF.")


if __name__ == "__main__":
    main()
