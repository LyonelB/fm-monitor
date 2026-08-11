#!/usr/bin/env python3
"""
patch_front_tef_audio.py

Ajoute un panneau « Analyse audio » propre au mode TEF, affiché à la place du
panneau « Analyse MPX » quand le TEF Lite SE est actif. Le panneau MPX
(RTL-SDR) et sa fonction updateMPX ne sont PAS modifiés (Stratégie A).

Touche deux fichiers :

  monitor.py
    - get_stats() : expose 'use_tef' dans les stats (pour que le front sache
      quel panneau afficher, sans deviner via signal_dbf).

  templates/index.html
    1. Ajoute le panneau #panel-audio-tef (structure validée en maquette :
       spectre audio 0-20 kHz, Qualité audio (S/B), Puissance MPX, niveaux L/R)
       juste après le panneau MPX existant, et donne l'id #panel-mpx-rtlsdr au
       panneau MPX pour pouvoir basculer.
    2. Ajoute les fonctions JS :
         - updateAnalysisPanel(stats) : choisit le panneau selon stats.use_tef
         - updateAudioTEF(stats)      : alimente le panneau TEF
         - drawAudioSpectrum()        : rend le spectre audio 0-20 kHz
    3. Route le rendu du spectre : fetchMPXSpectrum appelle drawAudioSpectrum
       en mode TEF, drawMPXSpectrum sinon.
    4. Remplace les 2 appels updateMPX(stats) par updateAnalysisPanel(stats).

Sécurités : .bak par fichier, validation AST (monitor.py) et vérifs de
cohérence (index.html), idempotent.
⚠ Mode RTL-SDR et updateMPX inchangés.
"""

import ast
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
MON = BASE / "monitor.py"
IDX = BASE / "templates" / "index.html"


# ═══════════════════════════════════════════════════════════════════════
# monitor.py — exposer use_tef dans get_stats
# ═══════════════════════════════════════════════════════════════════════
MON_OLD = """        stats['rds_ever_received'] = self.rds_ever_received
        stats['frequency'] = self.rtl_config['frequency']"""
MON_NEW = """        stats['rds_ever_received'] = self.rds_ever_received
        stats['use_tef'] = self.use_tef
        stats['frequency'] = self.rtl_config['frequency']"""


# ═══════════════════════════════════════════════════════════════════════
# index.html — 1. Donner un id au panneau MPX + insérer le panneau TEF
# ═══════════════════════════════════════════════════════════════════════
IDX_OLD_PANEL_OPEN = """      <!-- ══ Col droite : Analyse MPX ══ -->
      <div class="card flex flex-col gap-3">"""
IDX_NEW_PANEL_OPEN = """      <!-- ══ Col droite : Analyse MPX (RTL-SDR) ══ -->
      <div id="panel-mpx-rtlsdr" class="card flex flex-col gap-3">"""

# Insertion du panneau TEF juste après la fermeture du panneau MPX.
IDX_OLD_PANEL_CLOSE = """      </div><!-- /col droite MPX -->
    </div><!-- /grille 2 cols -->"""

