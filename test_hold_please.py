import os, struct, tempfile, unittest, wave
import hold_please

class HoldPleaseTests(unittest.TestCase):
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

if __name__ == "__main__": unittest.main()
