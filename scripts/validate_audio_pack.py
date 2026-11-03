"""Measure local PCM assets without playing them or changing system volume."""
from array import array
import argparse
import json
import math
from pathlib import Path
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from colosseum_randomizer.resources import interface_assets, music_track


def measure(path, *, loop=False):
    with wave.open(str(path), "rb") as stream:
        channels, rate, frames = stream.getnchannels(), stream.getframerate(), stream.getnframes()
        if stream.getsampwidth() != 2 or stream.getcomptype() != "NONE" or channels not in (1, 2):
            raise ValueError("Expected PCM16 mono/stereo")
        if frames <= 0 or frames * channels * 2 > 48 * 1024**2:
            raise ValueError("PCM size exceeds limits")
        pcm = stream.readframes(frames)
        if len(pcm) != frames * channels * 2:
            raise ValueError("Truncated audio")
    values = array("h", pcm)
    if sys.byteorder != "little":
        values.byteswap()
    peak = max(abs(value) for value in values)
    rms = math.sqrt(sum(value * value for value in values) / len(values))
    seam = max(abs(values[index] - values[-channels+index]) for index in range(channels))
    assert 0 < peak < 32767, "Silent or clipped audio"
    assert peak <= 32768 * 0.30, "Unexpected interface audio gain"
    if loop:
        assert channels == 2 and rate == 44100
        assert seam <= 32, "Discontinuous PCM loop boundary"
    return {"channels": channels, "rate": rate, "frames": frames, "seconds": frames/rate,
            "peak_dbfs": round(20*math.log10(peak/32768), 3),
            "rms_dbfs": round(20*math.log10(rms/32768), 3),
            "clipped_samples": sum(abs(value) >= 32767 for value in values),
            "boundary_delta_pcm": seam, "loop_boundary_checked": loop}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    _, sounds = interface_assets()
    music = music_track()
    if set(sounds) != {"move", "confirm", "back"} or music is None:
        parser.error("The local exported interface pack is required.")
    result = {"sounds": {name: measure(path) for name, path in sounds.items()},
              "music": measure(music, loop=True), "successful": True,
              "scope": "PCM levels, integrity and seam; human listening is not claimed."}
    with args.report.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
