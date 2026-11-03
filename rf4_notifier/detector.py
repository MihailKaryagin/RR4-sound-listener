"""Local few-shot sound matching. No pretrained model or game access required."""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

SAMPLE_RATE = 16000
HOP = 160
N_FFT = 512
N_MELS = 40


def mono_resample(audio: np.ndarray, rate: int) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 2:
        audio = audio.mean(axis=1)
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    if rate != SAMPLE_RATE:
        from math import gcd
        divisor = gcd(rate, SAMPLE_RATE)
        audio = signal.resample_poly(audio, SAMPLE_RATE // divisor, rate // divisor)
    return np.asarray(audio, dtype=np.float32)


def read_wav(path: Path) -> np.ndarray:
    rate, audio = wavfile.read(path)
    if np.issubdtype(audio.dtype, np.integer):
        info = np.iinfo(audio.dtype)
        if info.min == 0:
            audio = (audio.astype(np.float32) - 128) / 128
        else:
            audio = audio.astype(np.float32) / max(abs(info.min), info.max)
    return mono_resample(audio, rate)


def _mel_bank() -> np.ndarray:
    hz_to_mel = lambda hz: 2595 * np.log10(1 + hz / 700)
    points = 700 * (10 ** (np.linspace(hz_to_mel(100), hz_to_mel(7600), N_MELS + 2) / 2595) - 1)
    bins = np.linspace(0, SAMPLE_RATE / 2, N_FFT // 2 + 1)
    filters = []
    for left, center, right in zip(points[:-2], points[1:-1], points[2:]):
        triangle = np.maximum(0, np.minimum((bins - left) / (center - left), (right - bins) / (right - center)))
        filters.append(triangle / max(triangle.sum(), 1e-9))
    return np.asarray(filters, dtype=np.float32)


MEL_BANK = _mel_bank()


def features(audio: np.ndarray) -> np.ndarray:
    if len(audio) < N_FFT:
        return np.empty((N_MELS, 0), dtype=np.float32)
    _, _, spectrum = signal.stft(audio, fs=SAMPLE_RATE, nperseg=N_FFT,
                                 noverlap=N_FFT - HOP, boundary=None, padded=False)
    power = MEL_BANK @ (np.abs(spectrum) ** 2)
    db = 10 * np.log10(np.maximum(power, 1e-12))
    # Relative log-mel patterns tolerate volume changes, but retain spectral shape.
    db = np.maximum(db, db.max() - 65)
    return (db - db.mean()).astype(np.float32)


def trim_recording(audio: np.ndarray) -> np.ndarray:
    """Remove quiet leading/trailing regions; refuse silence instead of learning it."""
    if not len(audio) or np.sqrt(np.mean(audio ** 2)) < 0.0001:
        raise ValueError("Запись слишком тихая. Проверь устройство и громкость игры.")
    frame = 320
    count = len(audio) // frame
    if count == 0:
        raise ValueError("Образец короче 0,25 секунды. Запиши звук целиком.")
    rms = np.sqrt(np.mean(audio[:count * frame].reshape(count, frame) ** 2, axis=1))
    active = np.flatnonzero(rms > max(float(rms.max()) * 0.16, 0.0002))
    if not len(active):
        raise ValueError("В записи не найден звук.")
    start = max(0, int(active[0]) * frame - 800)
    end = min(len(audio), (int(active[-1]) + 1) * frame + 1600)
    result = audio[start:end]
    if len(result) < SAMPLE_RATE * 0.25:
        raise ValueError("Образец короче 0,25 секунды. Запиши звук целиком.")
    if len(result) > SAMPLE_RATE * 8:
        raise ValueError("Образец длиннее 8 секунд. Выдели короткий характерный звук.")
    return result


@dataclass
class Template:
    name: str
    kind: str
    matrix: np.ndarray
    samples: int


def similarity(template: np.ndarray, window: np.ndarray) -> float:
    """Maximum normalized spectrogram correlation across time and slight speed changes."""
    best = 0.0
    for speed in (0.94, 1.0, 1.06):
        width = max(4, round(template.shape[1] * speed))
        if window.shape[1] < width:
            continue
        target = template if width == template.shape[1] else signal.resample(template, width, axis=1).real
        target = target - target.mean()
        energy = float(np.sum(target ** 2))
        if energy < 1e-8:
            continue
        # Correlate time only, sum over mel bands. Center each candidate window.
        numerator = signal.fftconvolve(window, target[:, ::-1], axes=1, mode="valid").sum(axis=0)
        column_sum = window.sum(axis=0, dtype=np.float64)
        column_square = (window.astype(np.float64) ** 2).sum(axis=0)
        sums = np.convolve(column_sum, np.ones(width), mode="valid")
        squares = np.convolve(column_square, np.ones(width), mode="valid")
        variance = np.maximum(squares - sums ** 2 / (N_MELS * width), 1e-9)
        scores = numerator / np.sqrt(energy * variance)
        best = max(best, float(np.max(scores)))
    return float(np.clip(best, 0, 1))


class Detector:
    def __init__(self, directory: Path):
        self.templates: list[Template] = []
        self.errors: list[str] = []
        for path in sorted(directory.glob("*.wav")):
            try:
                audio = read_wav(path)
                if not SAMPLE_RATE * 0.25 <= len(audio) <= SAMPLE_RATE * 8:
                    raise ValueError("длина должна быть от 0,25 до 8 секунд")
                matrix = features(audio)
                if float(np.linalg.norm(matrix)) < 1:
                    raise ValueError("недостаточно звуковых данных")
                kind = "negative" if path.name.startswith("negative_") else "positive"
                self.templates.append(Template(path.stem, kind, matrix, len(audio)))
            except Exception as exc:
                self.errors.append(f"{path.name}: {exc}")
        self.window_samples = max((t.samples for t in self.templates), default=SAMPLE_RATE) * 1.07
        self.window_samples = int(self.window_samples + SAMPLE_RATE * 0.6)

    @property
    def positives(self) -> int:
        return sum(t.kind == "positive" for t in self.templates)

    def score(self, audio: np.ndarray) -> tuple[float, float, str]:
        matrix = features(audio)
        positive, negative, name = 0.0, 0.0, ""
        for template in self.templates:
            value = similarity(template.matrix, matrix)
            if template.kind == "negative":
                negative = max(negative, value)
            elif value > positive:
                positive, name = value, template.name
        return positive, negative, name


class TriggerGate:
    """One notification per event; rearms only after the signal disappears."""
    def __init__(self, threshold: float, cooldown: float, margin: float = 0.06):
        self.threshold = threshold
        self.cooldown = cooldown
        self.margin = margin
        self.armed = True
        self.last_trigger = float("-inf")
        self.quiet_since: float | None = None

    def update(self, positive: float, negative: float, now: float) -> bool:
        hit = positive >= self.threshold and positive >= negative + self.margin
        if positive < self.threshold - 0.1:
            if self.quiet_since is None:
                self.quiet_since = now
            if now - self.quiet_since >= 1.0 and now - self.last_trigger >= self.cooldown:
                self.armed = True
        else:
            self.quiet_since = None
        if hit and self.armed and now - self.last_trigger >= self.cooldown:
            self.armed = False
            self.last_trigger = now
            return True
        return False
