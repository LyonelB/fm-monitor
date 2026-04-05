#!/usr/bin/env python3
"""
Module de surveillance du signal FM avec RTL-SDR - Calcul RMS direct
Basé sur l'approche fonctionnelle avec lecture directe du stdout
"""
import subprocess
import threading
import queue
import json
import logging
import time
import os
import collections
import numpy as np
import requests
from datetime import datetime
from email_alert import EmailAlert
from database import FMDatabase
from mpx_analyzer import MPXAnalyzer

logger = logging.getLogger(__name__)

class FMMonitor:
    def __init__(self, config_path='config.json'):
        """Initialise le moniteur FM"""
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.rtl_config = self.config['rtl_sdr']
        self.audio_config = self.config['audio']

        # Queue pour le streaming MP3
        self.stream_queue = queue.Queue(maxsize=500)

        # Processus
        self.master_process = None
        self.monitor_thread = None
        self.running = False

        # État de la surveillance
        self.signal_ok = True
        self.silence_start_time = None
        self.alert_sent = False

        # Surveillance de la modulation
        self.level_history = collections.deque(maxlen=30)
        self.modulation_ok = True
        self.modulation_alert_sent = False
        self.no_modulation_start = None
        self.modulation_std_threshold = float(self.audio_config.get('modulation_std_threshold', 1.5))
        self.modulation_alert_delay = int(self.audio_config.get('modulation_alert_delay', 30))
        self.signal_lost_threshold = float(self.audio_config.get('signal_lost_threshold', -50.0))

        # Surveillance RDS
        self.rds_ok = False
        self.rds_ever_received = False
        self.rds_last_seen = None
        self.rds_alert_sent = False
        self.rds_timeout = int(self.audio_config.get('rds_timeout', 120))

        # Système d'alertes
        self.email_alert = EmailAlert(config_path)

        # Statistiques
        self.stats = {
            'start_time': None,
            'uptime': 0,
            'alerts_sent': 0,
            'last_alert': None,
            'current_level': -100.0,
            'modulation_active': False,
            'ps': '-',
            'rt': '-',
            'pi': '-',
            'station_logo': None,
            'status': 'Arrêté'
        }

        # Buffer pour accumuler le RadioText
        self.rt_buffer = ''
        self.rt_ab_flag = None
        self._rt_stable_count = 0
        self._rt_last_candidate = ''
        self._logo_searched = False
        self._logo_last_attempt = 0
        self._logo_fail_count = 0
        self._rds_db_reload = False
        self._rds_lookup = None

        # Lock pour thread-safety
        self.stats_lock = threading.Lock()

        # Base de données
        self.db = FMDatabase()
        self.last_db_save = time.time()

        # =============================================
        # FLAGS DE SERVICES (activables/désactivables)
        # =============================================
        self.vu_meter_enabled = True      # Calcul RMS et affichage VU-mètre
        self.audio_enabled = True          # Streaming audio (player)
        self.watchdog_enabled = False       # Watchdog auto-relance rtl_fm
        self.rds_enabled = True           # Lecteur RDS automatique (désactivé par défaut)
        self.history_enabled = False        # Enregistrement historique audio 24h
        self.mpx_enabled = True            # Analyse MPX (déviation, pilote, stéréo, RDS RF)

        # Analyseur MPX (process_every=4 → mise à jour ~48ms, adapté Pi 3B+)
        self.mpx_analyzer = MPXAnalyzer(sample_rate=171000, process_every=4)

        # Alerte sur-déviation
        self.deviation_alert_threshold = float(
            self.audio_config.get('deviation_alert_threshold', 80.0)
        )  # kHz — alerte si déviation peak > seuil
        self.deviation_alert_sent = False
        self.deviation_over_start = None
        self.deviation_alert_delay = int(
            self.audio_config.get('deviation_alert_delay', 10)
        )  # secondes de sur-déviation avant alerte

        # Queue pour sauvegarde BDD non-bloquante
        self.db_queue = queue.Queue(maxsize=100)

    def get_services_status(self):
        """Retourne l'état de tous les services"""
        return {
            'vu_meter': self.vu_meter_enabled,
            'audio': self.audio_enabled,
            'watchdog': self.watchdog_enabled,
            'rds': self.rds_enabled,
            'history': self.history_enabled,
            'mpx': self.mpx_enabled,
            'monitoring': self.running
        }

    def toggle_service(self, service, enabled):
        """Active ou désactive un service"""
        if service == 'vu_meter':
            self.vu_meter_enabled = enabled
            logger.info(f"VU-mètre {'activé' if enabled else 'désactivé'}")

        elif service == 'audio':
            self.audio_enabled = enabled
            if not enabled:
                # Vider la queue audio
                while not self.stream_queue.empty():
                    try:
                        self.stream_queue.get_nowait()
                    except queue.Empty:
                        break
            logger.info(f"Player audio {'activé' if enabled else 'désactivé'}")

        elif service == 'watchdog':
            self.watchdog_enabled = enabled
            logger.info(f"Watchdog {'activé' if enabled else 'désactivé'}")

        elif service == 'rds':
            self.rds_enabled = enabled
            if enabled:
                # Lancer le thread RDS si pas déjà actif
                if not hasattr(self, 'rds_thread') or not self.rds_thread.is_alive():
                    self.rds_thread = threading.Thread(target=self._rds_reader, daemon=True)
                    self.rds_thread.start()
                    logger.info("Lecteur RDS démarré")
            else:
                logger.info("Lecteur RDS désactivé")

        elif service == 'history':
            self.history_enabled = enabled
            logger.info(f"Historique audio {'activé' if enabled else 'désactivé'}")

        elif service == 'mpx':
            self.mpx_enabled = enabled
            if not enabled:
                self.mpx_analyzer.reset()
            logger.info(f"Analyse MPX {'activée' if enabled else 'désactivée'}")

        else:
            logger.warning(f"Service inconnu: {service}")
            return False

        return True

    def start(self):
        """Démarre la capture et la surveillance FM"""
        if self.running:
            logger.warning("Le moniteur est déjà en cours d'exécution")
            return

        logger.info(f"Démarrage de la surveillance FM sur {self.rtl_config['frequency']}")
        self.running = True
        self.stats['start_time'] = datetime.now()
        self.stats['status'] = 'En cours'

        # Créer le FIFO pour le streaming audio
        fifo_path = '/tmp/fm_stream.mp3'
        if os.path.exists(fifo_path):
            os.remove(fifo_path)
        os.mkfifo(fifo_path)
        logger.info(f"FIFO créé : {fifo_path}")

        # Nettoyer les processus existants
        os.system("pkill -9 rtl_fm 2>/dev/null")
        os.system("pkill -9 sox 2>/dev/null")
        time.sleep(0.5)

        try:
            # Démarrer le processus maître (rtl_fm - toujours actif)
            self.master_thread = threading.Thread(target=self._master_monitor, daemon=True)
            self.master_thread.start()

            # Démarrer le streaming MP3
            self.stream_thread = threading.Thread(target=self._stream_monitor, daemon=True)
            self.stream_thread.start()

            # Thread de surveillance du signal (toujours actif pour les alertes)
            self.monitor_thread = threading.Thread(target=self._monitor_signal, daemon=True)
            self.monitor_thread.start()

            # Démarrer le watchdog
            self.watchdog_thread = threading.Thread(target=self._watchdog, daemon=True)
            self.watchdog_thread.start()

            # Thread dédié pour sauvegarde BDD (non-bloquant)
            self.db_writer_thread = threading.Thread(target=self._db_writer, daemon=True)
            self.db_writer_thread.start()

            # RDS désactivé par défaut (activable depuis le dashboard)
            if self.rds_enabled:
                self.rds_thread = threading.Thread(target=self._rds_reader, daemon=True)
                self.rds_thread.start()

            self.rds_db_watcher_thread = threading.Thread(
                target=self._rds_db_watcher, daemon=True
            )
            self.rds_db_watcher_thread.start()
            logger.info("Watcher rds-station-db démarré (cycle 24h)")
            logger.info("Surveillance FM démarrée avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du démarrage: {e}")
            self.stop()
            raise

    def _watchdog(self):
        """Thread de surveillance qui relance rtl_fm si crash"""
        logger.info("Watchdog démarré")

        while self.running:
            try:
                time.sleep(10)

                if not self.running:
                    break

                # Ne rien faire si watchdog désactivé
                if not self.watchdog_enabled:
                    continue

                # Vérifier si le processus master est mort
                if self.master_process and self.master_process.poll() is not None:
                    logger.error("rtl_fm a planté ! Relance automatique...")

                    os.system("pkill -9 rtl_fm 2>/dev/null")
                    os.system("pkill -9 sox 2>/dev/null")
                    os.system("pkill -9 redsea 2>/dev/null")
                    time.sleep(2)

                    self.master_thread = threading.Thread(target=self._master_monitor, daemon=True)
                    self.master_thread.start()

                    logger.info("rtl_fm relancé automatiquement")

            except Exception as e:
                logger.error(f"Erreur watchdog: {e}")

    def _db_writer(self):
        """Thread dédié pour écriture BDD non-bloquante"""
        logger.info("Thread BDD démarré")
        while self.running:
            try:
                item = self.db_queue.get(timeout=1)
                self.db.save_audio_level(item['level'], item['signal_ok'])
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Erreur écriture BDD: {e}")

    def _master_monitor(self):
        """
        Processus maître : UN SEUL rtl_fm à 171k avec tee pour tout
        - Branche 1 : redsea pour RDS
        - Branche 2 : sox pour MP3
        - Stdout : Python pour calcul RMS
        """
        sample_rate = '171000'

        cmd = (
            f"stdbuf -o0 rtl_fm "
            f"-f {self.rtl_config['frequency']} "
            f"-M wbfm -s 171k -r 171k "
            f"-g {self.rtl_config['gain']} "
            f"-p {self.rtl_config['ppm_error']} "
            f"-A fast | "
            f"tee >(stdbuf -oL redsea -p > /tmp/rds_output.json) | "
            f"tee >(ffmpeg -f s16le -ar {sample_rate} -ac 1 -i - "
            f"-codec:a libmp3lame -b:a 128k -ar {self.audio_config['output_rate']} -ac 2 "
            f"-content_type audio/mpeg -f mp3 "
            f"icecast://source:fmmonitor2026@localhost:8000/fmmonitor 2>/dev/null) | cat"
        )

        logger.info("Lancement du processus maître rtl_fm 171k avec tee (RDS+Audio+RMS)")

        if os.path.exists('/tmp/rds_output.json'):
            os.remove('/tmp/rds_output.json')

        try:
            self.master_process = subprocess.Popen(
                cmd,
                shell=True,
                executable='/bin/bash',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )

            chunk_size = 4096

            while self.running and self.master_process.poll() is None:
                chunk = self.master_process.stdout.read(chunk_size)
                if not chunk:
                    break

                # VU-mètre désactivé : on lit quand même le stdout pour ne pas bloquer rtl_fm
                # mais on ne calcule pas le RMS
                if not self.vu_meter_enabled:
                    continue

                try:
                    samples = np.frombuffer(chunk, dtype=np.int16)

                    if len(samples) < 10:
                        continue

                    rms = np.sqrt(np.mean(np.square(samples.astype(np.float32))))

                    if rms > 0:
                        db = 20 * np.log10(rms / 32768.0)
                    else:
                        db = -100.0

                    modulation_active = bool(db > -60.0)
                    with self.stats_lock:
                        self.stats['current_level'] = float(db)
                        self.stats['modulation_active'] = modulation_active

                    # ── Analyse MPX (déviation, pilote, stéréo, RDS RF) ──
                    if self.mpx_enabled:
                        self.mpx_analyzer.process_chunk(samples)

                    # Envoyer en BDD via queue non-bloquante toutes les 5 secondes
                    if self.history_enabled and time.time() - self.last_db_save >= 5:
                        try:
                            self.db_queue.put_nowait({'level': float(db), 'signal_ok': self.signal_ok})
                            self.last_db_save = time.time()
                        except queue.Full:
                            pass

                except Exception as e:
                    logger.error(f"Erreur calcul RMS: {e}")

        except Exception as e:
            logger.error(f"Erreur processus maître: {e}")
        finally:
            if self.master_process:
                self.master_process.kill()

    def _stream_monitor(self):
        """Lit /tmp/fm_stream.mp3 et le met dans la queue"""
        logger.info("Démarrage du monitoring du stream MP3")

        while not os.path.exists('/tmp/fm_stream.mp3'):
            time.sleep(0.1)

        try:
            with open('/tmp/fm_stream.mp3', 'rb') as f:
                while self.running:
                    chunk = f.read(8192)
                    if chunk:
                        # Si audio désactivé, on lit quand même pour ne pas bloquer sox
                        # mais on ne met pas dans la queue
                        if not self.audio_enabled:
                            time.sleep(0.05)
                            continue
                        try:
                            self.stream_queue.put(chunk, timeout=0.1)
                        except queue.Full:
                            try:
                                self.stream_queue.get_nowait()
                            except queue.Empty:
                                pass
                    else:
                        time.sleep(0.05)
        except Exception as e:
            logger.error(f"Erreur stream MP3: {e}")

    def _rds_reader(self):
        """Lit les données RDS depuis /tmp/rds_output.json"""
        logger.info("Démarrage lecteur RDS automatique")

        while not os.path.exists('/tmp/rds_output.json'):
            time.sleep(0.5)

        try:
            proc = subprocess.Popen(
                ['tail', '-f', '/tmp/rds_output.json'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            for line in proc.stdout:
                if not self.running or not self.rds_enabled:
                    break

                try:
                    data = json.loads(line.strip())

                    with self.stats_lock:
                        if 'ps' in data:
                            self.stats['ps'] = data['ps'].strip()
                            self.rds_last_seen = time.time()
                            self.rds_ever_received = True
                            self.rds_ok = True
                            if not self._logo_searched:
                                import threading as _t
                                _t.Thread(target=self._fetch_station_logo, daemon=True).start()

                        if 'pi' in data:
                            new_pi = data['pi'].strip().upper().lstrip('0X').lstrip('0x')
                            if new_pi.startswith('X'):
                                new_pi = new_pi[1:]
                            old_pi = self.stats.get('pi', '-')
                            if new_pi != old_pi and new_pi not in ('', '-'):
                                logger.info(f'PI changé {old_pi} -> {new_pi}, réinit logo')
                                self._logo_searched = False
                                self._logo_last_attempt = 0
                                self.stats['station_logo'] = None
                                self._rds_db_reload = True
                                self.stats['pi'] = new_pi  # affecter AVANT de lancer le thread
                                import threading as _t
                                _t.Thread(target=self._fetch_station_logo, daemon=True).start()
                            else:
                                self.stats['pi'] = new_pi
                            self.rds_last_seen = time.time()
                            self.rds_ever_received = True
                            self.rds_ok = True
                            if not self._logo_searched:
                                import threading as _t
                                _t.Thread(target=self._fetch_station_logo, daemon=True).start()

                        if 'radiotext' in data:
                            rt_full = data['radiotext'].strip()
                            if rt_full:
                                self.stats['rt'] = rt_full
                                self.rt_buffer = rt_full
                        elif 'partial_radiotext' in data:
                            rt_segment = data['partial_radiotext'].strip()
                            rt_ab = data.get('rt_ab', 'A')
                            if self.rt_ab_flag is not None and self.rt_ab_flag != rt_ab:
                                self.rt_buffer = ''
                                self._rt_stable_count = 0
                                self._rt_last_candidate = ''
                            self.rt_ab_flag = rt_ab
                            if rt_segment and len(rt_segment) > len(self.rt_buffer):
                                self.rt_buffer = rt_segment
                            # Stabilisation : même texte 3 fois de suite → RT validé
                            if self.rt_buffer and self.rt_buffer == self._rt_last_candidate:
                                self._rt_stable_count += 1
                                if self._rt_stable_count >= 3:
                                    self.stats['rt'] = self.rt_buffer
                                    self._rt_stable_count = 0
                            else:
                                self._rt_last_candidate = self.rt_buffer
                                self._rt_stable_count = 1

                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Erreur lecture RDS: {e}")

        except Exception as e:
            logger.error(f"Erreur processus RDS: {e}")

    def read_rds_once(self, duration=10):
        """Lit les données RDS depuis le flux existant (/tmp/rds_output.json)"""
        try:
            logger.info(f"Lecture RDS ponctuelle ({duration}s) depuis flux existant...")

            if not os.path.exists('/tmp/rds_output.json'):
                logger.warning("Fichier RDS non disponible")
                return False

            ps_found = False
            rt_found = False
            start_time = time.time()

            proc = subprocess.Popen(
                ['tail', '-f', '/tmp/rds_output.json'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            import select

            while time.time() - start_time < duration:
                ready = select.select([proc.stdout], [], [], 0.5)
                if ready[0]:
                    line = proc.stdout.readline()
                    if line:
                        try:
                            data = json.loads(line.strip())

                            if 'ps' in data and not ps_found:
                                self.stats['ps'] = data['ps'].strip()
                                ps_found = True
                                logger.info(f"PS trouvé: {self.stats['ps']}")

                            if 'partial_radiotext' in data:
                                # Ignoré : on n'affiche que le RT complet
                                pass

                            if ps_found and rt_found:
                                logger.info("PS et RT trouvés, arrêt anticipé")
                                break

                        except json.JSONDecodeError:
                            pass

            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()

            logger.info(f"Lecture RDS terminée - PS: {ps_found}, RT: {rt_found}")
            return True

        except Exception as e:
            logger.error(f"Erreur lecture RDS: {e}")
            return False

    def _monitor_signal(self):
        """Surveille le niveau du signal et la modulation audio"""
        logger.info("Thread de surveillance démarré")

        while self.running:
            try:
                with self.stats_lock:
                    current_level = self.stats['current_level']

                # Alimenter le buffer d'historique
                self.level_history.append(current_level)

                # ── 1. PERTE TOTALE DE L'ÉMETTEUR (porteuse absente) ──────────
                # Seuil très bas : -50 dB par défaut → vrai crash émetteur
                if current_level < self.signal_lost_threshold:
                    if self.signal_ok:
                        self.signal_ok = False
                        self.silence_start_time = time.time()
                        logger.warning(f"Perte émetteur détectée: {current_level:.2f} dB")
                    else:
                        silence_duration = time.time() - self.silence_start_time
                        if silence_duration >= self.audio_config['silence_duration'] and not self.alert_sent:
                            logger.error(f"Émetteur perdu depuis {silence_duration:.0f}s - ENVOI ALERTE")
                            success = self.email_alert.send_alert(
                                alert_type="Émetteur FM hors ligne",
                                details=f"Aucune porteuse FM détectée.\nNiveau: {current_level:.2f} dB\nDurée: {int(silence_duration)}s",
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
                                )
                else:
                    if not self.signal_ok:
                        logger.info(f"Émetteur rétabli: {current_level:.2f} dB")
                        if self.alert_sent:
                            self.email_alert.send_recovery_alert()
                            self.db.save_alert(
                                alert_type='signal_restored',
                                level_db=current_level,
                                duration_seconds=int(time.time() - self.silence_start_time),
                                message=f"Émetteur rétabli - {current_level:.2f} dB",
                                email_sent=True
                            )
                    self.signal_ok = True
                    self.silence_start_time = None
                    self.alert_sent = False

                # ── 2. ABSENCE DE MODULATION (console coupée, porteuse présente) ──
                if len(self.level_history) >= 20:
                    std = float(np.std(list(self.level_history)))
                    no_modulation = std < self.modulation_std_threshold

                    if no_modulation:
                        if self.no_modulation_start is None:
                            self.no_modulation_start = time.time()
                        absence_duration = time.time() - self.no_modulation_start

                        if absence_duration >= self.modulation_alert_delay and not self.modulation_alert_sent:
                            logger.warning(f"Absence modulation ({std:.2f} dB std, {absence_duration:.0f}s) - ENVOI ALERTE")
                            success = self.email_alert.send_alert(
                                alert_type="Absence de modulation audio",
                                details=f"Signal FM présent ({current_level:.1f} dB) mais sans modulation audio depuis {int(absence_duration)}s.\n"
                                        f"Variation du niveau : ±{std:.2f} dB (seuil : ±{self.modulation_std_threshold} dB)\n"
                                        f"Vérifier la console du studio et la chaîne audio.",
                                skip_cooldown=True
                            )
                            if success:
                                self.modulation_alert_sent = True
                                self.modulation_ok = False
                                with self.stats_lock:
                                    self.stats['alerts_sent'] += 1
                                    self.stats['last_alert'] = datetime.now().isoformat()
                                self.db.save_alert(
                                    alert_type='no_modulation',
                                    level_db=current_level,
                                    duration_seconds=int(absence_duration),
                                    message=f"Absence modulation - std {std:.2f} dB",
                                    email_sent=True
                                )
                    else:
                        if self.modulation_alert_sent:
                            logger.info(f"Modulation rétablie (std={std:.2f} dB)")
                            self.email_alert.send_alert(
                                alert_type="Modulation audio rétablie",
                                details=f"La modulation audio est à nouveau détectée.\nVariation du niveau : ±{std:.2f} dB",
                                skip_cooldown=True
                            )
                            self.db.save_alert(
                                alert_type='modulation_restored',
                                level_db=current_level,
                                duration_seconds=0,
                                message=f"Modulation rétablie - std {std:.2f} dB",
                                email_sent=True
                            )
                        self.modulation_ok = True
                        self.modulation_alert_sent = False
                        self.no_modulation_start = None

                # ── 3. SURVEILLANCE RDS ────────────────────────────────────────
                if self.rds_enabled and self.rds_ever_received:
                    rds_absence = time.time() - self.rds_last_seen if self.rds_last_seen else 0
                    if rds_absence >= self.rds_timeout:
                        if not self.rds_alert_sent:
                            self.rds_ok = False
                            logger.warning(f"RDS absent depuis {rds_absence:.0f}s - ENVOI ALERTE")
                            success = self.email_alert.send_alert(
                                alert_type="Signal RDS absent",
                                details=f"Aucune donnée RDS reçue depuis {int(rds_absence)}s.\n"
                                        f"Vérifier le codeur RDS de la station.",
                                skip_cooldown=True
                            )
                            if success:
                                self.rds_alert_sent = True
                                self.db.save_alert(
                                    alert_type='rds_lost',
                                    level_db=current_level,
                                    duration_seconds=int(rds_absence),
                                    message=f"RDS absent depuis {int(rds_absence)}s",
                                    email_sent=True
                                )
                    else:
                        if self.rds_alert_sent:
                            logger.info("Signal RDS rétabli")
                            self.email_alert.send_alert(
                                alert_type="Signal RDS rétabli",
                                details="Les données RDS sont à nouveau reçues correctement.",
                                skip_cooldown=True
                            )
                            self.db.save_alert(
                                alert_type='rds_restored',
                                level_db=current_level,
                                duration_seconds=0,
                                message="RDS rétabli",
                                email_sent=True
                            )
                        self.rds_ok = True
                        self.rds_alert_sent = False

                # ── 4. SURVEILLANCE SUR-DÉVIATION FM ─────────────────────────
                if self.mpx_enabled:
                    mpx = self.mpx_analyzer.get_results()
                    deviation = mpx.get('deviation_peak', 0.0)

                    if deviation > self.deviation_alert_threshold:
                        if self.deviation_over_start is None:
                            self.deviation_over_start = time.time()
                        over_duration = time.time() - self.deviation_over_start

                        if over_duration >= self.deviation_alert_delay and not self.deviation_alert_sent:
                            logger.warning(
                                f"Sur-déviation FM : {deviation:.1f} kHz > "
                                f"{self.deviation_alert_threshold:.0f} kHz depuis {over_duration:.0f}s"
                            )
                            success = self.email_alert.send_alert(
                                alert_type="Sur-déviation FM détectée",
                                details=(
                                    f"Déviation FM : {deviation:.1f} kHz "
                                    f"(seuil : {self.deviation_alert_threshold:.0f} kHz)\n"
                                    f"Durée : {int(over_duration)}s\n"
                                    f"Pilote 19 kHz : {mpx.get('pilot_level', -100):.1f} dBFS\n"
                                    f"Vérifier le processeur audio et le limiter de déviation."
                                ),
                                skip_cooldown=True
                            )
                            if success:
                                self.deviation_alert_sent = True
                                self.db.save_alert(
                                    alert_type='over_deviation',
                                    level_db=current_level,
                                    duration_seconds=int(over_duration),
                                    message=f"Sur-déviation {deviation:.1f} kHz",
                                    email_sent=True
                                )
                    else:
                        if self.deviation_alert_sent:
                            logger.info(f"Déviation revenue dans les limites : {deviation:.1f} kHz")
                            self.email_alert.send_alert(
                                alert_type="Déviation FM normalisée",
                                details=f"Déviation revenue à {deviation:.1f} kHz.",
                                skip_cooldown=True
                            )
                        self.deviation_alert_sent = False
                        self.deviation_over_start = None

                # ── Mettre à jour uptime ──────────────────────────────────────
                if self.stats['start_time']:
                    uptime = (datetime.now() - self.stats['start_time']).total_seconds()
                    with self.stats_lock:
                        self.stats['uptime'] = int(uptime)

                time.sleep(1)

            except Exception as e:
                logger.error(f"Erreur surveillance: {e}")
                time.sleep(1)

    def _get_rds_lookup(self, force_refresh=False):
        """Instance RDSLookup partagée, rechargée si demandé."""
        try:
            from rds_lookup import RDSLookup
            if self._rds_lookup is None:
                self._rds_lookup = RDSLookup(country='FR', auto_refresh=False)
            if force_refresh:
                self._rds_lookup.force_refresh()
                logger.info("Base rds-station-db rechargée depuis GitHub")
            return self._rds_lookup
        except Exception as e:
            logger.warning(f"rds_lookup indisponible: {e}")
            return None

    def _rds_db_watcher(self):
        """
        Thread de surveillance rds-station-db.
        Toutes les 24h (ou sur changement de PI) :
          - Recharge la base depuis GitHub
          - Met a jour station_logo si le logo du PI courant a change
"""
        import time as _time
        INTERVAL = 24 * 3600
        while self.running:
            elapsed = 0
            while self.running and elapsed < INTERVAL:
                _time.sleep(60)
                elapsed += 60
                if self._rds_db_reload:
                    logger.info("Watcher: rechargement anticipe (changement PI)")
                    self._rds_db_reload = False
                    break
            if not self.running:
                break
            try:
                pi = self.stats.get('pi', '').strip().upper()
                if not pi or pi == '-':
                    continue
                ps_current = self.stats.get('ps', '').strip()
                lookup = self._get_rds_lookup(force_refresh=True)
                if not lookup:
                    continue
                # Recherche exacte PI+PS pour gérer les PI partagés (ex: RCF)
                station = lookup.get(pi=pi, ps=ps_current) if ps_current else lookup.get_by_pi(pi)
                if not station:
                    logger.info(f"Watcher: PI {pi} / PS '{ps_current}' non trouve dans la base")
                    continue
                new_logo = station.get('logo_url')
                current_logo = self.stats.get('station_logo')
                if new_logo and new_logo != current_logo:
                    logger.info(
                        f"Watcher: logo mis a jour [{pi}] {station.get('name')}: {new_logo}"
                    )
                    with self.stats_lock:
                        self.stats['station_logo'] = new_logo
                else:
                    logger.info(
                        f"Watcher: logo inchange [{pi}] {station.get('name')}"
                    )
            except Exception as e:
                logger.warning(f"Watcher rds-station-db erreur: {e}")

    def _fetch_station_logo(self):
        """
        Recherche le logo de la station recue.
        Recherche le logo de la station recue via rds-station-db (PI + PS).
"""
        import time as _time
        if _time.time() - self._logo_last_attempt < 60:
            return
        self._logo_last_attempt = _time.time()
        try:
            for _ in range(10):
                pi = self.stats.get('pi', '').strip().upper()
                ps = self.stats.get('ps', '').strip().upper()
                if pi and pi != '-' and ps and ps != '-':
                    break
                _time.sleep(0.5)
            pi = self.stats.get('pi', '').strip().upper()
            ps = self.stats.get('ps', '').strip()
            ps_upper = ps.upper()
            freq_raw = self.rtl_config.get('frequency', '')
            freq_mhz = freq_raw.replace('M', '').replace('m', '')
            station_name = self.config.get('station', {}).get('name', ps) or ps

            # Validation minimale : PI et PS doivent être disponibles
            if not pi or pi == '-' or not ps or ps == '-':
                logger.info("PI ou PS non disponible, logo non recherché")
                return

            # Priorite 1 : rds-station-db
            # get(pi+ps) : correspondance exacte, gère les PI partagés (ex: RCF)
            lookup = self._get_rds_lookup(force_refresh=True)
            if lookup:
                station = lookup.get(pi=pi, ps=ps)
                if station:
                    if station.get('logo_url'):
                        logo_url = station['logo_url']
                        logger.info(
                            f"Logo rds-station-db [{pi}/{ps}] "
                            f"{station.get('name')}: {logo_url}"
                        )
                        self._logo_searched = True
                        with self.stats_lock:
                            self.stats['station_logo'] = logo_url
                        return
                    else:
                        logger.info(
                            f"Station [{pi}/{ps}] {station.get('name')} "
                            f"trouvee mais sans logo"
                        )

            # Aucun logo trouvé dans rds-station-db
            self._logo_fail_count += 1
            logger.info(
                f"Aucun logo trouve pour [{pi}/{ps}] dans rds-station-db "
                f"(echec #{self._logo_fail_count})"
            )

        except Exception as e:
            logger.warning(f"Erreur recherche logo: {e}")

    def get_audio_chunk(self):
        """Récupère un chunk audio pour le streaming"""
        if not self.audio_enabled:
            return None
        try:
            return self.stream_queue.get(timeout=0.1)
        except queue.Empty:
            return None

    def get_stats(self):
        """Récupère les statistiques"""
        with self.stats_lock:
            stats = self.stats.copy()

        stats['signal_ok'] = self.signal_ok
        stats['modulation_ok'] = self.modulation_ok
        stats['rds_ok'] = self.rds_ok
        stats['rds_ever_received'] = self.rds_ever_received
        stats['frequency'] = self.rtl_config['frequency']
        stats['station_logo'] = self.stats.get('station_logo')

        # Données MPX (déviation, pilote, stéréo, RDS RF)
        if self.mpx_enabled:
            stats.update(self.mpx_analyzer.get_results())

        if stats['start_time']:
            stats['start_time'] = stats['start_time'].strftime('%d/%m/%Y %H:%M:%S')

        return stats

    def stop(self):
        """Arrête le moniteur"""
        logger.info("Arrêt du moniteur FM")
        self.running = False
        self.level_history.clear()
        self.modulation_ok = True
        self.modulation_alert_sent = False
        self.no_modulation_start = None
        self.rds_ok = False
        self.rds_ever_received = False
        self.rds_alert_sent = False
        self._logo_searched = False
        self._logo_last_attempt = 0
        self._logo_fail_count = 0
        self._rds_db_reload = False
        self._rds_lookup = None
        self.stats['station_logo'] = None
        self.deviation_alert_sent = False
        self.deviation_over_start = None
        self.mpx_analyzer.reset()

        if self.master_process:
            self.master_process.kill()

        os.system("pkill -9 rtl_fm 2>/dev/null")
        os.system("pkill -9 sox 2>/dev/null")
        os.system("pkill -9 ffmpeg 2>/dev/null")
        os.system("pkill -9 redsea 2>/dev/null")

        # Attendre que tous les threads soient bien terminés
        for attr in ['master_thread', 'monitor_thread', 'watchdog_thread',
                     'stream_thread', 'db_writer_thread']:
            t = getattr(self, attr, None)
            if t and t.is_alive():
                t.join(timeout=3)
                if t.is_alive():
                    logger.warning(f"Thread {attr} non terminé après 3s")

        # Supprimer le FIFO
        fifo_path = '/tmp/fm_stream.mp3'
        if os.path.exists(fifo_path):
            try:
                os.remove(fifo_path)
                logger.info("FIFO supprimé")
            except:
                pass

        self.stats['status'] = 'Arrêté'
