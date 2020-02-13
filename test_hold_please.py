import os, struct, tempfile, unittest, wave
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

if __name__ == "__main__": unittest.main()