IDX_NEW_PANEL_CLOSE = """      </div><!-- /col droite MPX -->

      <!-- ══ Col droite : Analyse audio (TEF) ══ -->
      <div id="panel-audio-tef" class="card flex flex-col gap-3 hidden">
        <div class="flex items-center justify-between">
          <span class="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
            <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
            Analyse audio
          </span>
          <span id="audio-badge" class="text-xs font-bold uppercase tracking-wide px-2.5 py-0.5 rounded-full bg-gray-100 text-gray-400">&mdash;</span>
        </div>
        <div class="border-t border-gray-100"></div>
        <!-- Spectre audio 0-20 kHz -->
        <div>
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Spectre audio</span>
            <span class="text-xs text-gray-400 font-mono">0 &ndash; 20 kHz</span>
          </div>
          <canvas id="audio-spectrum-canvas" style="width:100%;height:150px;display:block;border-radius:4px;" width="600" height="150"></canvas>
        </div>
        <div class="border-t border-gray-100"></div>
        <!-- Qualité audio (S/B) + Puissance MPX -->
        <div style="display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto auto 6px auto;gap:0 12px;align-items:center">
          <div class="text-center text-xs font-semibold text-gray-600" style="margin-bottom:4px">Qualité audio <span class="font-normal text-gray-400">(S/B)</span></div>
          <div class="text-center text-xs font-semibold text-gray-600" style="margin-bottom:4px">Puissance <span class="font-normal text-gray-400">MPX</span></div>
          <div class="text-center text-sm font-mono font-semibold text-gray-800" style="margin-bottom:4px" id="audio-val-snr">&mdash; dB</div>
          <div class="text-center text-sm font-mono font-semibold text-gray-800" style="margin-bottom:4px" id="audio-val-power">&mdash; dBFS</div>
          <div class="rounded-full bg-gray-100 overflow-hidden" style="height:6px">
            <div id="audio-bar-snr" class="h-full w-0 rounded-full transition-all duration-150" style="background:#22c55e"></div>
          </div>
          <div class="rounded-full bg-gray-100 overflow-hidden" style="height:6px">
            <div id="audio-bar-power" class="h-full w-0 rounded-full bg-green-400 transition-all duration-150"></div>
          </div>
          <div class="flex justify-between text-xs text-gray-400 font-mono" style="margin-top:2px"><span>0</span><span>40</span><span>80 dB</span></div>
          <div class="flex justify-between text-xs text-gray-400 font-mono" style="margin-top:2px"><span>-50</span><span>0 dBFS</span></div>
        </div>
        <div class="border-t border-gray-100"></div>
        <!-- Niveaux L / R -->
        <div>
          <div class="flex justify-between items-baseline mb-1">
            <span class="text-xs font-semibold text-gray-600">Niveau <span class="font-normal text-gray-400">audio L / R</span></span>
            <span class="text-sm font-mono font-semibold text-gray-800"><span id="audio-val-l">&mdash;</span> / <span id="audio-val-r">&mdash;</span> dBFS</span>
          </div>
          <div class="flex gap-1.5">
            <div class="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden"><div id="audio-bar-l" class="vu-bar w-0 bg-blue-400" style="height:100%"></div></div>
            <div class="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden"><div id="audio-bar-r" class="vu-bar w-0 bg-blue-400" style="height:100%"></div></div>
          </div>
          <div class="flex justify-between text-xs text-gray-400 font-mono mt-0.5"><span>-60</span><span>0 dBFS</span></div>
        </div>
      </div><!-- /col droite audio TEF -->
    </div><!-- /grille 2 cols -->"""


