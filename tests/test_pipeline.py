import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
from scipy.io import wavfile

from rf4_notifier.app import App
from rf4_notifier.detector import Detector, SAMPLE_RATE


class FakeCapture:
    audio = np.empty(0, dtype=np.float32)

    def __init__(self, device, output):
        self.output = output
        self.dropped = 0
        self.thread = Mock()
        self.thread.is_alive.return_value = False

    def start(self):
        for offset in range(0, len(self.audio), SAMPLE_RATE // 4):
            self.output.put(("audio", self.audio[offset:offset + SAMPLE_RATE // 4], SAMPLE_RATE))
        self.output.put(("ended", None, 0))

    def stop(self):
        pass


class PipelineTests(unittest.TestCase):
    def test_stream_detection_queues_one_notification_and_dry_run_queues_none(self):
        t = np.arange(SAMPLE_RATE) / SAMPLE_RATE
        sound = (np.sin(2 * np.pi * (600 * t + 900 * t ** 2)) * np.sin(np.pi * t) ** 2 * 0.3).astype(np.float32)
        FakeCapture.audio = np.concatenate((np.zeros(SAMPLE_RATE // 2), sound, np.zeros(SAMPLE_RATE * 2)))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wavfile.write(root / "positive_test.wav", SAMPLE_RATE, sound)
            detector = Detector(root)
            for dry_run in (False, True):
                with self.subTest(dry_run=dry_run):
                    app = App.__new__(App)
                    app.events = queue.Queue()
                    app.worker_stop = threading.Event()
                    app.network_jobs = queue.Queue()
                    ticks = iter(np.arange(0, 100, 0.3))
                    with patch("rf4_notifier.app.Capture", FakeCapture), patch(
                        "rf4_notifier.app.time.monotonic", side_effect=lambda: float(next(ticks))
                    ):
                        app._monitor_worker({}, {"threshold": 0.78, "cooldown": 30,
                                                 "token": "not-a-real-token", "chat_id": "123"},
                                            detector, dry_run)
                    self.assertEqual(app.network_jobs.qsize(), 0 if dry_run else 1)
                    events = list(app.events.queue)
                    self.assertTrue(any(kind == "finished" for kind, _ in events))
                    self.assertTrue(any(kind == "log" and "Похоже на поклёвку" in text
                                        for kind, text in events))


if __name__ == "__main__":
    unittest.main()
