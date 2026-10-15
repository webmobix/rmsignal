"""Pseudonymisation of direct identifiers before text reaches a model."""

import hashlib
import re


class Pseudonymiser:
    """Stable pseudonyms for names. ``protect`` goes to the model, ``restore`` only into the final report."""

    def __init__(self, salt: str = "rm-dashboard"):
        self.salt = salt
        self._to_pseudo: dict[str, str] = {}
        self._to_name: dict[str, str] = {}

    def pseudonym(self, key: str) -> str:
        return "PERSON_" + hashlib.sha256(f"{self.salt}:{key}".encode()).hexdigest()[:6].upper()

    def register(self, name: str, *, key: str, entity: bool = False, min_token: int = 4) -> str:
        """Register a person or organisation. Individuals' name parts are replaced too."""
        pseudo = self.pseudonym(key)
        self._to_name[pseudo] = name
        forms = {name}
        if not entity:
            forms |= {t for t in re.split(r"[\s\-]+", name) if len(t) >= min_token}
        for f in forms:
            self._to_pseudo[f.lower()] = pseudo
        return pseudo

    def protect(self, text: str) -> str:
        if not self._to_pseudo:
            return text
        pattern = "|".join(re.escape(n) for n in sorted(self._to_pseudo, key=len, reverse=True))
        return re.sub(rf"(?<!\w)(?:{pattern})(?!\w)", lambda m: self._to_pseudo[m.group(0).lower()], text, flags=re.I)

    def restore(self, text: str) -> str:
        return re.sub(r"PERSON_[0-9A-F]{6}", lambda m: self._to_name.get(m.group(0), m.group(0)), text)

    def protect_messages(self, messages: list[dict]) -> list[dict]:
        return [{**m, "content": self.protect(m["content"]) if isinstance(m.get("content"), str) else m.get("content")}
                for m in messages]
