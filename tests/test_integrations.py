import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from rf4_notifier import config
from rf4_notifier.telegram import send_message, validate


class IntegrationTests(unittest.TestCase):
    def test_dpapi_round_trip(self):
        secret = "тестовый секрет".encode()
        encrypted = config._crypt(secret)
        self.assertNotEqual(encrypted, secret)
        self.assertEqual(config._crypt(encrypted, decrypt=True), secret)

    def test_validation(self):
        validate("123456:" + "a" * 30, "123456")
        validate("123456:" + "a" * 30, "-1001234567890")
        with self.assertRaises(ValueError):
            validate("bad", "123")

    def test_saved_config_does_not_contain_plaintext_token(self):
        token = "123456:" + "a" * 30
        with tempfile.TemporaryDirectory() as temp:
            with patch("rf4_notifier.config.data_dir", return_value=Path(temp)):
                config.save({"token": token, "chat_id": "123", "threshold": 0.78})
                text = (Path(temp) / "config.json").read_text(encoding="utf-8")
                self.assertNotIn(token, text)
                loaded = config.load()
                self.assertEqual(loaded["token"], token)
                self.assertEqual(loaded["chat_id"], "123")

    @patch("urllib.request.urlopen")
    def test_successful_request(self, urlopen):
        urlopen.return_value.__enter__.return_value = io.BytesIO(b'{"ok": true}')
        send_message("123456:" + "a" * 30, "123", "hello")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertIn(b"chat_id=123", request.data)

    @patch("urllib.request.urlopen")
    def test_no_token_leaked_in_network_error(self, urlopen):
        token = "123456:" + "a" * 30
        urlopen.side_effect = urllib.error.HTTPError(
            f"https://api.telegram.org/bot{token}/sendMessage", 401, "bad", {}, None)
        with self.assertRaises(RuntimeError) as caught:
            send_message(token, "123", "test")
        self.assertNotIn(token, str(caught.exception))
        self.assertIn("токен", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
