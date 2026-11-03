import queue
import threading
import time
import tkinter as tk
import uuid
import winsound
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from scipy.io import wavfile

from . import config
from .audio import Capture, list_devices
from .detector import Detector, SAMPLE_RATE, TriggerGate, mono_resample, read_wav, trim_recording
from .paths import data_dir
from .telegram import send_message, validate
from . import ui


class SampleEditor(tk.Toplevel):
    def __init__(self, parent, audio: np.ndarray, save_callback):
        super().__init__(parent)
        self.title("Выделить образец звука")
        self.geometry("800x450")
        self.minsize(740, 420)
        self.configure(bg=ui.CARD)
        self.after(0, lambda: ui.dark_titlebar(self))
        self.audio = audio
        self.save_callback = save_callback
        self.duration = len(audio) / SAMPLE_RATE
        self.playing = False
        self.start = tk.DoubleVar(value=0)
        self.end = tk.DoubleVar(value=self.duration)
        self.kind = tk.StringVar(value="positive")
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Оставь только характерный звук. Фон и ожидание лучше обрезать.").pack(anchor="w")
        self.canvas = tk.Canvas(frame, height=100, background="#162535", highlightthickness=0)
        self.canvas.pack(fill="x", pady=10)
        self.canvas.bind("<Configure>", self.draw)
        self.position = ttk.Label(frame)
        self.position.pack(anchor="w")
        ttk.Scale(frame, from_=0, to=self.duration, variable=self.start, command=self.draw).pack(fill="x")
        ttk.Scale(frame, from_=0, to=self.duration, variable=self.end, command=self.draw).pack(fill="x")
        kinds = ttk.Frame(frame)
        kinds.pack(fill="x", pady=12)
        ttk.Radiobutton(kinds, text="Поклёвка", variable=self.kind, value="positive").pack(side="left")
        ttk.Radiobutton(kinds, text="Не поклёвка (ложный звук)", variable=self.kind, value="negative").pack(side="left", padx=16)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Прослушать выделение", command=self.play).pack(side="left")
        ttk.Button(buttons, text="Сохранить образец", command=self.save).pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.transient(parent)
        self.grab_set()

    def draw(self, *_):
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 10)
        start, end = self.start.get(), self.end.get()
        self.canvas.create_rectangle(width * start / self.duration, 0, width * end / self.duration, 100,
                                     fill="#28586b", outline="")
        step = max(1, len(self.audio) // width)
        peak = max(float(np.max(np.abs(self.audio))), 0.01)
        for x in range(width):
            values = self.audio[x * step:(x + 1) * step]
            if not len(values):
                break
            height = float(np.max(np.abs(values))) / peak * 45
            self.canvas.create_line(x, 50 - height, x, 50 + height, fill="#54d7c0")
        self.position.config(text=f"Начало: {start:.2f} с     Конец: {end:.2f} с     Длина: {max(0, end - start):.2f} с")

    def selection(self):
        length = self.end.get() - self.start.get()
        if not 0.25 <= length <= 8:
            raise ValueError("Выдели от 0,25 до 8 секунд звука.")
        return self.audio[int(self.start.get() * SAMPLE_RATE):int(self.end.get() * SAMPLE_RATE)]

    def play(self):
        if self.playing:
            return
        try:
            import io
            buffer = io.BytesIO()
            wavfile.write(buffer, SAMPLE_RATE, (np.clip(self.selection(), -1, 1) * 32767).astype(np.int16))
            # Synchronous memory playback runs outside Tk's UI thread.
            self.playing = True
            def playback():
                try:
                    winsound.PlaySound(buffer.getvalue(), winsound.SND_MEMORY)
                except RuntimeError:
                    pass
                finally:
                    self.playing = False
            threading.Thread(target=playback, daemon=True).start()
        except Exception as exc:
            messagebox.showerror("Прослушивание", str(exc), parent=self)

    def save(self):
        try:
            selection = self.selection()
            if np.sqrt(np.mean(selection ** 2)) < 0.0001:
                raise ValueError("Выделение слишком тихое.")
            self.save_callback(selection, self.kind.get())
            self.close()
        except Exception as exc:
            messagebox.showerror("Образец", str(exc), parent=self)

    def close(self):
        winsound.PlaySound(None, 0)
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bite Watch · РР4")
        self.geometry("1200x840")
        self.minsize(1100, 780)
        self.samples_dir = data_dir() / "samples"
        self.samples_dir.mkdir(exist_ok=True)
        self.events = queue.Queue()
        self.network_jobs = queue.Queue(maxsize=4)
        self.capture = None
        self.worker = None
        self.worker_stop = threading.Event()
        self.pending = False
        self.devices = []
        self.config_warning = ""
        try:
            saved = config.load()
        except Exception:
            saved = {}
            self.config_warning = "Не удалось прочитать настройки. Введи токен заново."
        self.token = tk.StringVar(value=saved.get("token", ""))
        self.chat = tk.StringVar(value=saved.get("chat_id", ""))
        self.threshold = tk.DoubleVar(value=float(saved.get("threshold", 0.78)))
        self.cooldown = tk.IntVar(value=int(saved.get("cooldown", 30)))
        self.record_seconds = tk.IntVar(value=6)
        self.status = tk.StringVar(value="Остановлено")
        self.level = tk.DoubleVar(value=0)
        self.score_text = tk.StringVar(value="Ложный звук: —")
        self._build()
        self.refresh_devices(saved.get("device_name"))
        self.refresh_samples()
        threading.Thread(target=self._network_loop, daemon=True, name="telegram-worker").start()
        self.after(80, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self.close)
        if self.config_warning:
            self.log(self.config_warning)

    def _build(self):
        ui.build_dashboard(self)

    def log(self, text):
        self.log_box.config(state="normal")
        tag = "bite" if "Похоже на поклёвку" in text else "success" if "Telegram принял" in text else ""
        self.log_box.insert("end", f"{datetime.now():%H:%M:%S}  {text}\n", tag)
        if int(self.log_box.index("end-1c").split(".")[0]) > 500:
            self.log_box.delete("1.0", "100.0")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def refresh_devices(self, preferred=None):
        try:
            self.devices = list_devices()
            self.device_box["values"] = [d["name"] for d in self.devices]
            if self.devices:
                index = next((i for i, d in enumerate(self.devices) if d["name"] == preferred), 0)
                self.device_box.current(index)
            else:
                self.log("Нет loopback-устройств. Подключи наушники или динамики и нажми «Обновить».")
        except Exception as exc:
            self.log(f"Не удалось получить устройства: {exc}")

    def selected_device(self):
        index = self.device_box.current()
        if index < 0 or index >= len(self.devices):
            raise ValueError("Выбери выходное устройство звука.")
        return self.devices[index]

    def refresh_samples(self):
        self.sample_paths = sorted(self.samples_dir.glob("*.wav"))
        self.sample_list.delete(0, "end")
        for path in self.sample_paths:
            self.sample_list.insert("end", ui.sample_title(path))
            if "krasnaya" in path.stem:
                self.sample_list.itemconfig("end", foreground=ui.CORAL)
            elif "sinaya" in path.stem:
                self.sample_list.itemconfig("end", foreground=ui.BLUE)
            elif "zelenaya" in path.stem:
                self.sample_list.itemconfig("end", foreground=ui.GREEN)
        positive = sum(not path.name.startswith("negative_") for path in self.sample_paths)
        self.sample_summary.set(f"{positive} образцов поклёвки · {len(self.sample_paths) - positive} ложных звуков")

    def add_sample(self, audio, kind):
        name = f"{kind}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.wav"
        wavfile.write(self.samples_dir / name, SAMPLE_RATE, np.asarray(audio, dtype=np.float32))
        self.refresh_samples()
        self.log(f"Сохранён образец: {name}")

    def import_sample(self):
        path = filedialog.askopenfilename(filetypes=[("WAV audio", "*.wav")])
        if not path:
            return
        try:
            if Path(path).stat().st_size > 25 * 1024 * 1024:
                raise ValueError("Файл больше 25 МБ. Сначала обрежь его в аудиоредакторе.")
            audio = read_wav(Path(path))
            if not SAMPLE_RATE * 0.25 <= len(audio) <= SAMPLE_RATE * 30:
                raise ValueError("Импортируй запись длительностью от 0,25 до 30 секунд.")
            SampleEditor(self, audio, self.add_sample)
        except Exception as exc:
            messagebox.showerror("Импорт", str(exc))

    def delete_sample(self):
        selected = self.sample_list.curselection()
        if selected and messagebox.askyesno("Удалить образец?", "Удалить выбранную запись безвозвратно?"):
            try:
                self.sample_paths[selected[0]].unlink()
                self.refresh_samples()
            except OSError as exc:
                messagebox.showerror("Образец", str(exc))

    def settings(self):
        threshold, cooldown = float(self.threshold.get()), int(self.cooldown.get())
        if not 0.5 <= threshold <= 0.98 or not 5 <= cooldown <= 600:
            raise ValueError("Порог: 0,50–0,98. Пауза: 5–600 секунд.")
        return {"token": self.token.get().strip(), "chat_id": self.chat.get().strip(),
                "threshold": threshold, "cooldown": cooldown,
                "device_name": self.device_box.get()}

    def save_settings(self, quiet=False):
        try:
            config.save(self.settings())
            if not quiet:
                self.log("Настройки сохранены. Токен зашифрован Windows DPAPI для текущего пользователя.")
            return True
        except Exception as exc:
            messagebox.showerror("Настройки", str(exc))
            return False

    def test_message(self):
        try:
            validate(self.token.get().strip(), self.chat.get().strip())
            self.telegram_state.set("Отправка теста…")
            self._enqueue_message(self.token.get().strip(), self.chat.get().strip(),
                                  "🎣 РР4: тестовое уведомление. Связь работает!")
        except Exception as exc:
            messagebox.showerror("Telegram", str(exc))

    def _enqueue_message(self, token, chat_id, text):
        try:
            self.network_jobs.put_nowait((token, chat_id, text))
        except queue.Full:
            self.events.put(("log", "Очередь Telegram заполнена. Сообщение пропущено."))
            self.events.put(("telegram", (token, chat_id, "Очередь заполнена · см. журнал")))

    def _network_loop(self):
        while True:
            token, chat_id, text = self.network_jobs.get()
            try:
                send_message(token, chat_id, text)
                self.events.put(("log", "Telegram принял сообщение."))
                self.events.put(("telegram", (token, chat_id, "Сообщение принято")))
            except Exception as exc:
                self.events.put(("log", f"Telegram: {exc}"))
                self.events.put(("telegram", (token, chat_id, "Ошибка отправки · см. журнал")))

    def _set_busy(self, busy):
        for button in (self.start_button, self.dry_button, self.record_button,
                       self.import_button, self.delete_button, self.refresh_button):
            button.config(state="disabled" if busy else "normal")
        self.device_box.config(state="disabled" if busy else "readonly")
        self.stop_button.config(state="normal" if busy else "disabled")

    def _launch(self, target, *args):
        self.worker_stop = threading.Event()
        self._set_busy(True)
        self.show_page("overview")
        self.worker = threading.Thread(target=target, args=args, daemon=True)
        self.worker.start()

    def record(self):
        try:
            device = self.selected_device()
            seconds = int(self.record_seconds.get())
            if not 2 <= seconds <= 20:
                raise ValueError("Длительность записи: от 2 до 20 секунд.")
            self.status.set("Запись… воспроизведи звук")
            self.log("Записывается ВЕСЬ звук выбранного выхода. Убери музыку, голоса и уведомления.")
            self._launch(self._record_worker, device, seconds)
        except Exception as exc:
            messagebox.showerror("Запись", str(exc))

    def _record_worker(self, device, seconds):
        audio_queue = queue.Queue(maxsize=100)
        capture = Capture(device, audio_queue)
        self.capture = capture
        chunks = []
        samples = 0
        rate = int(device["defaultSampleRate"])
        last_audio = time.monotonic()
        capture.start()
        try:
            while not self.worker_stop.is_set() and samples < seconds * rate:
                try:
                    kind, data, rate = audio_queue.get(timeout=0.5)
                except queue.Empty:
                    if not capture.thread.is_alive():
                        break
                    if time.monotonic() - last_audio > 8:
                        raise RuntimeError("Нет аудиоданных 8 секунд. Проверь выбранный выход звука.")
                    continue
                if kind == "error":
                    raise RuntimeError(data)
                if kind == "ended":
                    break
                last_audio = time.monotonic()
                chunks.append(data)
                samples += len(data)
                self.events.put(("level", min(100, float(np.sqrt(np.mean(data ** 2))) * 500)))
                self.events.put(("status", f"Запись: {min(seconds, samples / rate):.1f} / {seconds} с"))
            if not self.worker_stop.is_set() and chunks:
                audio = mono_resample(np.concatenate(chunks), rate)
                audio = trim_recording(audio) if len(audio) <= SAMPLE_RATE * 8 else audio
                self.events.put(("recorded", audio))
        except Exception as exc:
            self.events.put(("log", f"Запись: {exc}"))
        finally:
            capture.stop()
            capture.thread.join(timeout=3)
            self.events.put(("finished", None))

    def start(self, dry_run):
        try:
            device = self.selected_device()
            settings = self.settings()
            if not dry_run:
                validate(settings["token"], settings["chat_id"])
            detector = Detector(self.samples_dir)
            for error in detector.errors:
                self.log(f"Образец пропущен: {error}")
            if not detector.positives:
                raise ValueError("Сначала запиши или импортируй хотя бы один образец поклёвки.")
            if not self.save_settings(quiet=True):
                return
            self.status.set("Проверка без Telegram" if dry_run else "Слушаю игру…")
            self.chart.threshold = settings["threshold"]
            self.chart.history.clear()
            self.chart.draw()
            self.log(f"Запуск: {detector.positives} образцов поклёвки. Совпадение — не вероятность.")
            self._launch(self._monitor_worker, device, settings, detector, dry_run)
        except Exception as exc:
            messagebox.showerror("Запуск", str(exc))

    def _monitor_worker(self, device, settings, detector, dry_run):
        audio_queue = queue.Queue(maxsize=100)
        capture = Capture(device, audio_queue)
        self.capture = capture
        buffer = np.empty(0, dtype=np.float32)
        pending_blocks = []
        gate = TriggerGate(settings["threshold"], settings["cooldown"])
        last_analysis = time.monotonic()
        last_audio = last_analysis
        capture.start()
        try:
            while not self.worker_stop.is_set():
                try:
                    kind, data, rate = audio_queue.get(timeout=0.5)
                except queue.Empty:
                    if not capture.thread.is_alive():
                        break
                    if time.monotonic() - last_audio > 8:
                        raise RuntimeError("Нет аудиоданных 8 секунд. Проверь выбранный выход звука.")
                    continue
                if kind == "error":
                    raise RuntimeError(data)
                if kind == "ended":
                    break
                pending_blocks.append(data)
                now = time.monotonic()
                last_audio = now
                if now - last_analysis < 0.25:
                    continue
                last_analysis = now
                block = mono_resample(np.concatenate(pending_blocks), rate)
                pending_blocks.clear()
                buffer = np.concatenate((buffer, block))[-detector.window_samples:]
                rms = float(np.sqrt(np.mean(block ** 2)))
                positive, negative, name = detector.score(buffer)
                self.events.put(("meter", (min(100, rms * 500), positive, negative)))
                if gate.update(positive, negative, now):
                    self.events.put(("bite", (name, positive)))
                    self.events.put(("log", f"🎣 Похоже на поклёвку! Совпадение {positive:.0%}; {name}"))
                    if not dry_run:
                        text = f"🎣 РР4: обнаружен звук поклёвки!\nВремя ПК: {datetime.now():%H:%M:%S}"
                        self._enqueue_message(settings["token"], settings["chat_id"], text)
            if capture.dropped:
                self.events.put(("log", f"Пропущено аудиоблоков: {capture.dropped}. Сократи число или длину образцов."))
        except Exception as exc:
            self.events.put(("log", f"Захват/распознавание остановлено: {exc}"))
        finally:
            capture.stop()
            capture.thread.join(timeout=3)
            self.events.put(("finished", None))

    def stop(self):
        self.worker_stop.set()
        if self.capture:
            self.capture.stop()
        self.status.set("Остановка…")
        self.stop_button.config(state="disabled")

    def _drain_events(self):
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.log(value)
            elif kind == "status":
                self.status.set(value)
            elif kind == "telegram":
                token, chat_id, state = value
                if token == self.token.get().strip() and chat_id == self.chat.get().strip():
                    self.telegram_state.set(state)
            elif kind == "bite":
                name, score = value
                self.detection_count += 1
                self.count_metric.set(str(self.detection_count))
                self.last_event.set(f"{datetime.now():%H:%M:%S} · {score:.0%} совпадения")
            elif kind == "level":
                self.level.set(value)
                self.level_metric.set(f"{value:.0f}%")
                self.chart.push(value, 0)
            elif kind == "meter":
                level, positive, negative = value
                self.level.set(level)
                self.level_metric.set(f"{level:.0f}%")
                self.score_metric.set(f"{positive:.0%}")
                self.chart.push(level, positive)
                self.score_text.set(f"Ложный звук: {negative:.0%}")
            elif kind == "recorded":
                # Open the modal editor only once capture has fully stopped.
                self.pending = value
            elif kind == "finished":
                self.capture = None
                self._set_busy(False)
                self.status.set("Остановлено")
                self.level.set(0)
                self.level_metric.set("0%")
                if isinstance(self.pending, np.ndarray):
                    audio, self.pending = self.pending, False
                    SampleEditor(self, audio, self.add_sample)
        self.after(80, self._drain_events)

    def close(self):
        self.worker_stop.set()
        if self.capture:
            self.capture.stop()
        winsound.PlaySound(None, 0)
        self.destroy()


def main():
    App().mainloop()
