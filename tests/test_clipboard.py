import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from rf4_notifier.ui import ClipboardEntry, setup_theme


class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        setup_theme(self.root)
        self.entry = ClipboardEntry(self.root, secret=True, show="•")
        self.entry.pack()
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def paste_text(self, text, **kwargs):
        # Mock the read; never touch or print the user's actual clipboard.
        with patch.object(self.entry, "clipboard_get", return_value=text):
            return self.entry.paste(**kwargs)

    def test_paste_button_replaces_existing_value_and_trims_edges(self):
        self.entry.insert(0, "previous")
        self.paste_text(" 123456:example_not_a_real_token\r\n", replace_all=True)
        self.assertEqual(self.entry.get(), "123456:example_not_a_real_token")
        self.assertEqual(self.entry.cget("show"), "•")

    def test_paste_replaces_selection(self):
        self.entry.insert(0, "old")
        self.entry.selection_range(0, "end")
        self.paste_text("new")
        self.assertEqual(self.entry.get(), "new")

    def test_ctrl_v_with_russian_layout(self):
        with patch.object(self.entry, "clipboard_get", return_value="sample"):
            result = self.entry._control_key(SimpleNamespace(keycode=86, keysym="Cyrillic_em"))
        self.assertEqual(result, "break")
        self.assertEqual(self.entry.get(), "sample")

    def test_ctrl_a_with_russian_layout(self):
        self.entry.insert(0, "sample")
        self.entry._control_key(SimpleNamespace(keycode=65, keysym="Cyrillic_ef"))
        self.assertTrue(self.entry.selection_present())

    def test_empty_clipboard_does_not_erase_value(self):
        self.entry.insert(0, "keep")
        self.paste_text("  ", replace_all=True)
        self.assertEqual(self.entry.get(), "keep")

    def test_unavailable_clipboard_shows_safe_message(self):
        with patch.object(self.entry, "clipboard_get", side_effect=tk.TclError), patch(
            "rf4_notifier.ui.messagebox.showwarning"
        ) as warning:
            self.assertEqual(self.entry.paste(), "break")
            warning.assert_called_once()

    def test_disabled_entry_does_not_read_clipboard(self):
        self.entry.state(("disabled",))
        with patch.object(self.entry, "clipboard_get") as read:
            self.entry.paste()
            read.assert_not_called()

    def test_virtual_paste_uses_handler_once(self):
        with patch.object(self.entry, "clipboard_get", return_value="example") as read:
            self.entry.event_generate("<<Paste>>")
        self.assertEqual(self.entry.get(), "example")
        read.assert_called_once()


if __name__ == "__main__":
    unittest.main()
