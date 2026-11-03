r"""Run manually on Windows: .venv\Scripts\python.exe tests\gui_smoke.py."""
import sys
import argparse
import ctypes
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from rf4_notifier.app import App, SampleEditor
from rf4_notifier.detector import SAMPLE_RATE


parser = argparse.ArgumentParser()
parser.add_argument("--screenshots", type=Path, help="optional screenshots folder; requires Pillow")
parser.add_argument("--live-audio", action="store_true", help="brief dry run using actual loopback device")
args = parser.parse_args()


def screenshot(app, name):
    if args.screenshots:
        from PIL import ImageGrab
        args.screenshots.mkdir(parents=True, exist_ok=True)
        app.lift()
        app.update()
        hwnd = ctypes.windll.user32.GetParent(app.winfo_id())
        ImageGrab.grab(window=hwnd).save(args.screenshots / name)


# Never display or save actual credentials during UI testing.
with patch("rf4_notifier.app.config.load", return_value={}):
    app = App()
app.update()
print(f"GUI initialized; loopback devices: {len(app.devices)}; samples: {app.sample_list.size()}")
assert len(app.pages) == 4
for page in app.pages:
    app.show_page(page)
    app.update()
    assert app.active_page == page
    screenshot(app, f"{page}.png")

app.show_page("overview")
app._set_busy(True)
assert str(app.start_button.cget("state")) == "disabled"
app._set_busy(False)
assert str(app.start_button.cget("state")) == "normal"
app.events.put(("meter", (35, 0.86, 0.12)))
app.events.put(("bite", ("positive_test", 0.86)))
app.events.put(("telegram", ("", "", "Сообщение принято")))
app._drain_events()
assert app.detection_count == 1
assert app.score_metric.value.cget("text") == "86%"
assert app.telegram_state.get() == "Сообщение принято"
assert len(app.chart.history) == 1

for size in ("1100x780", "1400x900"):
    app.geometry(size)
    app.update()
    assert app.start_button.winfo_width() > 100
    assert app.chart.winfo_height() > 70
    for page in app.pages:
        app.show_page(page)
        app.update()
        if size == "1100x780":
            screenshot(app, f"{page}-compact.png")

app.show_page("overview")

editor = SampleEditor(app, np.sin(np.arange(SAMPLE_RATE) * 0.05).astype(np.float32) * 0.1,
                      lambda *_: None)
app.update()
assert len(editor.selection()) == SAMPLE_RATE
editor.close()
app.update()
if args.live_audio:
    assert app.devices and app.sample_list.size(), "Live test requires a device and installed samples"
    with patch("rf4_notifier.app.config.save"):
        app.start(True)
    app.after(2000, app.stop)
    app.after(3500, app.quit)
    app.mainloop()
    assert not app.worker.is_alive(), "Audio worker did not stop"
    assert len(app.chart.history) > 1, "No live meter events received"
    print(f"Live audio dashboard passed: {len(app.chart.history)} meter updates")
app.close()
print("Navigation, dashboard events, resize, controls and sample editor smoke test passed")