# ═══════════════════════════════════════════════════════════════════════
# index.html — 2+3. Fonctions JS (insérées juste avant updateMPX)
# ═══════════════════════════════════════════════════════════════════════
IDX_OLD_JS_ANCHOR = "    function updateMPX(stats) {"
IDX_NEW_JS_BLOCK = """    // ── Panneau d'analyse : bascule TEF / RTL-SDR selon le mode ──────────
    function updateAnalysisPanel(stats) {
      const isTEF = stats.use_tef === true
                    || (stats.use_tef === undefined && stats.signal_dbf !== undefined && stats.signal_dbf !== null);
      const pMpx = document.getElementById('panel-mpx-rtlsdr');
      const pAud = document.getElementById('panel-audio-tef');
      if (isTEF) {
        if (pMpx) pMpx.classList.add('hidden');
        if (pAud) pAud.classList.remove('hidden');
        updateAudioTEF(stats);
      } else {
        if (pAud) pAud.classList.add('hidden');
        if (pMpx) pMpx.classList.remove('hidden');
        updateMPX(stats);
      }
    }

    function updateAudioTEF(stats) {
      // Puissance MPX (audio)
      const power    = stats.mpx_power ?? -100;
      const powerPct = Math.max(0, Math.min(100, (power + 50) / 50 * 100));
      const pBar = document.getElementById('audio-bar-power');
      const pVal = document.getElementById('audio-val-power');
      if (pBar) pBar.style.width = powerPct + '%';
      if (pVal) pVal.textContent = power.toFixed(1) + ' dBFS';
      // Qualité audio (S/B) — 0..80 dB
      const snr    = stats.snr ?? 0;
      const snrPct = Math.min((snr / 80) * 100, 100);
      const sVal = document.getElementById('audio-val-snr');
      const sBar = document.getElementById('audio-bar-snr');
      if (sVal) sVal.textContent = snr.toFixed(1) + ' dB';
      if (sBar) { sBar.style.width = snrPct + '%'; sBar.style.background = snr >= 40 ? '#22c55e' : snr >= 25 ? '#f59e0b' : '#ef4444'; }
      // Niveaux L / R (-60..0 dBFS)
      const l = stats.level_left ?? -100, r = stats.level_right ?? -100;
      const lVal = document.getElementById('audio-val-l'), rVal = document.getElementById('audio-val-r');
      const lBar = document.getElementById('audio-bar-l'), rBar = document.getElementById('audio-bar-r');
      if (lVal) lVal.textContent = l.toFixed(1);
      if (rVal) rVal.textContent = r.toFixed(1);
      if (lBar) lBar.style.width = Math.max(0, Math.min(100, (l + 60) / 60 * 100)) + '%';
      if (rBar) rBar.style.width = Math.max(0, Math.min(100, (r + 60) / 60 * 100)) + '%';
      // Badge stéréo / mono
      const badge = document.getElementById('audio-badge');
      if (badge) {
        const cls = 'text-xs font-bold uppercase tracking-wide px-2.5 py-0.5 rounded-full ';
        if (stats.stereo_present) { badge.textContent = 'Stéréo'; badge.className = cls + 'bg-green-100 text-green-700'; }
        else { badge.textContent = 'Mono'; badge.className = cls + 'bg-yellow-100 text-yellow-600'; }
      }
    }

    // Spectre audio 0-20 kHz (256 points, mapping direct index→fréquence).
    const audioCanvas = () => document.getElementById('audio-spectrum-canvas');
    let audioSpectrumSmooth = [];
    const AUDIO_JS_ALPHA = 0.3;
    function drawAudioSpectrum() {
      const cv = audioCanvas();
      if (!cv || audioSpectrumSmooth.length === 0) return;
      const dpr = window.devicePixelRatio || 1;
      const rect = cv.getBoundingClientRect();
      cv.width = rect.width * dpr; cv.height = rect.height * dpr;
      const ctx = cv.getContext('2d'); ctx.scale(dpr, dpr);
      const W = rect.width, H = rect.height;
      const dbMax = -20, dbMin = -90;
      const N = audioSpectrumSmooth.length;
      const freqDisplay = 20000;
      function freqToX(f) { return (f / freqDisplay) * W; }
      ctx.fillStyle = '#f9fafb'; ctx.fillRect(0, 0, W, H);
      // Zone utile 0-15 kHz (vert) et bande bruit 15-20 kHz (rouge léger)
      ctx.fillStyle = 'rgba(16,185,129,0.06)'; ctx.fillRect(0, 0, freqToX(15000), H);
      ctx.fillStyle = 'rgba(239,68,68,0.04)'; ctx.fillRect(freqToX(15000), 0, W - freqToX(15000), H);
      // Grille
      ctx.strokeStyle = 'rgba(0,0,0,0.06)'; ctx.lineWidth = 1;
      [-40, -60, -80].forEach(db => { const y = H - ((db - dbMin) / (dbMax - dbMin)) * H; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); });
      // Courbe
      ctx.beginPath(); ctx.strokeStyle = '#2563eb'; ctx.lineWidth = 1.5;
      for (let i = 0; i < N; i++) {
        const f = (i / N) * freqDisplay;
        const x = freqToX(f);
        const db = Math.max(dbMin, Math.min(dbMax, audioSpectrumSmooth[i]));
        const y = H - ((db - dbMin) / (dbMax - dbMin)) * H;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath();
      ctx.fillStyle = 'rgba(37,99,235,0.08)'; ctx.fill();
      // Marqueur 15 kHz
      const xL = freqToX(15000);
      ctx.strokeStyle = '#ef4444'; ctx.globalAlpha = 0.5; ctx.lineWidth = 1;
      ctx.setLineDash([2, 3]); ctx.beginPath(); ctx.moveTo(xL, 0); ctx.lineTo(xL, H - 16); ctx.stroke();
      ctx.setLineDash([]); ctx.globalAlpha = 1;
      // Labels
      ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.font = 'bold 9px monospace'; ctx.textAlign = 'center';
      [{f:5000,l:'5k',c:'#9ca3af'},{f:10000,l:'10k',c:'#9ca3af'},{f:15000,l:'15k',c:'#ef4444'}].forEach(({f,l,c}) => {
        ctx.fillStyle = c; ctx.fillText(l, freqToX(f) * dpr, cv.height - 4);
      });
      ctx.restore();
    }

    function updateMPX(stats) {"""


