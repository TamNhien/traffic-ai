"""Unicode-aware but restrictive login IDs: NFC display and stable casefold key."""
from __future__ import annotations
import unicodedata

SEPARATORS = frozenset("_.-")


def username_key(value: str) -> str:
    # A canonical DB key also ensures differently-cased Vietnamese login IDs cannot coexist.
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", value.strip()).casefold())


def validate_username(value: str) -> str:
    value = unicodedata.normalize("NFC", value.strip())
    if not 3 <= len(value) <= 80 or len(username_key(value)) > 80:
        raise ValueError("Tên đăng nhập phải từ 3 đến 80 ký tự")
    if value[0] in SEPARATORS or value[-1] in SEPARATORS:
        raise ValueError("Tên đăng nhập phải bắt đầu và kết thúc bằng chữ hoặc số")
    for i, char in enumerate(value):
        category = unicodedata.category(char)
        if char in SEPARATORS:
            continue
        if category[0] in {"L", "N"}:
            continue
        if category[0] == "M" and i > 0 and unicodedata.category(value[i - 1])[0] in {"L", "M"}:
            continue
        raise ValueError("Tên đăng nhập chỉ được gồm chữ tiếng Việt, số, dấu chấm, gạch nối và gạch dưới; không có khoảng trắng")
    return value
