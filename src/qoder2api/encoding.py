import base64


CUSTOM_ALPHABET = "_doRTgHZBKcGVjlvpC,@aFSx#DPuNJme&i*MzLOEn)sUrthbf%Y^w.(kIQyXqWA!"
STD_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
CUSTOM_PAD = "$"

STD_TO_CUSTOM = str.maketrans(STD_ALPHABET + "=", CUSTOM_ALPHABET + CUSTOM_PAD)
CUSTOM_TO_STD = str.maketrans(CUSTOM_ALPHABET + CUSTOM_PAD, STD_ALPHABET + "=")


def encode(plaintext: bytes) -> str:
    standard = base64.b64encode(plaintext).decode("ascii")
    split = len(standard) // 3
    rearranged = standard[-split:] + standard[split:-split] + standard[:split]
    return rearranged.translate(STD_TO_CUSTOM)


def decode(encoded: str) -> bytes:
    mapped = encoded.translate(CUSTOM_TO_STD)
    split = len(mapped) // 3
    standard = mapped[-split:] + mapped[split:-split] + mapped[:split]
    return base64.b64decode(standard)
