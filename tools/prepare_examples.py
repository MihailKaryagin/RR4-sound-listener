"""Prepare bite templates and test separate pulses; never modifies source videos."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from scipy.io import wavfile

from rf4_notifier.detector import Detector, SAMPLE_RATE, TriggerGate, features, read_wav, similarity
from rf4_notifier.paths import data_dir


def pulses(audio):
    frame = SAMPLE_RATE // 100
    count = len(audio) // frame
    rms = np.sqrt(np.mean(audio[:count * frame].reshape(count, frame) ** 2, axis=1))
    active = rms > max(float(rms.max()) * 0.15, 0.0003)
    edges = np.diff(np.r_[False, active, False].astype(int))
    regions = list(zip(np.flatnonzero(edges == 1) / 100, np.flatnonzero(edges == -1) / 100))
    merged = []
    for start, end in regions:
        if merged and start - merged[-1][1] < 0.15:
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    duration = len(audio) / SAMPLE_RATE
    return [(max(0, start - 0.08), min(duration, end + 0.12)) for start, end in merged
            if end - start >= 0.35 and start > 0.08 and end < duration - 0.08]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="also add templates to the app's sample folder")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "examples"
    prepared = root / "prepared"
    prepared.mkdir(exist_ok=True)
    report = {"note": "Separate repeated pulses from the same videos, NOT independent sessions or background validation.",
              "samples": [], "validation": [], "cross_scores": {}, "stream_validation": []}
    recordings = {}
    for source in sorted((root / "extracted").glob("*.wav")):
        audio = read_wav(source)
        spans = pulses(audio)
        if len(spans) < 3:
            raise ValueError(f"{source.name}: need at least 3 complete pulses")
        recordings[source.stem] = (audio, spans)
        for index, (start, end) in enumerate(spans[:2], 1):
            destination = prepared / f"positive_{source.stem}_{index:02d}.wav"
            clip = audio[round(start * SAMPLE_RATE):round(end * SAMPLE_RATE)]
            if not destination.exists():
                wavfile.write(destination, SAMPLE_RATE, clip.astype(np.float32))
            report["samples"].append({"file": destination.name, "source": source.name,
                                      "start": start, "end": end})
    detector = Detector(prepared)
    if detector.errors:
        raise ValueError(detector.errors)
    for kind, (audio, spans) in recordings.items():
        for start, end in spans[2:]:
            clip = audio[round(start * SAMPLE_RATE):round(end * SAMPLE_RATE)]
            clip = np.pad(clip, (SAMPLE_RATE // 4, SAMPLE_RATE // 4))
            positive, negative, name = detector.score(clip)
            report["validation"].append({"source": kind, "start": start, "end": end,
                                          "score": round(positive, 4), "match": name})
        start, end = spans[2]
        matrix = features(np.pad(audio[round(start * SAMPLE_RATE):round(end * SAMPLE_RATE)],
                                 (SAMPLE_RATE // 4, SAMPLE_RATE // 4)))
        report["cross_scores"][kind] = {
            other: round(max(similarity(template.matrix, matrix) for template in detector.templates
                             if template.name.startswith(f"positive_{other}_")), 4)
            for other in recordings
        }
        for gain in (1.0, 0.25):
            gate = TriggerGate(0.78, 30)
            stream = np.pad(audio * gain, (SAMPLE_RATE // 2, SAMPLE_RATE * 2))
            detections = []
            for end_sample in range(SAMPLE_RATE // 4, len(stream), SAMPLE_RATE // 4):
                window = stream[max(0, end_sample - detector.window_samples):end_sample]
                positive, negative, name = detector.score(window)
                now = end_sample / SAMPLE_RATE
                if gate.update(positive, negative, now):
                    detections.append({"time": now, "match": name, "score": round(positive, 4)})
            report["stream_validation"].append({"source": kind, "gain": gain, "detections": detections})
            if len(detections) != 1 or not detections[0]["match"].startswith(f"positive_{kind}_"):
                raise AssertionError(f"Unexpected stream result: {kind}, {gain}: {detections}")
    if args.install:
        import shutil
        destination = data_dir() / "samples"
        destination.mkdir(exist_ok=True)
        for sample in report["samples"]:
            target = destination / sample["file"]
            if target.exists():
                if target.read_bytes() != (prepared / sample["file"]).read_bytes():
                    raise FileExistsError(f"Will not overwrite existing sample: {target}")
            else:
                shutil.copy2(prepared / sample["file"], target)
        report["installed_to"] = str(destination)
    (prepared / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
