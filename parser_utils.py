# parser_utils.py
"""Pure helper functions used by the Word parser and tests."""
import re


def normalise_header(text: str) -> str:
    text = (text or "").lower().replace("\n", " ")
    for ch in ("\u00b5", "\u03bc", "\uf06d"):
        text = text.replace(ch, "u")
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", "", text)
    return text


def first_numeric_token(text: str, allow_percent: bool = False) -> str:
    if text is None:
        return "--"
    raw = str(text).strip().replace(",", ".")
    if not raw:
        return "--"
    if raw.upper() in {"NC", "N.C.", "NR", "N/R", "--"}:
        return "--"
    if allow_percent:
        percent_match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*%", raw)
        if percent_match:
            return percent_match.group(1)
        ratio_match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", raw)
        if ratio_match and float(ratio_match.group(2)) != 0:
            return str(round(100.0 * float(ratio_match.group(1)) / float(ratio_match.group(2)), 6)).rstrip("0").rstrip(".")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", raw)
    if not match:
        return "--"
    return match.group(0)
