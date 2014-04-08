#!/usr/bin/env python

# Copyright 2012 Dimitri Stolnikov <horiz0n@gmx.net>
# Copyright 2012 Steve Markgraf <steve@steve-m.de>

# Adjust the center frequency (-f) and gain (-g) according to your needs.
# Use left click in Wideband Spectrum window to roughly select a GSM carrier.
# In Wideband Spectrum you can also tune by 1/4 of the bandwidth by clicking on
# the rightmost/leftmost spectrum side.
# Use left click in Channel Spectrum windows to fine tune the carrier by
# clicking on the left or right side of the spectrum.


import sys
import math
from gnuradio import gr, gru, eng_notation, blks2, optfir
from gnuradio.eng_option import eng_option
from gnuradio.wxgui import fftsink2
from gnuradio.wxgui import forms
from grc_gnuradio import wxgui as grc_wxgui
from optparse import OptionParser
import osmosdr
import wx
for extdir in ['../../debug/src/lib','../../debug/src/lib/.libs','../lib','../lib/.libs']:
    if extdir not in sys.path:
        sys.path.append(extdir)
import gsm

class tune_corrector(gr.feval_dd):
    def __init__(self, top_block):
        gr.feval_dd.__init__(self)
        self.top_block = top_block
    def eval(self, freq_offset):
        self.top_block.offset = self.top_block.offset + int(freq_offset)
        self.top_block.tuner.set_center_freq(self.top_block.offset)
        return freq_offset

class synchronizer(gr.feval_dd):
    def __init__(self, top_block):
        gr.feval_dd.__init__(self)
        self.top_block = top_block

    def eval(self, timing_offset):
        return timing_offset


# applies frequency translation, resampling and demodulation

