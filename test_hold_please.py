import json, os, struct, subprocess, sys, tempfile, unittest, wave
import hold_please

class HoldPleaseTests(unittest.TestCase):
    def test_swing_conserves_pair_frames_rests_and_odd_last(self):
        seq = hold_please.parse_sequence("C4:1 R:0.5 G4:0.25 R:0.75 E4:0.1")
        swung = hold_please.swing_sequence(seq, .75)
        self.assertAlmostEqual(sum(x[1] for x in seq), sum(x[1] for x in swung))
        beat = 60 / 120 * hold_please.RATE
        original = [round(x[1] * beat) for x in seq]; data = hold_please.samples(seq, 120, swing=.75)
        self.assertEqual(len(data)//2, sum(original)); self.assertEqual(swung[-1], seq[-1])
        rest_start = round((swung[0][1]) * beat); rest_end = rest_start + round(swung[1][1] * beat)
        vals = struct.unpack("<%dh" % (len(data)//2), data); self.assertEqual(max(map(abs, vals[rest_start:rest_end])), 0)
        self.assertEqual(hold_please.samples(seq, 120), hold_please.samples(seq, 120, swing=0))

    def test_harmony_changes_pcm_and_stays_bounded(self):
        seq = hold_please.parse_sequence("C4:0.2 R:0.1 G4:0.2")
        plain = hold_please.samples(seq, 120); harmony = hold_please.samples(seq, 120, 7)
        self.assertNotEqual(plain, harmony)
        vals = struct.unpack("<%dh" % (len(harmony)//2), harmony)
        self.assertLessEqual(max(map(abs, vals)), 32767)
        rest_start = round(0.2 * 60 / 120 * hold_please.RATE)
        rest_end = rest_start + round(0.1 * 60 / 120 * hold_please.RATE)
        self.assertEqual(max(map(abs, vals[rest_start:rest_end])), 0)

    def test_stereo_interleaving_and_requirement(self):
        seq = hold_please.parse_sequence("C4:0.2 R:0.1 G4:0.2")
        data = hold_please.samples(seq, 120, 7, True)
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            hold_please.write_wav(f.name, data, True, 2)
            with wave.open(f.name, "rb") as w:
                self.assertEqual((w.getnchannels(), w.getnframes()), (2, len(data)//4))
                vals = struct.unpack("<%dh" % (len(data)//2), w.readframes(w.getnframes()))
                self.assertNotEqual(vals[0::2], vals[1::2]); rest = round(0.2 * 60 / 120 * hold_please.RATE)
                self.assertEqual(max(map(abs, vals[2*rest:2*(rest + round(0.1 * 60 / 120 * hold_please.RATE))])), 0)
        self.assertRaises(ValueError, hold_please.samples, seq, 120, None, True)

    def test_wav_properties_peak_and_rest(self):
        data = hold_please.samples(hold_please.parse_sequence("C4:0.1 R:0.1"), 120)
        with tempfile.NamedTemporaryFile(suffix=".wav") as f:
            hold_please.write_wav(f.name, data, True)
            with wave.open(f.name, "rb") as w:
                self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()), (44100, 1, 2)); self.assertEqual(w.getnframes(), len(data)//2)
                raw = w.readframes(w.getnframes()); vals = struct.unpack("<%dh" % (len(raw)//2), raw)
                self.assertGreater(max(map(abs, vals)), 1000); rest_start = len(vals)//2; self.assertEqual(max(map(abs, vals[rest_start:])), 0)
    def test_rejected_notes_tempo_and_long_input(self):
        for bad in ("H4:1", "C8:1", "C4:0", "C4:nan"): self.assertRaises(ValueError, hold_please.parse_sequence, bad)
        self.assertRaises(ValueError, hold_please.parse_sequence, "C4:121"); self.assertRaises(SystemExit, hold_please.main, ["C4:1", "--tempo", "300"])
        self.assertRaises(ValueError, hold_please.samples, [("C4", 1)], 120, 13)
    def test_enharmonics_and_preflight(self):
        self.assertEqual(hold_please.frequency("B#4"), hold_please.frequency("C5"))
        self.assertEqual(hold_please.frequency("Cb4"), hold_please.frequency("B3"))
        self.assertEqual(hold_please.frequency("E#4"), hold_please.frequency("F4"))
        with self.assertRaises(ValueError): hold_please.samples([("C4",120)],40)
        with self.assertRaises(ValueError): hold_please.samples([("C4",0.000000001)],120)
        with self.assertRaises(ValueError): hold_please.samples([("C4",1)],0)
    def test_overwrite_refused(self):
        with tempfile.NamedTemporaryFile() as f: self.assertRaises(FileExistsError, hold_please.write_wav, f.name, b"", False)
    def test_swing_validation_and_cli_outputs(self):
        for value in (-0.01, .76, float("nan"), float("inf")): self.assertRaises(ValueError, hold_please.samples, hold_please.parse_sequence("C4:1 D4:1"), 120, swing=value)
        with tempfile.TemporaryDirectory() as d:
            mono = os.path.join(d, "mono.wav"); stereo = os.path.join(d, "stereo.wav")
            self.assertRaises(SystemExit, hold_please.main, ["C4:1", "--swing", ".8", "-o", mono])
            hold_please.main(["C4:1 D4:1", "--swing", ".5", "-o", mono])
            hold_please.main(["C4:1 D4:1", "--swing", ".5", "--harmony", "7", "--stereo", "-o", stereo])
            with wave.open(stereo, "rb") as w: self.assertEqual(w.getnchannels(), 2)
    def test_fades_ramp_pcm_and_validate(self):
        seq = hold_please.parse_sequence("C4:0.2 D4:0.2")
        data = hold_please.samples(seq, 120, fade_in=.05, fade_out=.05)
        vals = struct.unpack("<%dh" % (len(data)//2), data)
        self.assertEqual(vals[0], 0); self.assertEqual(vals[-1], 0); self.assertGreater(max(map(abs, vals[1000:3000])), abs(vals[100]))
        stereo = hold_please.samples(seq, 120, 7, True, None, .05, .05); pairs = struct.unpack("<%dh" % (len(stereo)//2), stereo)
        self.assertEqual(pairs[0], pairs[1]); self.assertLessEqual(max(map(abs, pairs)), 32767)
        self.assertRaises(ValueError, hold_please.samples, seq, 120, fade_in=float("nan")); self.assertRaises(ValueError, hold_please.samples, seq, 120, fade_out=1.0)
    def test_transpose_changes_frequency_and_cli_validates(self):
        self.assertAlmostEqual(hold_please.frequency("A4", 12), 880.0, places=5)
        seq = hold_please.parse_sequence("A4:0.2 R:0.1")
        self.assertNotEqual(hold_please.samples(seq, 120), hold_please.samples(seq, 120, transpose=12))
        self.assertEqual(hold_please.samples([("R", .2)], 120), hold_please.samples([("R", .2)], 120, transpose=-24))
        self.assertRaises(ValueError, hold_please.samples, seq, 120, transpose=25)
        self.assertRaises(SystemExit, hold_please.main, ["A4:1", "--transpose", "25", "-o", "/tmp/transpose.wav"])
    def test_transpose_nyquist_guard_and_valid_edge(self):
        with self.assertRaises(ValueError): hold_please.samples(hold_please.parse_sequence("B7:1"), 120, harmony=12, transpose=24)
        data = hold_please.samples(hold_please.parse_sequence("A6:0.1"), 120, harmony=12, transpose=24)
        self.assertGreater(len(data), 0)
    def test_sequence_file_utf8_bounds_and_conflicts(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "notes.txt")
            with open(path, "w", encoding="utf-8") as f: f.write("C4:0.1\nR:0.1\nD4:0.1")
            out = os.path.join(d, "file.wav"); hold_please.main(["--sequence-file", path, "-o", out]); self.assertTrue(os.path.getsize(out) > 44)
            with open(path, "wb") as f: f.write(b"C4:1\n\xff")
            self.assertRaises(SystemExit, hold_please.main, ["--sequence-file", path, "-o", os.path.join(d, "bad.wav")])
            with open(path, "wb") as f: f.write(b"C4:1" * 20000)
            self.assertRaises(SystemExit, hold_please.main, ["--sequence-file", path, "-o", os.path.join(d, "big.wav")])
            self.assertRaises(SystemExit, hold_please.main, ["C4:1", "--sequence-file", path, "-o", os.path.join(d, "conflict.wav")])
            self.assertRaises(SystemExit, hold_please.main, [hold_please.PRESET, "--sequence-file", path, "-o", os.path.join(d, "preset-conflict.wav")])
            self.assertRaises(SystemExit, hold_please.main, ["--sequence-file", os.path.join(d, "missing"), "-o", os.path.join(d, "missing.wav")])
    def test_sequence_file_ignores_blank_and_whole_line_comments(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "commented.txt"); out = os.path.join(d, "commented.wav")
            with open(path, "w", encoding="utf-8", newline="") as f: f.write("# Café planning\r\n\r\n C4:0.1\r\n# another note\nR:0.1\n")
            hold_please.main(["--sequence-file", path, "-o", out]); self.assertTrue(os.path.exists(out))
            with open(path, "w", encoding="utf-8") as f: f.write("# comments only\n\n")
            self.assertRaises(SystemExit, hold_please.main, ["--sequence-file", path, "-o", os.path.join(d, "empty.wav")])
            self.assertRaises(ValueError, hold_please.parse_sequence, "C4:0.1 # inline remains strict")
    def test_repeat_expands_frames_and_preserves_rests(self):
        seq = hold_please.parse_sequence("C4:0.1 R:0.1")
        self.assertEqual(len(hold_please.repeat_sequence(seq, 3)), 6)
        self.assertEqual(len(hold_please.samples(hold_please.repeat_sequence(seq, 3), 120)), 3 * len(hold_please.samples(seq, 120)))
        self.assertRaises(ValueError, hold_please.repeat_sequence, seq, 0)
        self.assertRaises(ValueError, hold_please.repeat_sequence, hold_please.parse_sequence("C4:120"), 2)
        self.assertRaises(SystemExit, hold_please.main, ["C4:1", "--repeat", "17", "-o", "/tmp/repeat.wav"])
    def test_gain_scales_mono_stereo_and_validates(self):
        seq = hold_please.parse_sequence("C4:0.2")
        full = hold_please.samples(seq, 120); half = hold_please.samples(seq, 120, gain=.5)
        full_vals = struct.unpack("<%dh" % (len(full)//2), full); half_vals = struct.unpack("<%dh" % (len(half)//2), half)
        self.assertGreater(max(map(abs, full_vals)), max(map(abs, half_vals))); self.assertEqual(hold_please.samples(seq, 120, gain=0), b"\0" * len(full))
        stereo = hold_please.samples(seq, 120, harmony=7, stereo=True, gain=.5); self.assertGreater(max(map(abs, struct.unpack("<%dh" % (len(stereo)//2), stereo))), 0)
        for bad in (-.01, 1.01, float("nan"), float("inf")): self.assertRaises(ValueError, hold_please.samples, seq, 120, gain=bad)
    def test_normalize_reaches_peak_and_preserves_silence(self):
        seq = hold_please.parse_sequence("C4:0.2 R:0.1")
        raw = hold_please.samples(seq, 120, gain=.2); normalized = hold_please.samples(seq, 120, gain=.2, normalize=True)
        raw_values = struct.unpack("<%dh" % (len(raw)//2), raw); normalized_values = struct.unpack("<%dh" % (len(normalized)//2), normalized)
        self.assertLess(max(map(abs, raw_values)), 32767); self.assertEqual(max(map(abs, normalized_values)), 32767)
        silence = hold_please.samples(hold_please.parse_sequence("R:1"), 120, normalize=True)
        self.assertEqual(silence, b"\0" * (hold_please.RATE // 2 * 2))
        self.assertEqual(hold_please.samples(seq, 120), hold_please.samples(seq, 120, normalize=False))
    def test_normalize_preserves_stereo_shape_at_selected_rate(self):
        data = hold_please.samples(hold_please.parse_sequence("C4:0.2"), 120, harmony=7, stereo=True, gain=.2, rate=22050, normalize=True)
        values = struct.unpack("<%dh" % (len(data)//2), data)
        self.assertEqual(len(values) % 2, 0); self.assertEqual(max(map(abs, values)), 32767)
        self.assertGreater(max(map(abs, values[0::2])), 0); self.assertGreater(max(map(abs, values[1::2])), 0)
    def test_inspect_matches_wav_without_creating_output(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "inspect.wav"); score = hold_please.repeat_sequence(hold_please.parse_sequence("C4:0.2 R:0.1"), 2)
            _, frames, channels, _ = hold_please.preflight(score, 120, harmony=7, stereo=True, swing=.25)
            hold_please.main(["C4:0.2 R:0.1", "--repeat", "2", "--tempo", "120", "--swing", ".25", "--harmony", "7", "--stereo", "-o", path])
            with wave.open(path, "rb") as w: self.assertEqual((w.getnframes(), w.getnchannels()), (frames, channels))
            inspect_path = os.path.join(d, "no-write.wav"); self.assertFalse(os.path.exists(inspect_path)); hold_please.main(["C4:0.2 R:0.1", "--inspect", "-o", inspect_path]); self.assertFalse(os.path.exists(inspect_path))
            self.assertRaises(SystemExit, hold_please.main, ["C4:1", "--inspect", "--stereo"])
            self.assertRaises(SystemExit, hold_please.main, ["C4:1", "--inspect", "--transpose", "25"])
            self.assertRaises(SystemExit, hold_please.main, ["C4:1", "--inspect", "--gain", "nan"])
            self.assertRaises(SystemExit, hold_please.main, ["C4:1", "--inspect", "--fade-in", "2"])
            _, _, _, peak = hold_please.preflight(hold_please.parse_sequence("A4:1"), 120, harmony=-12)
            self.assertAlmostEqual(peak, hold_please.frequency("A4"), places=5)
    def test_inspect_json_is_pipeable_and_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            output_path = os.path.join(d, "metadata.wav")
            result = subprocess.run([sys.executable, "hold_please.py", "A4:0.2", "--inspect-json", "--sample-rate", "22050", "-o", output_path], capture_output=True, text=True, check=True)
            metadata = json.loads(result.stdout)
            self.assertEqual(set(metadata), {"sample_rate", "duration_seconds", "frames", "channels", "bytes", "peak_frequency_hz"})
            self.assertEqual((metadata["sample_rate"], metadata["channels"]), (22050, 1)); self.assertFalse(os.path.exists(output_path)); self.assertEqual(metadata["bytes"], metadata["frames"] * 2 + 44)
            conflict = subprocess.run([sys.executable, "hold_please.py", "A4:0.2", "--inspect", "--inspect-json"], capture_output=True, text=True)
            self.assertNotEqual(conflict.returncode, 0); self.assertIn("mutually exclusive", conflict.stderr)
    def test_sample_rates_headers_frames_and_nyquist(self):
        seq = hold_please.parse_sequence("C4:0.2")
        for rate in (22050, 44100, 48000):
            data = hold_please.samples(seq, 120, rate=rate)
            with tempfile.NamedTemporaryFile(suffix=".wav") as f:
                hold_please.write_wav(f.name, data, True, 1, rate)
                with wave.open(f.name, "rb") as w: self.assertEqual((w.getframerate(), w.getnframes()), (rate, len(data)//2))
        self.assertRaises(ValueError, hold_please.samples, hold_please.parse_sequence("B7:1"), 120, transpose=24, harmony=12, rate=22050)
    def test_sample_rate_pitch_tracks_selected_clock(self):
        for rate in (22050, 44100, 48000):
            data = hold_please.samples(hold_please.parse_sequence("A4:1"), 120, rate=rate)
            vals = struct.unpack("<%dh" % (len(data)//2), data); crossings = sum(a < 0 <= b for a,b in zip(vals, vals[1:]))
            self.assertAlmostEqual(crossings / (len(vals) / rate), 440, delta=8)
        self.assertRaises(ValueError, hold_please.samples, hold_please.parse_sequence("A4:1"), 120, rate=12345)

if __name__ == "__main__": unittest.main()
