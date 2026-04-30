#!/usr/bin/env python3
"""
Module d'analyse du signal MPX FM
Mesure la déviation FM, le pilote 19 kHz, le stéréo 38 kHz, le RDS 57 kHz,
les niveaux L/R séparés et le SNR.

Conçu pour fonctionner sur Raspberry Pi 3B+ (léger, filtres pré-calculés).

Décodage stéréo :
    - L+R : passe-bas 15 kHz sur MPX (audio mono)
    - Récupération porteuse 38 kHz : pilot² → passe-bande 38 kHz → normalisation
    - L-R : passe-bande 23-53 kHz × porteuse → passe-bas 15 kHz
    - L = (L+R + L-R) / 2  |  R = (L+R - L-R) / 2

SNR :
    - Signal   : bande audio 100 Hz – 15 kHz (L+R)
    - Bruit    : bande 60 – 75 kHz (aucun contenu FM standard)
    - SNR (dB) : 20 × log10(signal_rms / noise_rms)
"""

import numpy as np
from scipy import signal as scipy_signal
import threading
import logging

logger = logging.getLogger(__name__)

SAMPLE_RATE     = 171000
MAX_DEV_HZ      = 75_000.0
PILOT_FREQ      = 19_000
STEREO_FREQ     = 38_000
RDS_FREQ        = 57_000

PILOT_DETECT_DB  = -60.0
STEREO_DETECT_DB = -60.0
RDS_DETECT_DB    = -75.0


