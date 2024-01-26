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

def frequency(note, transpose=0):
    if note == "R": return 0.0
    m = re.fullmatch(r"([A-G])([#b]?)([2-7])", note)
    base = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}[m.group(1)]
    accidental = {'': 0, '#': 1, 'b': -1}[m.group(2)]
    midi = 12 * (int(m.group(3)) + 1) + base + accidental
    return 440.0 * 2 ** ((midi - 69 + transpose) / 12)

def swing_sequence(sequence, swing):
    if not 0 <= swing <= .75: raise ValueError("swing must be between 0 and 0.75")
    adjusted = list(sequence)
    for i in range(0, len(sequence) - 1, 2):
        first, second = sequence[i][1], sequence[i + 1][1]
        transfer = min(first, second) * swing
        adjusted[i] = (sequence[i][0], first + transfer)
        adjusted[i + 1] = (sequence[i + 1][0], second - transfer)
    return adjusted

def repeat_sequence(sequence, repeat):
    if not isinstance(repeat, int) or isinstance(repeat, bool) or not 1 <= repeat <= 16: raise ValueError("repeat must be an integer from 1 to 16")
    expanded = list(sequence) * repeat
    if sum(duration for _, duration in expanded) > MAX_BEATS: raise ValueError("repeated sequence exceeds 120 beats")
    return expanded

def preflight(sequence, tempo, harmony=None, stereo=False, swing=None, fade_in=0.0, fade_out=0.0, transpose=0, gain=1.0):
    if not math.isfinite(tempo) or not 40 <= tempo <= 240: raise ValueError("tempo must be between 40 and 240 BPM")
    if harmony is not None and (not isinstance(harmony, int) or isinstance(harmony, bool) or not -12 <= harmony <= 12): raise ValueError("harmony must be an integer from -12 to 12")
    if stereo and harmony is None: raise ValueError("stereo output requires --harmony")
    if not isinstance(transpose, int) or isinstance(transpose, bool) or not -24 <= transpose <= 24: raise ValueError("transpose must be an integer from -24 to 24")
    if not math.isfinite(gain) or not 0 <= gain <= 1: raise ValueError("gain must be finite and between 0 and 1")
    if not all(math.isfinite(x) and x >= 0 for x in (fade_in, fade_out)): raise ValueError("fade durations must be finite and nonnegative")
    for note, _ in sequence:
        if note != "R" and frequency(note, transpose) >= RATE / 2: raise ValueError("transposed note reaches the Nyquist limit")
        if note != "R" and harmony is not None and frequency(note, transpose + harmony) >= RATE / 2: raise ValueError("transposed harmony reaches the Nyquist limit")
    beat = 60.0 / tempo; source = [round(d * beat * RATE) for _, d in sequence]; adjusted = swing_sequence(sequence, swing) if swing is not None and swing != 0 else sequence; frames = [round(d * beat * RATE) for _, d in adjusted]
    if swing is not None and swing != 0:
        for i in range(0, len(frames) - 1, 2): frames[i + 1] = source[i] + source[i + 1] - frames[i]
    if any(n < 1 for n in frames): raise ValueError("each duration must produce at least one audio frame")
    total = sum(frames); duration = total / RATE
    if fade_in > duration or fade_out > duration: raise ValueError("fade duration cannot exceed audio duration")
    channels = 2 if stereo else 1
    if total * 2 * channels + 44 > MAX_BYTES: raise ValueError("output exceeds 10 MB limit")
    peak = max((max(frequency(note, transpose), frequency(note, transpose + harmony)) if harmony is not None else frequency(note, transpose) for note, _ in sequence if note != "R"), default=0.0)
    return frames, total, channels, peak

