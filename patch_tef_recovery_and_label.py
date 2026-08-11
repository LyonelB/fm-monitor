#!/usr/bin/env python3
"""
patch_tef_recovery_and_label.py

Corrige trois points, en préservant STRICTEMENT le mode RTL-SDR.

── Correctif 1 : bug du rétablissement de signal en mode TEF ──────────────
   `_on_tef_signal` écrivait `self.signal_ok = signal_ok` à chaque trame
   (avec l'ancien critère dbf >= seuil). Cette écriture court-circuitait la
   logique de rétablissement du thread de surveillance : au retour des
   trames, signal_ok repassait True immédiatement, donc le bloc
   « if not self.signal_ok » (émetteur rétabli) n'était jamais atteint et
   send_recovery_alert() n'était jamais appelé.
   → On supprime cette écriture. En mode TEF, self.signal_ok est désormais
     piloté UNIQUEMENT par le thread (comptage de trames Ss). La variable
     locale signal_ok reste utilisée pour les stats et l'historique.
   Effet de bord bénéfique : plus de faux « Perte -100 dB » au démarrage.

── Correctif 2 : libellés d'alerte conditionnels au mode ──────────────────
   Le bloc d'alerte « perte signal » utilisait en dur « Émetteur FM hors
   ligne » / « Aucune porteuse FM détectée ». En TEF, le détecteur mesure la
   RÉCEPTION (débit de trames), pas l'émission. On rend les libellés
   conditionnels : TEF → « Signal FM non capté » (détail neutre) ;
   RTL-SDR → textes d'origine inchangés. Les clés base (signal_lost /
   signal_restored) restent identiques (historique préservé).

── Correctif 3 : pied de page email ───────────────────────────────────────
   « Système de surveillance FM - RTL-SDR » → « BL-FMO Système de
   surveillance FM » (4 occurrences dans email_alert.py). Libellé seul,
   aucun comportement modifié.

Sécurités : .bak sur chaque fichier, validation AST, idempotent.
⚠ Logique RTL-SDR inchangée.
"""

import ast
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
MON = BASE / "monitor.py"
EMAIL = BASE / "email_alert.py"


# ═══════════════════════════════════════════════════════════════════════
# monitor.py — Correctif 1 : retrait de l'écriture parasite de signal_ok
# ═══════════════════════════════════════════════════════════════════════
MON_OLD_ONSIGNAL = """            self.stats['modulation_active'] = signal_ok
        self.signal_ok = signal_ok
        if self.history_enabled and time.time() - self.last_db_save >= 5:"""

MON_NEW_ONSIGNAL = """            self.stats['modulation_active'] = signal_ok
        # NOTE : en mode TEF, self.signal_ok n'est PLUS écrit ici. Il est
        # piloté uniquement par le thread de surveillance (comptage de trames
        # Ss), sinon le retour des trames court-circuitait la détection de
        # rétablissement (recovery jamais envoyé). La variable locale
        # signal_ok reste utilisée pour les stats/historique ci-dessous.
        if self.history_enabled and time.time() - self.last_db_save >= 5:"""


# ═══════════════════════════════════════════════════════════════════════
# monitor.py — Correctif 2 : libellés conditionnels dans le bloc d'alerte
# On remplace le bloc envoi d'alerte de perte + le bloc rétablissement.
# ═══════════════════════════════════════════════════════════════════════
MON_OLD_ALERT = """                    else:
                        silence_duration = time.time() - self.silence_start_time
                        if silence_duration >= self.audio_config['silence_duration'] and not self.alert_sent:
                            logger.error(f"Émetteur perdu depuis {silence_duration:.0f}s - ENVOI ALERTE")
                            success = self.email_alert.send_alert(
                                alert_type="Émetteur FM hors ligne",
                                details=f"Aucune porteuse FM détectée.\\nNiveau: {current_level:.2f} dB\\nDurée: {int(silence_duration)}s",
                                skip_cooldown=True
                            )
                            if success:
                                self.alert_sent = True
                                with self.stats_lock:
                                    self.stats['alerts_sent'] += 1
                                    self.stats['last_alert'] = datetime.now().isoformat()
                                self.db.save_alert(
                                    alert_type='signal_lost',
                                    level_db=current_level,
                                    duration_seconds=int(silence_duration),
                                    message=f"Émetteur hors ligne - {current_level:.2f} dB",
                                    email_sent=True
                                )"""