class top_block(grc_wxgui.top_block_gui):
  def __init__(self):
    grc_wxgui.top_block_gui.__init__(self, title="Top Block")

    options = get_options()

    self.tune_corrector_callback = tune_corrector(self)
    self.synchronizer_callback = synchronizer(self)
    self.converter = gr.vector_to_stream(gr.sizeof_float, 142)

    self.ifreq = options.frequency
    self.rfgain = options.gain

    self.src = osmosdr.source_c(options.args)
    
    # added by scateu @ 2014-1-9
    self.src.set_freq_corr(0, 0)
    self.src.set_dc_offset_mode(1, 0)
    self.src.set_iq_balance_mode(0, 0)
    self.src.set_gain_mode(0, 0)
    self.src.set_gain(14, 0)
    self.src.set_if_gain(58, 0)
    self.src.set_bb_gain(20, 0)
    self.src.set_antenna("", 0)
    self.src.set_bandwidth(0, 0)

    self.src.set_center_freq(self.ifreq)
    self.src.set_sample_rate(int(options.sample_rate))

    if self.rfgain is None:
        self.src.set_gain_mode(1)
        self.iagc = 1
        self.rfgain = 0
    else:
        self.iagc = 0
        self.src.set_gain_mode(0)
        self.src.set_gain(self.rfgain)

    # may differ from the requested rate
    sample_rate = self.src.get_sample_rate()
    sys.stderr.write("sample rate: %d\n" % (sample_rate))

    gsm_symb_rate = 1625000.0 / 6.0
    sps = sample_rate / gsm_symb_rate / 4
    out_sample_rate = gsm_symb_rate * 4

    self.offset = 0

    taps = gr.firdes.low_pass(1.0, sample_rate, 145e3, 10e3, gr.firdes.WIN_HANN)
    self.tuner = gr.freq_xlating_fir_filter_ccf(1, taps, self.offset, sample_rate)

    self.interpolator = gr.fractional_interpolator_cc(0, sps)

    self.receiver = gsm.receiver_cf(
        self.tune_corrector_callback, self.synchronizer_callback, 4,
        options.key.replace(' ', '').lower(),
        options.configuration.upper())

    self.output = gr.file_sink(gr.sizeof_float, options.output_file)

    self.connect(self.src, self.tuner, self.interpolator, self.receiver, self.converter, self.output)

    def set_ifreq(ifreq):
        self.ifreq = ifreq
        self._ifreq_text_box.set_value(self.ifreq)
        self.src.set_center_freq(self.ifreq)

    self._ifreq_text_box = forms.text_box(
        parent=self.GetWin(),
        value=self.ifreq,
        callback=set_ifreq,
        label="Center Frequency",
        converter=forms.float_converter(),
    )
    self.Add(self._ifreq_text_box)

    def set_iagc(iagc):
        self.iagc = iagc
        self._agc_check_box.set_value(self.iagc)
        self.src.set_gain_mode(self.iagc, 0)
        self.src.set_gain(0 if self.iagc == 1 else self.rfgain, 0)

    self._agc_check_box = forms.check_box(
        parent=self.GetWin(),
        value=self.iagc,
        callback=set_iagc,
        label="Automatic Gain",
        true=1,
        false=0,
    )

    self.Add(self._agc_check_box)

    def set_rfgain(rfgain):
        self.rfgain = rfgain
        self._rfgain_slider.set_value(self.rfgain)
        self._rfgain_text_box.set_value(self.rfgain)
        self.src.set_gain(0 if self.iagc == 1 else self.rfgain, 0)

    _rfgain_sizer = wx.BoxSizer(wx.VERTICAL)
    self._rfgain_text_box = forms.text_box(
        parent=self.GetWin(),
        sizer=_rfgain_sizer,
        value=self.rfgain,
        callback=set_rfgain,
        label="RF Gain",
        converter=forms.float_converter(),
        proportion=0,
    )
    self._rfgain_slider = forms.slider(
        parent=self.GetWin(),
        sizer=_rfgain_sizer,
        value=self.rfgain,
        callback=set_rfgain,
        minimum=0,
        maximum=50,
        num_steps=200,
        style=wx.SL_HORIZONTAL,
        cast=float,
        proportion=1,
    )

    self.Add(_rfgain_sizer)

    def fftsink2_callback(x, y):
        if abs(x / (sample_rate / 2)) > 0.9:
            set_ifreq(self.ifreq + x / 2)
        else:
            sys.stderr.write("coarse tuned to: %d Hz\n" % x)
            self.offset = -x
            self.tuner.set_center_freq(self.offset)

    self.scope = fftsink2.fft_sink_c(self.GetWin(),
        title="Wideband Spectrum (click to coarse tune)",
        fft_size=1024,
        sample_rate=sample_rate,
        ref_scale=2.0,
        ref_level=0,
        y_divs=10,
        fft_rate=10,
        average=False,
        avg_alpha=0.3)

    self.Add(self.scope.win)
    self.scope.set_callback(fftsink2_callback)

    self.connect(self.src, self.scope)

    def fftsink2_callback2(x, y):
        self.offset = self.offset - (x / 10)
        sys.stderr.write("fine tuned to: %d Hz\n" % self.offset)
        self.tuner.set_center_freq(self.offset)

    self.scope2 = fftsink2.fft_sink_c(self.GetWin(),
        title="Channel Spectrum (click to fine tune)",
        fft_size=1024,
        sample_rate=gsm_symb_rate * 4,
        ref_scale=2.0,
        ref_level=-20,
        y_divs=10,
        fft_rate=10,
        average=False,
        avg_alpha=0.3)

    self.Add(self.scope2.win)
    self.scope2.set_callback(fftsink2_callback2)

    self.connect(self.interpolator, self.scope2)

def get_options():
    parser = OptionParser(option_class=eng_option)
    parser.add_option("-a", "--args", type="string", default="",
        help="gr-osmosdr device arguments")
    parser.add_option("-s", "--sample-rate", type="eng_float", default=1800000,
        help="set receiver sample rate (default 1800000)")
    parser.add_option("-f", "--frequency", type="eng_float", default=924.2e6,
        help="set receiver center frequency")
    parser.add_option("-g", "--gain", type="eng_float", default=None,
        help="set receiver gain")

    # demodulator related settings
    parser.add_option("-o", "--output-file", type="string", default="cfile2.out", help="specify the output file")
    parser.add_option("-v", "--verbose", action="store_true", default=False, help="dump demodulation data")
    parser.add_option("-k", "--key", type="string", default="AD 6A 3E C2 B4 42 E4 00", help="KC session key")
    parser.add_option("-c", "--configuration", type="string", default="0B", help="Decoder configuration")
    (options, args) = parser.parse_args()
    if len(args) != 0:
        parser.print_help()
        raise SystemExit, 1

    return (options)

if __name__ == '__main__':
        tb = top_block()
        tb.Run(True)
