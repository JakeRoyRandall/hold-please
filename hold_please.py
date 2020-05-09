#!/usr/bin/env python3
"""A tiny, bounded meeting-hold music generator using only the standard library."""
import argparse, math, os, re, struct, wave

RATE = 44100
MAX_BEATS = 120
MAX_BYTES = 10_000_000
PRESET = "C4:1 D4:1 E4:1 R:0.5 E4:1 D4:1 C4:2"
NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)([2-7]):([0-9]+(?:\.[0-9]+)?)$")


def parse_sequence(text):
    if not text.strip(): raise ValueError("sequence is empty")
    result = []
    for token in text.split():
        if token.upper().startswith("R:"):
            name, beats = "R", token[2:]
        else:
            m = NOTE_RE.fullmatch(token)
            if not m: raise ValueError(f"invalid note token: {token}")
            name, beats = m.group(1).upper() + m.group(2) + m.group(3), m.group(4)
        try: duration = float(beats)
        except ValueError: raise ValueError(f"invalid duration: {beats}")
        if not math.isfinite(duration) or duration <= 0: raise ValueError("durations must be finite and positive")
        result.append((name, duration))
    if sum(d for _, d in result) > MAX_BEATS: raise ValueError(f"sequence exceeds {MAX_BEATS} beats")
    return result

def frequency(note):
    if note == "R": return 0.0
    m = re.fullmatch(r"([A-G])([#b]?)([2-7])", note)
    base = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}[m.group(1)]
    accidental = {'': 0, '#': 1, 'b': -1}[m.group(2)]
    midi = 12 * (int(m.group(3)) + 1) + base + accidental
    return 440.0 * 2 ** ((midi - 69) / 12)

def samples(sequence, tempo):
    if not math.isfinite(tempo) or not 40 <= tempo <= 240: raise ValueError("tempo must be between 40 and 240 BPM")
    beat = 60.0 / tempo
    frame_counts = [round(beats * beat * RATE) for _, beats in sequence]
    if any(n < 1 for n in frame_counts): raise ValueError("each duration must produce at least one audio frame")
    if sum(frame_counts) * 2 + 44 > MAX_BYTES: raise ValueError("output exceeds 10 MB limit")
    out = bytearray()
    for (note, beats), n in zip(sequence, frame_counts):
        f = frequency(note); attack = min(round(.01 * RATE), n // 2); release = attack
        for i in range(n):
            if f == 0: value = 0.0
            else:
                env = min(1.0, i / max(1, attack), (n - i) / max(1, release))
                value = 0.22 * env * math.sin(2 * math.pi * f * i / RATE)
            out.extend(struct.pack("<h", round(value * 32767)))
    return bytes(out)

def write_wav(path, data, force=False):
    if len(data) + 44 > MAX_BYTES: raise ValueError("output exceeds 10 MB limit")
    if not force:
        try: handle = open(path, "xb")
        except FileExistsError: raise FileExistsError(f"refusing to overwrite {path}; use --force")
    else: handle = open(path, "wb")
    with handle, wave.open(handle, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(RATE); wav.writeframes(data)

def main(argv=None):
    p = argparse.ArgumentParser(description="Generate gentle music for a meeting hold.")
    p.add_argument("sequence", nargs="?", default=PRESET, help="tokens such as C4:1 R:0.5 E4:2")
    p.add_argument("-o", "--output", default="hold-please.wav"); p.add_argument("--tempo", type=float, default=96); p.add_argument("--force", action="store_true")
    a = p.parse_args(argv)
    try:
        if not math.isfinite(a.tempo) or not 40 <= a.tempo <= 240: raise ValueError("tempo must be between 40 and 240 BPM")
        write_wav(a.output, samples(parse_sequence(a.sequence), a.tempo), a.force)
    except (ValueError, FileExistsError, OSError) as e: p.error(str(e))
    print(f"wrote {a.output}")

if __name__ == "__main__": main()
