import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

from rf4_notifier.detector import (
    Detector, SAMPLE_RATE, TriggerGate, features, mono_resample, read_wav,
    similarity, trim_recording,
)


def example_sound():
    t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
    return (signal.chirp(t, 450, 1, 2800) * np.sin(np.pi * t) ** 2 * 0.3).astype(np.float32)


class DetectorTests(unittest.TestCase):
    def test_embedded_sample_with_noise_and_volume_change(self):
        rng = np.random.default_rng(12)
        sound = example_sound()
        window = rng.normal(0, 0.002, SAMPLE_RATE * 3).astype(np.float32)
        window[6500:6500 + len(sound)] += sound * 0.35
        score = similarity(features(sound), features(window))
        self.assertGreater(score, 0.8)

    def test_unrelated_noise_does_not_match(self):
        noise = np.random.default_rng(5).normal(0, 0.1, SAMPLE_RATE * 3).astype(np.float32)
        self.assertLess(similarity(features(example_sound()), features(noise)), 0.55)

    def test_silence_and_short_input(self):
        target = features(example_sound())
        self.assertEqual(similarity(target, features(np.zeros(SAMPLE_RATE * 2))), 0)
        self.assertEqual(similarity(target, features(np.zeros(50))), 0)

    def test_speed_tolerance(self):
        sound = example_sound()
        slower = signal.resample(sound, round(len(sound) * 1.06))
        window = np.concatenate((np.zeros(3000), slower, np.zeros(3000)))
        self.assertGreater(similarity(features(sound), features(window)), 0.75)

    def test_trim_rejects_silence(self):
        with self.assertRaises(ValueError):
            trim_recording(np.zeros(SAMPLE_RATE))

    def test_trim_rejects_tiny_input(self):
        with self.assertRaises(ValueError):
            trim_recording(np.ones(10, dtype=np.float32))

    def test_trim_removes_padding(self):
        audio = np.concatenate((np.zeros(SAMPLE_RATE), example_sound(), np.zeros(SAMPLE_RATE)))
        trimmed = trim_recording(audio)
        self.assertLess(len(trimmed), SAMPLE_RATE * 1.5)
        self.assertGreater(len(trimmed), SAMPLE_RATE * 0.5)

    def test_resample_stereo(self):
        audio = np.ones((48000, 2), dtype=np.float32) * 0.2
        result = mono_resample(audio, 48000)
        self.assertEqual(len(result), SAMPLE_RATE)
        self.assertAlmostEqual(float(np.mean(result)), 0.2, places=3)

    def test_wav_loading_and_template_kinds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sound = example_sound()
            wavfile.write(root / "positive_test.wav", SAMPLE_RATE, (sound * 32767).astype(np.int16))
            wavfile.write(root / "negative_noise.wav", SAMPLE_RATE,
                          np.random.default_rng(2).normal(0, 0.01, SAMPLE_RATE).astype(np.float32))
            wavfile.write(root / "positive_bad.wav", SAMPLE_RATE, np.zeros(10, dtype=np.float32))
            decoded = read_wav(root / "positive_test.wav")
            np.testing.assert_allclose(sound, decoded, atol=0.0001)
            detector = Detector(root)
            self.assertEqual(detector.positives, 1)
            self.assertEqual(len(detector.errors), 1)
            positive, negative, _ = detector.score(np.concatenate((np.zeros(2000), sound, np.zeros(3000))))
            self.assertGreater(positive, 0.9)
            self.assertGreater(positive, negative + 0.06)


class TriggerTests(unittest.TestCase):
    def test_single_notification_and_rearm(self):
        gate = TriggerGate(0.78, 5)
        self.assertTrue(gate.update(0.9, 0.1, 0))
        self.assertFalse(gate.update(0.9, 0.1, 1))
        self.assertFalse(gate.update(0.9, 0.1, 7))
        self.assertFalse(gate.update(0.2, 0.1, 8))
        self.assertFalse(gate.update(0.2, 0.1, 9.1))
        self.assertTrue(gate.update(0.9, 0.1, 9.4))

    def test_negative_example_blocks_notification(self):
        gate = TriggerGate(0.78, 5)
        self.assertFalse(gate.update(0.9, 0.88, 0))
        self.assertTrue(gate.update(0.9, 0.2, 1))


if __name__ == "__main__":
    unittest.main()
