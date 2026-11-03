import queue
import threading

import numpy as np
import pyaudiowpatch as pyaudio


def list_devices() -> list[dict]:
    with pyaudio.PyAudio() as audio:
        default_index = None
        try:
            default_index = audio.get_default_wasapi_loopback()["index"]
        except OSError:
            pass
        result = []
        for item in audio.get_loopback_device_info_generator():
            device = dict(item)
            device["default"] = device["index"] == default_index
            result.append(device)
        return sorted(result, key=lambda device: not device["default"])


class Capture:
    def __init__(self, device: dict, output: queue.Queue):
        self.device = device
        self.output = output
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.dropped = 0

    def start(self):
        self.thread = threading.Thread(target=self._run, name="wasapi-capture", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self):
        try:
            rate = int(self.device["defaultSampleRate"])
            channels = int(self.device["maxInputChannels"])
            if channels < 1:
                raise RuntimeError("Устройство не поддерживает захват звука.")
            with pyaudio.PyAudio() as audio:
                with audio.open(format=pyaudio.paFloat32, channels=channels, rate=rate,
                                input=True, input_device_index=int(self.device["index"]),
                                frames_per_buffer=2048) as stream:
                    while not self.stop_event.is_set():
                        raw = stream.read(2048, exception_on_overflow=False)
                        block = np.frombuffer(raw, dtype=np.float32).reshape(-1, channels).mean(axis=1)
                        try:
                            self.output.put_nowait(("audio", block.copy(), rate))
                        except queue.Full:
                            self.dropped += 1
        except Exception as exc:
            # Never block shutdown on a full queue.
            try:
                self.output.put(("error", str(exc), 0), timeout=0.5)
            except queue.Full:
                pass
        finally:
            try:
                self.output.put(("ended", None, 0), timeout=0.5)
            except queue.Full:
                pass
