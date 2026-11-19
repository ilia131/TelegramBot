import unicodedata

MAX_RECEIPT_BYTES = 10 * 1024 * 1024


def valid_name(name: str) -> bool:
    return 1 <= len(name) <= 48 and any(c.isalnum() for c in name) and all(
        unicodedata.category(c)[0] in "LMN" or c in " _-‌" for c in name
    )
