#!/usr/bin/env python3
# FM demodulator based on I/Q (quadrature) samples
# https://epxx.co/artigos/pythonfm_en.html

import struct, numpy, sys, math
from scipy.signal import resample, decimate
import sounddevice as sd
from scipy.signal import butter, lfilter, freqz
from rtlsdr import *
import asyncio


# My Method
def build_butter_filter(cutoff, fs, order=24):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

def apply_filter(b,a,x):
    y = lfilter(b, a, x)
    return y

class FM_Tuner:
    def __init__(self) -> None:
        self.MAX_DEVIATION = 200000 # Hz
        self.INPUT_RATE = 256000
        self.DEVIATION_X_SIGNAL = 0.99 / (math.pi * self.MAX_DEVIATION / (self.INPUT_RATE / 2))
        self.remaining_data = b''

        # His Method
        # lo_pass = filters.low_pass(INPUT_RATE, INPUT_RATE, 48)

        self.b,self.a = build_butter_filter(44100, self.INPUT_RATE)


        # configure device
        self.sdr = RtlSdr()
        self.sdr.sample_rate = self.INPUT_RATE
        self.sdr.center_freq = 144.725e6
        self.sdr.gain = 'auto'

    def _demodulateSamples( self, iqdata ):
            # iqdata = iqdata - 127.5
            # iqdata = iqdata / 128.0
            angles = numpy.angle(iqdata)

            # Determine phase rotation between samples
            # (Output one element less, that's we always save last sample
            # in remaining_data)
            rotations = numpy.ediff1d(angles)

            # Wrap rotations >= +/-180º
            rotations = (rotations + numpy.pi) % (2 * numpy.pi) - numpy.pi

            # Convert rotations to baseband signal 
            output_raw = numpy.multiply(rotations, self.DEVIATION_X_SIGNAL)
            output_raw = numpy.clip(output_raw, -0.999, +0.999)

            """
            Attempt to downsample to 44100Hz.

            Still studders but its actually not horrible
            """
            output_raw = apply_filter(self.b, self.a, output_raw)
            output_raw = resample(output_raw, int(len(output_raw) * 44100/self.INPUT_RATE))

            return output_raw    



    def getAudioSamples( self ):
        iqdata = self.sdr.read_samples(self.INPUT_RATE)
        return self._demodulateSamples( iqdata )
    
    async def asyncAudioGenerator( self ):
        async for samps in self.sdr.stream( self.INPUT_RATE ):
            yield self._demodulateSamples( samps )

    async def run( self ):
        async for audio in self.asyncAudioGenerator():
            sd.play(audio, 44100, blocking=False)


if __name__ == "__main__":
    fm = FM_Tuner()

    asyncio.run( fm.run() )
