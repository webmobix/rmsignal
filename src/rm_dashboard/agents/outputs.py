"""Reading a model's final answer: one JSON object, possibly fenced or surrounded by prose."""

import json
import re


def parse_object_list(text: str | None, key: str) -> tuple[list, str | None]:
    """(items under ``key``, error)."""
    if not text or not text.strip():
        return [], "the model produced no answer"
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-z]*\n?|```$", "", s, flags=re.M).strip()
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end <= start:
        return [], "the model's answer was not JSON"
    try:
        obj = json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return [], "the model's answer was not valid JSON"
    items = obj.get(key) if isinstance(obj, dict) else None
    return (items, None) if isinstance(items, list) else ([], f"the model's answer had no {key} list")


def parse_json_object(text: str | None) -> tuple[dict | None, str | None]:
    """(object, error)."""
    if not text or not text.strip():
        return None, "the model produced no answer"
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-z]*\n?|```$", "", s, flags=re.M).strip()
    start, end = s.find("{"), s.rfind("}")
    if start < 0 or end <= start:
        return None, "the model's answer was not JSON"
    try:
        obj = json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return None, "the model's answer was not valid JSON"
    return (obj, None) if isinstance(obj, dict) else (None, "the model's answer was not an object")