class MPXAnalyzer:

    def __init__(self, sample_rate: int = SAMPLE_RATE, process_every: int = 4):
        self.sample_rate   = sample_rate
        self.process_every = process_every
        self._ema_alpha = 0.05  # lissage EMA (0=très lisse, 1=pas de lissage)
        self._ema = {
            'mpx_power': None, 'pilot_level': None,
            'stereo_level': None, 'rds_level': None, 'snr': None,
            'deviation_peak': None, 'deviation_rms': None
        }
        self._counter      = 0
        self._fft_size     = 2048
        self._fft_window   = np.hanning(self._fft_size)
        self._fft_avg      = None   # moyenne glissante EMA sur FFT
        self._fft_alpha    = 0.3    # lissage FFT (moins fort pour garder les pics)
        self._lock         = threading.Lock()

        self._results = {
            'mpx_enabled':     True,
            'deviation_peak':  0.0,
            'deviation_rms':   0.0,
            'mpx_power':      -100.0,
            'pilot_level':    -100.0,
            'pilot_present':   False,
            'stereo_level':   -100.0,
            'stereo_present':  False,
            'rds_level':      -100.0,
            'rds_rf_present':  False,
            'level_left':     -100.0,
            'level_right':    -100.0,
            'snr':             0.0,
            'fft_spectrum':    [],
        }

        nyq = sample_rate / 2.0

        # Pilote 19 kHz ± 300 Hz
        self._b_pilot, self._a_pilot = scipy_signal.butter(
            4, [(PILOT_FREQ - 300) / nyq, (PILOT_FREQ + 300) / nyq], btype='bandpass')

        # Porteuse 38 kHz ± 1 kHz (nettoyage du pilot²)
        self._b_c38, self._a_c38 = scipy_signal.butter(
            4, [(STEREO_FREQ - 1_000) / nyq, (STEREO_FREQ + 1_000) / nyq], btype='bandpass')

        # L+R audio 100 Hz – 15 kHz
        self._b_lpr, self._a_lpr = scipy_signal.butter(
            4, [100 / nyq, 15_000 / nyq], btype='bandpass')

        # L-R DSB-SC 23 – 53 kHz
        self._b_lmr, self._a_lmr = scipy_signal.butter(
            4, [23_000 / nyq, 53_000 / nyq], btype='bandpass')

        # Passe-bas post-démodulation L-R 15 kHz
        self._b_lmr_lp, self._a_lmr_lp = scipy_signal.butter(
            4, 15_000 / nyq, btype='low')

        # Stéréo 38 kHz (mesure niveau sous-porteuse)
        self._b_stereo, self._a_stereo = scipy_signal.butter(
            4, [23_000 / nyq, 53_000 / nyq], btype='bandpass')

        # RDS 57 kHz ± 4 kHz
        self._b_rds, self._a_rds = scipy_signal.butter(
            4, [(RDS_FREQ - 4_000) / nyq, (RDS_FREQ + 4_000) / nyq], btype='bandpass')

        # Bruit 60 – 75 kHz (SNR)
        self._b_noise, self._a_noise = scipy_signal.butter(
            4, [60_000 / nyq, 75_000 / nyq], btype='bandpass')

        logger.info(f"MPXAnalyzer initialisé — fs={sample_rate} Hz, traitement 1/{process_every} chunks, L/R+SNR activés")

    def process_chunk(self, samples_int16: np.ndarray) -> None:
        self._counter += 1
        if self._counter % self.process_every != 0:
            return
        if len(samples_int16) < 512:
            return

        try:
            mpx = samples_int16.astype(np.float32) / 32768.0

            # 1. Puissance MPX totale
            mpx_rms = float(np.sqrt(np.mean(mpx ** 2)))
            mpx_db  = _rms_to_db(mpx_rms)

            # 2. Déviation FM
            peak     = float(np.max(np.abs(mpx)))
            dev_peak = round(peak * MAX_DEV_HZ / 1000.0, 1)
            dev_rms  = round(mpx_rms * MAX_DEV_HZ / 1000.0, 1)

            # 3. Pilote 19 kHz
            pilot_sig = scipy_signal.lfilter(self._b_pilot, self._a_pilot, mpx)
            pilot_rms = float(np.sqrt(np.mean(pilot_sig ** 2)))
            pilot_db  = _rms_to_db(pilot_rms)

            # 4. Stéréo 38 kHz (niveau sous-porteuse)
            stereo     = scipy_signal.lfilter(self._b_stereo, self._a_stereo, mpx)
            stereo_rms = float(np.sqrt(np.mean(stereo ** 2)))
            stereo_db  = _rms_to_db(stereo_rms)

            # 5. RDS 57 kHz
            rds     = scipy_signal.lfilter(self._b_rds, self._a_rds, mpx)
            rds_rms = float(np.sqrt(np.mean(rds ** 2)))
            rds_db  = _rms_to_db(rds_rms)

            # 6. Décodage L/R
            # a) L+R audio mono
            lpr = scipy_signal.lfilter(self._b_lpr, self._a_lpr, mpx)

            # b) Récupération porteuse 38 kHz : pilot² → bandpass 38 kHz → normalisation
            carrier_sq  = pilot_sig ** 2
            carrier_38k = scipy_signal.lfilter(self._b_c38, self._a_c38, carrier_sq)
            c_peak      = float(np.max(np.abs(carrier_38k))) + 1e-10
            carrier_n   = carrier_38k / c_peak

            # c) Démodulation L-R DSB-SC
            lmr_band  = scipy_signal.lfilter(self._b_lmr, self._a_lmr, mpx)
            lmr_demod = lmr_band * carrier_n * 2.0
            lmr       = scipy_signal.lfilter(self._b_lmr_lp, self._a_lmr_lp, lmr_demod)

            # d) L = (L+R + L-R) / 2  |  R = (L+R - L-R) / 2
            l_audio = (lpr + lmr) / 2.0
            r_audio = (lpr - lmr) / 2.0
            l_db = _rms_to_db(float(np.sqrt(np.mean(l_audio ** 2))))
            r_db = _rms_to_db(float(np.sqrt(np.mean(r_audio ** 2))))

            # 7. SNR
            lpr_rms   = float(np.sqrt(np.mean(lpr ** 2)))
            noise     = scipy_signal.lfilter(self._b_noise, self._a_noise, mpx)
            noise_rms = float(np.sqrt(np.mean(noise ** 2))) + 1e-10
            snr_db    = round(20.0 * np.log10(max(lpr_rms, 1e-10) / noise_rms), 1)
            snr_db    = float(np.clip(snr_db, 0.0, 80.0))

            # 8. FFT spectre MPX
            chunk_fft = mpx[:self._fft_size] if len(mpx) >= self._fft_size else np.pad(mpx, (0, self._fft_size - len(mpx)))
            windowed  = chunk_fft * self._fft_window
            spectrum  = np.abs(np.fft.rfft(windowed))
            # Convertir en dB avec plancher à -100 dB
            spectrum_db = 20 * np.log10(np.maximum(spectrum * 2 / self._fft_size, 1e-10))
            # Moyenne glissante EMA sur le spectre
            if self._fft_avg is None:
                self._fft_avg = spectrum_db
            else:
                self._fft_avg = self._fft_alpha * spectrum_db + (1 - self._fft_alpha) * self._fft_avg
            # Réduire à 512 points pour l'API (décimation)
            fft_decimated = self._fft_avg[::len(self._fft_avg)//512][:512]

            # Lissage EMA
            a = self._ema_alpha
            def ema(key, val):
                if self._ema[key] is None:
                    self._ema[key] = val
                else:
                    self._ema[key] = a * val + (1 - a) * self._ema[key]
                return round(self._ema[key], 1)

            with self._lock:
                self._results.update({
                    'deviation_peak':  ema('deviation_peak', dev_peak),
                    'deviation_rms':   ema('deviation_rms', dev_rms),
                    'mpx_power':       ema('mpx_power', mpx_db),
                    'pilot_level':     ema('pilot_level', pilot_db),
                    'pilot_present':   bool(pilot_db > PILOT_DETECT_DB),
                    'stereo_level':    ema('stereo_level', stereo_db),
                    'stereo_present':  bool(stereo_db > STEREO_DETECT_DB),
                    'rds_level':       ema('rds_level', rds_db),
                    'rds_rf_present':  bool(rds_db > RDS_DETECT_DB),
                    'level_left':      round(l_db, 1),
                    'level_right':     round(r_db, 1),
                    'snr':             ema('snr', snr_db),
                    'fft_spectrum':    [round(float(x), 1) for x in fft_decimated],
                })

        except Exception as exc:
            logger.debug(f"MPXAnalyzer.process_chunk: {exc}")

    def get_results(self) -> dict:
        with self._lock:
            return self._results.copy()

    def reset(self) -> None:
        with self._lock:
            self._results.update({
                'deviation_peak':  0.0,
                'deviation_rms':   0.0,
                'mpx_power':      -100.0,
                'pilot_level':    -100.0,
                'pilot_present':   False,
                'stereo_level':   -100.0,
                'stereo_present':  False,
                'rds_level':      -100.0,
                'rds_rf_present':  False,
                'level_left':     -100.0,
                'level_right':    -100.0,
                'snr':             0.0,
            })
        self._counter = 0


def _rms_to_db(rms: float) -> float:
    return 20.0 * np.log10(rms) if rms > 1e-10 else -100.0
