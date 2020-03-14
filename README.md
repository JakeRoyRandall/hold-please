# Hold Please: music for the meeting that could have been an email

This small Python 3 standard-library tool turns a bounded note/rest sequence into a playable 16-bit mono WAV. Notes use tokens such as `C4:1 R:0.5 E4:2`, where the number is beats; tempo defaults to 96 BPM. The preset is a short original hold melody with a gentle fixed amplitude and 10 ms attack/release to reduce clicks.

Created September 2026 retrospectively for the calendar garden; it is not historical 2020 work. The calendar author is disclosed as the author of this retrospective exercise, not as a historical attribution.

```sh
cd app
python3 hold_please.py --output ../evidence/hold-please.wav
python3 hold_please.py 'C4:1 R:0.5 G4:1' --tempo 110 --output ../evidence/custom.wav
python3 hold_please.py 'C4:1 R:0.5 G4:1' --harmony 7 --output ../evidence/harmony.wav
python3 hold_please.py 'C4:1 R:0.5 G4:1' --harmony 7 --stereo --output ../evidence/stereo.wav
python3 -m unittest -v test_hold_please.py
```

The generator accepts notes C–B with optional sharps/flats and octaves 2–7, rests, positive finite beat lengths, and tempos from 40–240 BPM. It caps sequences at 120 beats and output at 10 MB, and refuses to overwrite an existing file unless `--force` is supplied. It does not synthesize speech or promise studio quality.

`--harmony N` mixes a second voice at a bounded integer offset from -12 to 12 semitones. It preserves rests and uses balanced gains so the output remains within 16-bit PCM limits; without the flag, the original mono output is unchanged.

`--stereo` requires `--harmony` and writes true two-channel PCM: melody on the left and the harmony on the right. Stereo byte size is included in the same 10 MB preflight bound.

`--swing S` redistributes each consecutive pair by moving up to `S` times the shorter duration from the second item to the first (`0..0.75`). Pair totals and total audio frames remain constant, rests participate like notes, and an odd final item is unchanged. The default without `--swing` produces the original bytes.

`--fade-in SECONDS` and `--fade-out SECONDS` apply smooth global ramps to the rendered PCM, including both stereo channels. Values are finite, nonnegative, and cannot exceed the generated duration; overlapping ramps use the lower gain. Frame count and the default no-fade bytes are unchanged.

`--transpose N` shifts both melody and harmony by an integer number of semitones from `-24` to `24`; rests remain silent. The default `0` leaves the original bytes unchanged.

Use `--sequence-file PATH` instead of the positional sequence to read whitespace-separated note/rest tokens across multiple lines. Blank lines and whole-line `#` comments are ignored (inline comments remain invalid). Files must be valid UTF‑8 and no larger than 64 KiB; the option cannot be combined with a positional sequence. Invalid, oversized, missing, or undecodable files fail before output creation.

`--repeat N` expands the parsed score `N` times (`1..16`) before swing, fades, harmony, and rendering. The expanded score must still fit the 120-beat and 10 MB limits; `N=1` is the default byte-identical behavior.

`--reverse` reverses the parsed note/rest events before `--repeat`, preserving each event's pitch and duration. It changes event order only; it does not reverse the generated waveform. Inspect metadata uses the same reversed and repeated plan.

`--gain G` scales every output channel from `0` to `1` before 16-bit quantization. The default `1.0` preserves existing bytes; `0` is silent and all values are finite and bounded.

`--normalize` optionally peak-normalizes rendered PCM after gain and fades. Non-silent output is scaled to its greatest available 16-bit magnitude without clipping; silence remains silent. Without this flag, output remains byte-identical.

`--inspect` prints duration, frame count, channel count, estimated WAV bytes, and peak frequency using the same repeat/swing timing plan, then exits without allocating PCM or writing the requested output.

`--inspect-json` emits the equivalent metadata as JSON with `sample_rate`, `duration_seconds`, `frames`, `channels`, `bytes`, and `peak_frequency_hz` keys. It performs no rendering or file write and cannot be combined with `--inspect`.

`--sample-rate` accepts `22050`, `44100`, or `48000` Hz; the default `44100` preserves existing output. Frame planning, WAV headers, fade timing, and Nyquist validation all use the selected rate.

`--stdout` writes a binary WAV stream to stdout for piping; its success message goes to stderr. It cannot be combined with `-o/--output` or `--force`. Without `--stdout`, the default output file remains `hold-please.wav`.
