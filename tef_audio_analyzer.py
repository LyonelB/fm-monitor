#!/usr/bin/env python3
"""
TEFAudioAnalyzer — numpy pur, 50ms chunks, interface MPXAnalyzer compatible.
"""
import subprocess, threading, logging, numpy as np
logger = logging.getLogger(__name__)
SAMPLE_RATE=48000; CHUNK_FRAMES=2400; BYTES_PER_FRAME=4

class TEFAudioAnalyzer:
    def __init__(self, alsa_device='hw:Tuner', sample_rate=SAMPLE_RATE, chunk_frames=CHUNK_FRAMES):
        self.alsa_device=alsa_device; self.sample_rate=sample_rate; self.chunk_frames=chunk_frames
        self._lock=threading.Lock(); self._running=False; self._thread=None; self._proc=None
        freq_res=sample_rate/chunk_frames
        self._sig_lo=int(100/freq_res); self._sig_hi=int(15000/freq_res)
        self._noise_lo=int(15000/freq_res); self._noise_hi=int(23000/freq_res)
        # Spectre audio pour l'affichage : 0-20 kHz décimé en ~256 points.
        self._spec_freq_res=freq_res
        self._spec_hi=int(20000/freq_res)          # dernier bin utile (20 kHz)
        self._spec_points=256                       # points envoyés au front
        self.spectrum_hz_per_point=20000.0/self._spec_points
        self._results={'mpx_enabled':True,'deviation_peak':0.0,'deviation_rms':0.0,
            'mpx_power':-100.0,'pilot_level':-100.0,'pilot_present':False,
            'stereo_level':-100.0,'stereo_present':False,'rds_level':-100.0,
            'rds_rf_present':False,'level_left':-100.0,'level_right':-100.0,'snr':0.0,
            'fft_spectrum':[]}
        self._stereo_buf = []   # conservé pour compatibilité mais inutilisé
        logger.info(f"TEFAudioAnalyzer initialisé — {alsa_device}, {sample_rate}Hz stéréo, {chunk_frames} frames/50ms (numpy pur)")

    def start(self):
        if self._running: return
        self._running=True
        self._thread=threading.Thread(target=self._capture_loop,daemon=True,name='tef-audio-analyzer')
        self._thread.start(); logger.info("TEFAudioAnalyzer démarré")

    def stop(self):
        self._running=False
        if self._proc:
            try: self._proc.kill()
            except: pass
            self._proc=None
        if self._thread and self._thread.is_alive(): self._thread.join(timeout=4)
        logger.info("TEFAudioAnalyzer arrêté")

    def get_results(self):
        with self._lock: return self._results.copy()

    def reset(self):
        with self._lock:
            self._results.update({'deviation_peak':0.0,'deviation_rms':0.0,'mpx_power':-100.0,
                'pilot_level':-100.0,'pilot_present':False,'stereo_level':-100.0,
                'stereo_present':False,'rds_level':-100.0,'rds_rf_present':False,
                'level_left':-100.0,'level_right':-100.0,'snr':0.0,'fft_spectrum':[]})

    def is_alive(self): return self._thread is not None and self._thread.is_alive()

    def _capture_loop(self):
        cmd=['arecord','-D',self.alsa_device,'-f','S16_LE','-r',str(self.sample_rate),
             '-c','2','-t','raw','--buffer-size',str(self.chunk_frames*4)]
        import time
        while self._running:
            try:
                self._proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
                bpc=self.chunk_frames*BYTES_PER_FRAME; buf=b''
                while self._running and self._proc.poll() is None:
                    d=self._proc.stdout.read(bpc-len(buf))
                    if not d: break
                    buf+=d
                    if len(buf)>=bpc: self._process(buf[:bpc]); buf=buf[bpc:]
            except Exception as e: logger.error(f"TEFAudioAnalyzer capture: {e}")
            finally:
                if self._proc:
                    try: self._proc.kill()
                    except: pass
                    self._proc=None
            if self._running: time.sleep(5)

    def _process(self, raw):
        try:
            s=np.frombuffer(raw,dtype=np.int16).astype(np.float32)/32768.0
            if len(s)<256: return
            L=s[0::2]; R=s[1::2]; M=(L+R)*0.5
            l_db=_rms_to_db(float(np.sqrt(np.mean(L**2))))
            r_db=_rms_to_db(float(np.sqrt(np.mean(R**2))))
            mpx_db=_rms_to_db(float(np.sqrt(np.mean(M**2))))
            win=np.hanning(len(M)); fft=np.abs(np.fft.rfft(M*win))
            sig=float(np.sum(fft[self._sig_lo:self._sig_hi]**2))+1e-20
            noise=float(np.sum(fft[self._noise_lo:self._noise_hi]**2))+1e-20
            snr=float(np.clip(10.0*np.log10(sig/noise),0.0,80.0))
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
                    'fft_spectrum':fft_spectrum})
        except Exception as e: logger.debug(f"TEFAudioAnalyzer._process: {e}")

def _rms_to_db(rms): return 20.0*np.log10(rms) if rms>1e-10 else -100.0