# ═══════════════════════════════════════════════════════════════════════
# index.html — 3b. Router le rendu spectre selon le mode
# ═══════════════════════════════════════════════════════════════════════
IDX_OLD_SPEC = """                mpxSpectrumData = mpxSpectrumSmooth;
                drawMPXSpectrum();"""
IDX_NEW_SPEC = """                mpxSpectrumData = mpxSpectrumSmooth;
                // Route le rendu : spectre audio (TEF) ou MPX (RTL-SDR)
                const audPanel = document.getElementById('panel-audio-tef');
                if (audPanel && !audPanel.classList.contains('hidden')) {
                    if (audioSpectrumSmooth.length !== raw.length) audioSpectrumSmooth = raw.slice();
                    else for (let i = 0; i < raw.length; i++) audioSpectrumSmooth[i] = AUDIO_JS_ALPHA * raw[i] + (1 - AUDIO_JS_ALPHA) * audioSpectrumSmooth[i];
                    drawAudioSpectrum();
                } else {
                    drawMPXSpectrum();
                }"""


# ═══════════════════════════════════════════════════════════════════════
# index.html — 4. Router les 2 appels updateMPX → updateAnalysisPanel
# (dans updateStats et dans le handler SSE)
# ═══════════════════════════════════════════════════════════════════════
IDX_OLD_CALL1 = """            updateVUMeter(stats);
            pushRealtimeLevel(smoothedLevel(stats.signal_dbf !== undefined ? stats.signal_dbf : level));
            updateMPX(stats);"""
IDX_NEW_CALL1 = """            updateVUMeter(stats);
            pushRealtimeLevel(smoothedLevel(stats.signal_dbf !== undefined ? stats.signal_dbf : level));
            updateAnalysisPanel(stats);"""

IDX_OLD_CALL2 = "                updateMPX(stats); document.getElementById('rds-ps-display').textContent = stats.ps;"
IDX_NEW_CALL2 = "                updateAnalysisPanel(stats); document.getElementById('rds-ps-display').textContent = stats.ps;"


def apply_fragments(path, fragments, is_python):
    if not path.exists():
        sys.exit(f"ERREUR : {path} introuvable.")
    src = path.read_text(encoding="utf-8")
    patched = src
    for label, old, new in fragments:
        c = patched.count(old)
        if c == 0:
            sys.exit(f"ERREUR : fragment '{label}' introuvable dans {path.name}. Aucune écriture.")
        if c > 1:
            sys.exit(f"ERREUR : fragment '{label}' trouvé {c} fois (ambigu) dans {path.name}. Aucune écriture.")
        patched = patched.replace(old, new, 1)
    if is_python:
        try:
            ast.parse(patched)
        except SyntaxError as e:
            sys.exit(f"ERREUR : {path.name} patché ne compile pas ({e}). Aucune écriture.")
    else:
        # Vérifs de cohérence HTML minimales
        if patched.count('panel-audio-tef') < 2:
            sys.exit("ERREUR : le panneau TEF n'a pas été inséré correctement.")
        if patched.count('function updateAudioTEF') != 1:
            sys.exit("ERREUR : updateAudioTEF absente ou dupliquée.")
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    path.write_text(patched, encoding="utf-8")
    print(f"OK — {path.name} patché. Sauvegarde : {bak.name}")


def main():
    if IDX.exists() and "panel-audio-tef" in IDX.read_text(encoding="utf-8"):
        sys.exit("Le patch semble déjà appliqué (panel-audio-tef présent). Rien à faire.")

    apply_fragments(MON, [("expose use_tef", MON_OLD, MON_NEW)], is_python=True)
    apply_fragments(
        IDX,
        [
            ("id panneau MPX", IDX_OLD_PANEL_OPEN, IDX_NEW_PANEL_OPEN),
            ("insertion panneau TEF", IDX_OLD_PANEL_CLOSE, IDX_NEW_PANEL_CLOSE),
            ("fonctions JS TEF", IDX_OLD_JS_ANCHOR, IDX_NEW_JS_BLOCK),
            ("routage spectre", IDX_OLD_SPEC, IDX_NEW_SPEC),
            ("appel updateStats", IDX_OLD_CALL1, IDX_NEW_CALL1),
            ("appel SSE", IDX_OLD_CALL2, IDX_NEW_CALL2),
        ],
        is_python=False,
    )
    print("\\nTerminé. Panneau Analyse audio (TEF) ajouté. RTL-SDR et updateMPX inchangés.")


if __name__ == "__main__":
    main()
