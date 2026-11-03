"""Extract local videos for sample preparation; requires imageio-ffmpeg."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import imageio_ffmpeg
import numpy as np

from rf4_notifier.detector import SAMPLE_RATE, read_wav


def main():
    root = Path(__file__).resolve().parents[1] / "examples"
    extracted = root / "extracted"
    extracted.mkdir(exist_ok=True)
    for source in sorted(root.glob("*.mp4")):
        destination = extracted / f"{source.stem}.wav"
        if not destination.exists():
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-hide_banner",
                            "-loglevel", "error", "-n", "-i", str(source), "-vn", "-ac", "1",
                            "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(destination)], check=True)
        audio = read_wav(destination)
        frame = SAMPLE_RATE // 20
        count = len(audio) // frame
        rms = np.sqrt(np.mean(audio[:count * frame].reshape(count, frame) ** 2, axis=1))
        floor = float(np.quantile(rms, 0.2))
        peak = float(rms.max())
        active = rms > max(peak * 0.15, floor * 4, 0.0003)
        changes = np.diff(np.r_[False, active, False].astype(int))
        spans = list(zip(np.flatnonzero(changes == 1) / 20, np.flatnonzero(changes == -1) / 20))
        print(f"{source.name}: duration={len(audio)/SAMPLE_RATE:.2f}s; rms_peak={peak:.5f}; floor={floor:.5f}")
        print("  active regions:", spans)
        print("  RMS / 0.5s:", [round(float(np.max(rms[i:i + 10])), 4) for i in range(0, len(rms), 10)])


if __name__ == "__main__":
    main()
