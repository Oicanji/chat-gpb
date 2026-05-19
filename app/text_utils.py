import re
import unicodedata

MIN_TOKEN_LEN = 3


def clean_visible(text: str) -> str:
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize(text: str) -> str:
    lowered = text.lower()
    nfkd = unicodedata.normalize("NFKD", lowered)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def tokenize_raw(query: str, stopwords: set[str]) -> list[str]:
    norm = normalize(clean_visible(query))
    tokens = re.findall(r"[a-z0-9]+", norm)
    filtered = [t for t in tokens if len(t) >= MIN_TOKEN_LEN and t not in stopwords]
    return filtered or [t for t in tokens if len(t) >= MIN_TOKEN_LEN]