def samples(sequence, tempo, harmony=None, stereo=False, swing=None, fade_in=0.0, fade_out=0.0, transpose=0, gain=1.0):
    frame_counts, total_frames, channels, _ = preflight(sequence, tempo, harmony, stereo, swing, fade_in, fade_out, transpose, gain)
    out = bytearray()
    absolute = 0
    fade_in_frames = round(fade_in * RATE); fade_out_frames = round(fade_out * RATE)
    for (note, beats), n in zip(sequence, frame_counts):
        f = frequency(note, transpose); attack = min(round(.01 * RATE), n // 2); release = attack
        for i in range(n):
            if f == 0: left = right = 0.0
            else:
                env = min(1.0, i / max(1, attack), (n - i) / max(1, release))
                primary = math.sin(2 * math.pi * f * i / RATE)
                if stereo:
                    left = right = 0.22 * env * primary
                    right = 0.22 * env * math.sin(2 * math.pi * f * 2 ** (harmony / 12) * i / RATE)
                elif harmony is None or harmony == 0: left = 0.22 * env * primary; right = 0.0
                else: left = 0.11 * env * (primary + math.sin(2 * math.pi * f * 2 ** (harmony / 12) * i / RATE)); right = 0.0
            gain_in = 1.0 if fade_in_frames == 0 else min(1.0, absolute / max(1, fade_in_frames))
            gain_out = 1.0 if fade_out_frames == 0 else min(1.0, (total_frames - 1 - absolute) / max(1, fade_out_frames))
            envelope = min(gain_in, gain_out); left *= envelope * gain; right *= envelope * gain
            out.extend(struct.pack("<h", round(left * 32767)))
            if stereo: out.extend(struct.pack("<h", round(right * 32767)))
            absolute += 1
    return bytes(out)

def write_wav(path, data, force=False, channels=1):
    if len(data) + 44 > MAX_BYTES: raise ValueError("output exceeds 10 MB limit")
    if not force:
        try: handle = open(path, "xb")
        except FileExistsError: raise FileExistsError(f"refusing to overwrite {path}; use --force")
    else: handle = open(path, "wb")
    with handle, wave.open(handle, "wb") as wav:
        wav.setnchannels(channels); wav.setsampwidth(2); wav.setframerate(RATE); wav.writeframes(data)

def main(argv=None):
    p = argparse.ArgumentParser(description="Generate gentle music for a meeting hold.")
    p.add_argument("sequence", nargs="?", default=None, help="tokens such as C4:1 R:0.5 E4:2")
    p.add_argument("--sequence-file", help="read note/rest tokens as strict UTF-8 from a file (max 64 KiB)")
    p.add_argument("-o", "--output", default="hold-please.wav"); p.add_argument("--tempo", type=float, default=96); p.add_argument("--force", action="store_true")
    p.add_argument("--harmony", type=int, default=None, help="mix a second voice -12..12 semitones above/below the melody")
    p.add_argument("--stereo", action="store_true", help="put melody left and harmony right (requires --harmony)")
    p.add_argument("--swing", type=float, default=None, help="redistribute consecutive pair durations by 0..0.75")
    p.add_argument("--fade-in", type=float, default=0.0); p.add_argument("--fade-out", type=float, default=0.0)
    p.add_argument("--transpose", type=int, default=0)
    p.add_argument("--repeat", type=int, default=1, help="repeat the score 1..16 times")
    p.add_argument("--gain", type=float, default=1.0, help="scale all channels from 0 to 1"); p.add_argument("--inspect", action="store_true", help="print WAV metadata without rendering or writing")
    a = p.parse_args(argv)
    try:
        if a.sequence_file and a.sequence is not None: raise ValueError("sequence and --sequence-file are mutually exclusive")
        sequence_text = a.sequence if a.sequence is not None else PRESET
        if a.sequence_file:
            with open(a.sequence_file, "rb") as source:
                raw = source.read(65537)
            if len(raw) > 65536: raise ValueError("sequence file exceeds 64 KiB")
            try: sequence_text = raw.decode("utf-8")
            except UnicodeDecodeError as error: raise ValueError("sequence file is not valid UTF-8") from error
        if a.harmony is not None and not -12 <= a.harmony <= 12: raise ValueError("harmony must be an integer from -12 to 12")
        if a.swing is not None and (not math.isfinite(a.swing) or not 0 <= a.swing <= .75): raise ValueError("swing must be between 0 and 0.75")
        score = repeat_sequence(parse_sequence(sequence_text), a.repeat)
        if a.inspect:
            _, frames, channels, peak = preflight(score, a.tempo, a.harmony, a.stereo, a.swing, a.fade_in, a.fade_out, a.transpose, a.gain)
            print(f"duration_seconds={frames / RATE:.6f}\nframes={frames}\nchannels={channels}\nestimated_wav_bytes={frames * channels * 2 + 44}\npeak_frequency_hz={peak:.6f}")
            return
        write_wav(a.output, samples(score, a.tempo, a.harmony, a.stereo, a.swing, a.fade_in, a.fade_out, a.transpose, a.gain), a.force, 2 if a.stereo else 1)
    except (ValueError, FileExistsError, OSError) as e: p.error(str(e))
    print(f"wrote {a.output}")

if __name__ == "__main__": main()