MON_NEW_ALERT = """                    else:
                        silence_duration = time.time() - self.silence_start_time
                        if silence_duration >= self.audio_config['silence_duration'] and not self.alert_sent:
                            # Libellés selon le mode : le TEF mesure la réception
                            # (débit de trames), pas l'émission → libellé distinct.
                            if self.use_tef:
                                _sig_type = "Signal FM non capté"
                                _sig_detail = (
                                    f"Aucune trame signal reçue du tuner depuis {int(silence_duration)}s.\\n"
                                    f"Le tuner ne capte plus de signal FM sur {self.stats.get('signal_dbf', 0):.1f} dBf.\\n"
                                    f"Causes possibles : réception/antenne du tuner, ou interruption de la diffusion."
                                )
                                _sig_msg = f"Signal FM non capté - {current_level:.2f} dB"
                            else:
                                _sig_type = "Émetteur FM hors ligne"
                                _sig_detail = f"Aucune porteuse FM détectée.\\nNiveau: {current_level:.2f} dB\\nDurée: {int(silence_duration)}s"
                                _sig_msg = f"Émetteur hors ligne - {current_level:.2f} dB"
                            logger.error(f"{_sig_type} depuis {silence_duration:.0f}s - ENVOI ALERTE")
                            success = self.email_alert.send_alert(
                                alert_type=_sig_type,
                                details=_sig_detail,
                                skip_cooldown=True
                            )
                            if success:
                                self.alert_sent = True
                                with self.stats_lock:
                                    self.stats['alerts_sent'] += 1
                                    self.stats['last_alert'] = datetime.now().isoformat()
                                self.db.save_alert(
                                    alert_type='signal_lost',
                                    level_db=current_level,
                                    duration_seconds=int(silence_duration),
                                    message=_sig_msg,
                                    email_sent=True
                                )"""


# ═══════════════════════════════════════════════════════════════════════
# email_alert.py — Correctif 3 : pied de page (4 occurrences identiques)
# ═══════════════════════════════════════════════════════════════════════
EMAIL_OLD_FOOTER = "Système de surveillance FM - RTL-SDR"
EMAIL_NEW_FOOTER = "BL-FMO Système de surveillance FM"


def patch_file(path, fragments, footer_replace=None):
    """Applique une liste de (label, old, new) à un fichier, + option footer."""
    if not path.exists():
        sys.exit(f"ERREUR : {path} introuvable. Lance le patch depuis ~/fm-monitor.")
    src = path.read_text(encoding="utf-8")
    patched = src

    for label, old, new in fragments:
        c = patched.count(old)
        if c == 0:
            # Idempotence : si le "new" est déjà là, on tolère.
            if new.split("\\n")[0] in patched:
                sys.exit(f"Le patch semble déjà appliqué ({label}). Rien à faire.")
            sys.exit(f"ERREUR : fragment '{label}' introuvable dans {path.name}. Aucune écriture.")
        if c > 1:
            sys.exit(f"ERREUR : fragment '{label}' trouvé {c} fois (ambigu) dans {path.name}. Aucune écriture.")
        patched = patched.replace(old, new, 1)

    if footer_replace:
        old_f, new_f = footer_replace
        n = patched.count(old_f)
        if n == 0 and new_f not in patched:
            sys.exit(f"ERREUR : pied de page introuvable dans {path.name}.")
        patched = patched.replace(old_f, new_f)  # toutes les occurrences

    try:
        ast.parse(patched)
    except SyntaxError as e:
        sys.exit(f"ERREUR : {path.name} patché ne compile pas ({e}). Aucune écriture.")

    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    path.write_text(patched, encoding="utf-8")
    print(f"OK — {path.name} patché. Sauvegarde : {bak.name}")


def main():
    # Garde-fou d'idempotence globale
    if MON.exists() and "Signal FM non capté" in MON.read_text(encoding="utf-8"):
        sys.exit("Le patch semble déjà appliqué (monitor.py). Rien à faire.")

    patch_file(
        MON,
        [
            ("retrait écriture signal_ok", MON_OLD_ONSIGNAL, MON_NEW_ONSIGNAL),
            ("libellés conditionnels alerte", MON_OLD_ALERT, MON_NEW_ALERT),
        ],
    )
    patch_file(
        EMAIL,
        [],
        footer_replace=(EMAIL_OLD_FOOTER, EMAIL_NEW_FOOTER),
    )
    print("\\nTerminé. Correctifs : rétablissement TEF réparé, "
          "libellés TEF distincts, pied de page BL-FMO. RTL-SDR inchangé.")


if __name__ == "__main__":
    main()
