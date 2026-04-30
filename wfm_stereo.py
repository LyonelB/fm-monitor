#!/usr/bin/env python3
"""
GNU Radio WFM stéréo pour FM Monitor
- Branche A : audio stéréo S16LE 48kHz → stdout → ffmpeg → Icecast
- Branche B : MPX démodulé mono S16LE 240kHz → FIFO → redsea → /tmp/rds_output.json
"""
from gnuradio import gr, analog, blocks
import osmosdr
import sys
import os

RDS_FIFO = '/tmp/rds_gnuradio.pcm'
MPX_FIFO = '/tmp/mpx_gnuradio.pcm'

class WFMStereo(gr.top_block):
    def __init__(self, freq=88.6e6, gain=40, ppm=0):
        gr.top_block.__init__(self, "WFM Stereo FM Monitor")

        samp_rate  = 1200000
        audio_rate = 48000
        mpx_decim  = 5        # 1200000 / 5 = 240000 Hz

        # ── Source RTL-SDR ────────────────────────────────────────────
        self.src = osmosdr.source(args="numchan=1 rtl=0")
        self.src.set_sample_rate(samp_rate)
        self.src.set_center_freq(freq)
        # gain 'auto' ou -1 → AGC activé via set_gain_mode
        if str(gain).strip() in ('auto', '-1', 'AUTO'):
            self.src.set_gain_mode(True, 0)  # AGC hardware
        else:
            self.src.set_gain_mode(False, 0)
            self.src.set_gain(float(gain), 0)
        self.src.set_freq_corr(ppm)

        # ── Branche A : WFM stéréo → stdout ──────────────────────────
        self.wfm = analog.wfm_rcv_pll(
            demod_rate=samp_rate,
            audio_decimation=samp_rate // audio_rate,
            deemph_tau=50e-6
        )
        self.mult_l     = blocks.multiply_const_ff(32767)
        self.mult_r     = blocks.multiply_const_ff(32767)
        self.f2s_l      = blocks.float_to_short(1, 1)
        self.f2s_r      = blocks.float_to_short(1, 1)
        self.interleave = blocks.interleave(gr.sizeof_short)
        self.audio_sink = blocks.file_descriptor_sink(gr.sizeof_short, 1)

        self.connect(self.src, self.wfm)
        self.connect((self.wfm, 0), self.mult_l, self.f2s_l, (self.interleave, 0))
        self.connect((self.wfm, 1), self.mult_r, self.f2s_r, (self.interleave, 1))
        self.connect(self.interleave, self.audio_sink)

        # ── Branche B : signal IQ décimé → FIFO pour redsea ─────────
        # redsea attend du PCM mono S16LE à 171kHz (même format que rtl_fm)
        # On décime 1200000 / 7 ≈ 171428 Hz puis on extrait la partie réelle
        from gnuradio.filter import firdes
        from gnuradio import filter as grfilter

        decim_b = 7  # 1200000 / 7 ≈ 171428 Hz
        taps = firdes.low_pass(1.0, samp_rate, 80000, 20000)
        self.decim_b    = grfilter.fir_filter_ccf(decim_b, taps)
        self.fm_demod_b = analog.fm_demod_cf(
            channel_rate=samp_rate // decim_b,
            audio_decim=1,
            deviation=75000,
            audio_pass=75000,
            audio_stop=80000,
            gain=1.0,
            tau=0.0
        )
        self.mult_mpx = blocks.multiply_const_ff(32767)
        self.f2s_mpx  = blocks.float_to_short(1, 1)
        self.mpx_sink = blocks.file_sink(gr.sizeof_short, RDS_FIFO, False)
        self.mpx_sink.set_unbuffered(True)
        self.mpx_sink2 = blocks.file_sink(gr.sizeof_short, MPX_FIFO, False)
        self.mpx_sink2.set_unbuffered(True)

        self.connect(self.src, self.decim_b, self.fm_demod_b, self.mult_mpx, self.f2s_mpx)
        self.connect(self.f2s_mpx, self.mpx_sink)
        self.connect(self.f2s_mpx, self.mpx_sink2)


if __name__ == "__main__":
    freq = float(sys.argv[1]) * 1e6 if len(sys.argv) > 1 else 88.6e6
    gain = float(sys.argv[2]) if len(sys.argv) > 2 else 40
    ppm  = int(sys.argv[3])   if len(sys.argv) > 3 else 0

    if not os.path.exists(RDS_FIFO):
        os.mkfifo(RDS_FIFO)
    if not os.path.exists(MPX_FIFO):
        os.mkfifo(MPX_FIFO)


    tb = WFMStereo(freq=freq, gain=gain, ppm=ppm)
    import signal
    tb.start()
    try:
        signal.pause()
    except KeyboardInterrupt:
        pass
    tb.stop()
    tb.wait()
