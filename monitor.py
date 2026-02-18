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
import numpy as np
from datetime import datetime
from email_alert import EmailAlert
from database import FMDatabase

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

        # Système d'alertes
        self.email_alert = EmailAlert(config_path)

        # Statistiques
        self.stats = {
            'start_time': None,
            'uptime': 0,
            'alerts_sent': 0,
            'last_alert': None,
            'current_level': -100.0,
            'ps': '-',
            'rt': '-',
            'status': 'Arrêté'
        }

        # Buffer pour accumuler le RadioText
        self.rt_buffer = ''
        self.rt_ab_flag = None

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
        self.watchdog_enabled = True       # Watchdog auto-relance rtl_fm
        self.rds_enabled = False           # Lecteur RDS automatique (désactivé par défaut)
        self.history_enabled = True        # Enregistrement historique audio 24h

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
            f"tee >(sox -t raw -r {sample_rate} -e signed -b 16 -c 1 - "
            f"-t mp3 -r {self.audio_config['output_rate']} -C 128 - "
            f"> /tmp/fm_stream.mp3) | cat"
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

                    with self.stats_lock:
                        self.stats['current_level'] = float(db)

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
                            self.stats['ps'] = data['ps']

                        if 'partial_radiotext' in data:
                            rt_segment = data['partial_radiotext'].strip()
                            rt_ab = data.get('rt_ab', 'A')

                            if self.rt_ab_flag is not None and self.rt_ab_flag != rt_ab:
                                self.stats['rt'] = self.rt_buffer.strip()
                                self.rt_buffer = ''

                            self.rt_ab_flag = rt_ab

                            if rt_segment and len(rt_segment) > len(self.rt_buffer):
                                self.rt_buffer = rt_segment
                                self.stats['rt'] = rt_segment

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
                                rt_segment = data['partial_radiotext'].strip()
                                if rt_segment and len(rt_segment) > len(self.stats.get('rt', '')):
                                    self.stats['rt'] = rt_segment
                                    rt_found = True
                                    logger.info(f"RT trouvé: {rt_segment}")

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
        """Surveille le niveau du signal et envoie des alertes"""
        logger.info("Thread de surveillance démarré")

        while self.running:
            try:
                with self.stats_lock:
                    current_level = self.stats['current_level']

                threshold = self.audio_config['silence_threshold']

                if current_level < threshold:
                    if self.signal_ok:
                        self.signal_ok = False
                        self.silence_start_time = time.time()
                        logger.warning(f"Signal faible détecté: {current_level:.2f} dB")
                    else:
                        silence_duration = time.time() - self.silence_start_time

                        if silence_duration >= self.audio_config['silence_duration'] and not self.alert_sent:
                            logger.error(f"Signal perdu depuis {silence_duration:.0f}s - ENVOI ALERTE")

                            success = self.email_alert.send_alert(
                                alert_type="Signal FM perdu",
                                details=f"Niveau: {current_level:.2f} dB, Durée: {int(silence_duration)}s"
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
                                    message=f"Signal perdu - {current_level:.2f} dB",
                                    email_sent=True
                                )
                else:
                    if not self.signal_ok:
                        logger.info(f"Signal rétabli: {current_level:.2f} dB")

                    self.signal_ok = True
                    self.silence_start_time = None
                    self.alert_sent = False

                # Mettre à jour uptime
                if self.stats['start_time']:
                    uptime = (datetime.now() - self.stats['start_time']).total_seconds()
                    with self.stats_lock:
                        self.stats['uptime'] = int(uptime)

                time.sleep(1)

            except Exception as e:
                logger.error(f"Erreur surveillance: {e}")
                time.sleep(1)

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
        stats['frequency'] = self.rtl_config['frequency']

        if stats['start_time']:
            stats['start_time'] = stats['start_time'].strftime('%d/%m/%Y %H:%M:%S')

        return stats

    def stop(self):
        """Arrête le moniteur"""
        logger.info("Arrêt du moniteur FM")
        self.running = False

        if self.master_process:
            self.master_process.kill()

        os.system("pkill -9 rtl_fm 2>/dev/null")
        os.system("pkill -9 sox 2>/dev/null")
        os.system("pkill -9 redsea 2>/dev/null")

        # Supprimer le FIFO
        fifo_path = '/tmp/fm_stream.mp3'
        if os.path.exists(fifo_path):
            try:
                os.remove(fifo_path)
                logger.info("FIFO supprimé")
            except:
                pass

        self.stats['status'] = 'Arrêté'
