#!/usr/bin/env python3
"""
Module de gestion de la base de données SQLite
Enregistre l'historique des niveaux audio, alertes et RDS
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class FMDatabase:
    def __init__(self, db_path='fm_monitor.db'):
        """Initialise la base de données"""
        self.db_path = db_path
        # Activer WAL mode pour éviter les locks
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=5000')
        conn.close()
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager pour les connexions DB"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Erreur base de données: {e}")
            raise
        finally:
            conn.close()
    
    def init_database(self):
        """Crée les tables si elles n'existent pas"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Table des niveaux audio (enregistrement toutes les 5s)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audio_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    level_db REAL NOT NULL,
                    signal_ok BOOLEAN NOT NULL
                )
            ''')
            
            # Index pour les requêtes temporelles
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_audio_timestamp 
                ON audio_levels(timestamp)
            ''')
            
            # Table des alertes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    alert_type TEXT NOT NULL,
                    level_db REAL,
                    duration_seconds INTEGER,
                    message TEXT,
                    email_sent BOOLEAN DEFAULT 0
                )
            ''')
            
            # Table historique RDS (optionnel, pour analyse)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rds_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ps TEXT,
                    rt TEXT
                )
            ''')
            
            logger.info("Base de données initialisée")
    
    def save_audio_level(self, level_db, signal_ok):
        """Enregistre un niveau audio"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO audio_levels (level_db, signal_ok)
                    VALUES (?, ?)
                ''', (level_db, signal_ok))
        except Exception as e:
            logger.error(f"Erreur sauvegarde niveau: {e}")
    
    def save_alert(self, alert_type, level_db, duration_seconds, message, email_sent=False):
        """Enregistre une alerte"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO alerts (timestamp, alert_type, level_db, duration_seconds, message, email_sent)
                    VALUES (datetime('now', 'localtime'), ?, ?, ?, ?, ?)
                ''', (alert_type, level_db, duration_seconds, message, email_sent))
                logger.info(f"Alerte enregistrée: {alert_type}")
        except Exception as e:
            logger.error(f"Erreur sauvegarde alerte: {e}")
    
    def save_rds(self, ps, rt):
        """Enregistre les données RDS (optionnel)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO rds_history (ps, rt)
                    VALUES (?, ?)
                ''', (ps, rt))
        except Exception as e:
            logger.error(f"Erreur sauvegarde RDS: {e}")
    
    def get_audio_history(self, hours=24):
        """Récupère l'historique des niveaux audio"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                since = datetime.now() - timedelta(hours=hours)
                
                cursor.execute('''
                    SELECT timestamp, level_db, signal_ok
                    FROM audio_levels
                    WHERE timestamp >= ?
                    ORDER BY timestamp ASC
                ''', (since,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erreur récupération historique: {e}")
            return []
    
    def get_alerts_history(self, limit=50):
        """Récupère l'historique des alertes"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT timestamp, alert_type, level_db, duration_seconds, message, email_sent
                    FROM alerts
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Erreur récupération alertes: {e}")
            return []
    
    def get_alerts_history_grouped(self, limit=50):
        """Récupère l'historique des alertes regroupées par paires (perte + retour)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Récupérer toutes les alertes
                cursor.execute('''
                    SELECT timestamp, alert_type, level_db, duration_seconds, message, email_sent
                    FROM alerts
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit * 2,))  # Doubler la limite car on regroupe
                
                alerts = [dict(row) for row in cursor.fetchall()]
                
                # Regrouper les alertes par paires
                grouped = []
                i = 0
                
                while i < len(alerts):
                    alert = alerts[i]
                    
                    if alert['alert_type'] == 'signal_restored':
                        # Chercher le signal_lost correspondant (juste après dans la liste inversée)
                        signal_lost = None
                        if i + 1 < len(alerts) and alerts[i + 1]['alert_type'] == 'signal_lost':
                            signal_lost = alerts[i + 1]
                            i += 2  # Sauter les deux
                        else:
                            # Pas de signal_lost trouvé, afficher quand même le restored seul
                            grouped.append({
                                'start_time': alert['timestamp'],
                                'end_time': alert['timestamp'],
                                'duration': alert['duration_seconds'] or 0,
                                'level_lost': alert['level_db'],
                                'level_restored': alert['level_db'],
                                'emails_sent': 1 if alert['email_sent'] else 0,
                                'status': 'restored_only'
                            })
                            i += 1
                            continue
                        
                        # Créer l'entrée groupée
                        grouped.append({
                            'start_time': signal_lost['timestamp'],
                            'end_time': alert['timestamp'],
                            'duration': alert['duration_seconds'] or signal_lost['duration_seconds'] or 0,
                            'level_lost': signal_lost['level_db'],
                            'level_restored': alert['level_db'],
                            'emails_sent': (1 if signal_lost['email_sent'] else 0) + (1 if alert['email_sent'] else 0),
                            'status': 'complete'
                        })
                    
                    elif alert['alert_type'] == 'signal_lost':
                        # Signal perdu sans rétablissement (encore en cours ou pas de restored)
                        grouped.append({
                            'start_time': alert['timestamp'],
                            'end_time': None,
                            'duration': alert['duration_seconds'] or 0,
                            'level_lost': alert['level_db'],
                            'level_restored': None,
                            'emails_sent': 1 if alert['email_sent'] else 0,
                            'status': 'ongoing'
                        })
                        i += 1
                    else:
                        i += 1
                
                return grouped[:limit]  # Limiter au nombre demandé
                
        except Exception as e:
            logger.error(f"Erreur récupération alertes groupées: {e}")
            return []
    
    def cleanup_old_data(self, days=7):
        """Nettoie les données de plus de X jours"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cutoff = datetime.now() - timedelta(days=days)
                
                cursor.execute('DELETE FROM audio_levels WHERE timestamp < ?', (cutoff,))
                deleted = cursor.rowcount
                
                logger.info(f"Nettoyage: {deleted} enregistrements supprimés")
                return deleted
        except Exception as e:
            logger.error(f"Erreur nettoyage: {e}")
            return 0
