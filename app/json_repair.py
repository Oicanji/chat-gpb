import json
import re


def repair_json_text(text: str) -> str:
    t = text.strip()
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    t = re.sub(r'(\d)\s*"(\s*[}\],])', r"\1\2", t)
    t = re.sub(r'("(?:[^"\\]|\\.)*")\s*"(\s*[},])', r"\1\2", t)
    return t


def loads_json_object(text: str) -> dict | list:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    last_error: json.JSONDecodeError | None = None
    for candidate in (cleaned, repair_json_text(cleaned)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise json.JSONDecodeError("JSON vazio", cleaned, 0)
