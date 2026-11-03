import json
import re
import urllib.error
import urllib.parse
import urllib.request


def validate(token: str, chat_id: str):
    if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{20,}", token):
        raise ValueError("Проверь токен бота, полученный у @BotFather.")
    if not re.fullmatch(r"-?\d+|@[A-Za-z][A-Za-z0-9_]{4,}", chat_id):
        raise ValueError("Укажи числовой chat ID или @имя канала.")


def send_message(token: str, chat_id: str, text: str) -> None:
    validate(token, chat_id)
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        descriptions = {400: "Проверь chat ID и нажми Start в чате с ботом.",
                        401: "Неверный токен бота.", 403: "Бот заблокирован или не имеет доступа к чату.",
                        429: "Telegram ограничил частоту сообщений. Попробуй позже."}
        # Do not include exception URL: it contains the secret token.
        raise RuntimeError(descriptions.get(exc.code, f"Ошибка Telegram HTTP {exc.code}.")) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError("Telegram недоступен: проверь интернет. Повторной отправки не будет.") from None
    if not result.get("ok"):
        raise RuntimeError("Telegram не подтвердил доставку сообщения.")
