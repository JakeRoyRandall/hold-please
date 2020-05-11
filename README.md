# Hold Please: music for the meeting that could have been an email

This small Python 3 standard-library tool turns a bounded note/rest sequence into a playable 16-bit mono WAV. Notes use tokens such as `C4:1 R:0.5 E4:2`, where the number is beats; tempo defaults to 96 BPM. The preset is a short original hold melody with a gentle fixed amplitude and 10 ms attack/release to reduce clicks.

Created September 2026 retrospectively for the calendar garden; it is not historical 2020 work. The calendar author is disclosed as the author of this retrospective exercise, not as a historical attribution.

```sh
python3 hold_please.py --output ../evidence/hold-please.wav
python3 hold_please.py 'C4:1 R:0.5 G4:1' --tempo 110 --output ../evidence/custom.wav
python3 hold_please.py 'C4:1 R:0.5 G4:1' --harmony 7 --output ../evidence/harmony.wav
python3 hold_please.py 'C4:1 R:0.5 G4:1' --harmony 7 --stereo --output ../evidence/stereo.wav
python3 -m unittest -v test_hold_please.py
```

The generator accepts notes C–B with optional sharps/flats and octaves 2–7, rests, positive finite beat lengths, and tempos from 40–240 BPM. It caps sequences at 120 beats and output at 10 MB, and refuses to overwrite an existing file unless `--force` is supplied. It does not synthesize speech, normalize loudness, or promise studio quality.

`--harmony N` mixes a second voice at a bounded integer offset from -12 to 12 semitones. It preserves rests and uses balanced gains so the output remains within 16-bit PCM limits; without the flag, the original mono output is unchanged.

`--stereo` requires `--harmony` and writes true two-channel PCM: melody on the left and the harmony on the right. Stereo byte size is included in the same 10 MB preflight bound.

Standalone tests: `python3 -m unittest -v`. Git author dates are deliberately assigned for contribution-calendar artwork; committer timestamps record actual September2026 creation.
