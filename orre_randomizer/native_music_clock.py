"""GameCube DAC clock correction, independent of emulator speed.

Dolphin 2609b uses 108 MHz / 3372 for GameCube audio at a nominal 32 kHz.
The fixed 1125/1124 ratio follows that hardware clock independently of game speed.
"""
from array import array

GC_CLOCK_NUMERATOR = 1125
GC_CLOCK_DENOMINATOR = 1124
GC_CLOCK_RATIO = GC_CLOCK_NUMERATOR / GC_CLOCK_DENOMINATOR


class ConsoleDacClock:
    """Resample nominal 32 kHz synthesis onto the corrected console clock.

Only the two samples around the next source position are retained. Keeping an
integer phase makes output independent of 20 ms packet boundaries and allows
the existing synthesis journal to reconstruct the exact same clock state.
"""
    def __init__(self):
        self.phase = 0
        self.pending = array('h')
        self.generated_source_frames = 0
        self.consumed_source_frames = 0

    def render(self, frames, source):
        if type(frames) is not int or not 0 < frames <= 32000:
            raise ValueError('Music clock block exceeds bounds')
        needed = (self.phase + (frames - 1) * GC_CLOCK_NUMERATOR) // GC_CLOCK_DENOMINATOR + 2
        missing = needed - len(self.pending) // 2
        while missing > 0:
            count = min(missing, 32000)
            block = source(count)
            if not isinstance(block, array) or block.typecode != 'h' or len(block) != count * 2:
                raise ValueError('Music source returned an invalid PCM block')
            self.pending.extend(block)
            self.generated_source_frames += count
            missing -= count
        output = array('h')
        phase = self.phase
        for _ in range(frames):
            low, fraction = divmod(phase, GC_CLOCK_DENOMINATOR)
            for channel in (0, 1):
                first = self.pending[low * 2 + channel]
                second = self.pending[(low + 1) * 2 + channel]
                output.append(round((first * (GC_CLOCK_DENOMINATOR - fraction) + second * fraction) / GC_CLOCK_DENOMINATOR))
            phase += GC_CLOCK_NUMERATOR
        consumed, self.phase = divmod(phase, GC_CLOCK_DENOMINATOR)
        del self.pending[:consumed * 2]
        self.consumed_source_frames += consumed
        return output
