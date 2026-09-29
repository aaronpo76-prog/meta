"""Company-name matching: exact, corporate family, sister companies, and loose name matches."""

import json
import re
from pathlib import Path

_SUFFIXES = r"(inc|llc|ltd|limited|corp|corporation|co|company|gmbh|plc|pbc|sa|ag)"

DIRECT, FAMILY, NAME_MATCH, RELATED = "direct", "family", "name-match", "related"


def normalize_company(name: str) -> str:
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[®™©]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    s = re.sub(rf"(\s{_SUFFIXES})+$", "", s)
    s = re.sub(r"^the\s+", "", s)
    return s


def _contains_word(haystack: str, needle: str) -> bool:
    return bool(needle) and re.search(rf"(^|\s){re.escape(needle)}(\s|$)", haystack) is not None


class CompanyMatcher:
    """Resolves a target company into the set of employer names that count as "at" it."""

    def __init__(self, target: str, aliases_path: Path | None = None):
        self.target = target
        t = normalize_company(target)
        self.members = {t}
        self.related: set[str] = set()
        self.canonical = target
        groups = _load_groups(aliases_path)
        # A group named after the target defines it; otherwise use any group listing it as a member.
        own = [g for g in groups if normalize_company(g["name"]) == t]
        for group in own or groups:
            names = {normalize_company(n) for n in [group["name"], *group.get("members", [])]}
            if t in names:
                self.canonical = group["name"]
                self.members |= names
                self.related |= {normalize_company(n) for n in group.get("related", [])}
        self.related -= self.members
        self._target_norm = t

    def classify(self, company: str) -> str | None:
        c = normalize_company(company)
        if not c:
            return None
        if c == self._target_norm:
            return DIRECT
        if c in self.members:
            return FAMILY
        if c in self.related:
            return RELATED
        # "Google DeepMind", "Intuit Mailchimp", "Prime Video & Amazon MGM Studios"
        if any(_contains_word(c, m) for m in self.members if len(m) >= 3):
            return NAME_MATCH
        return None

    def alumni_mention(self, position: str) -> bool:
        """True when a headline says ex-/formerly/previously <target>."""
        p = " " + normalize_company(position.replace("ex-", "ex ")) + " "
        return any(
            re.search(rf"\b(ex|formerly|previously|former|alum|alumni)( at| of)? {re.escape(m)}\b", p)
            for m in self.members
        )


def _load_groups(path: Path | None) -> list[dict]:
    if not path or not Path(path).exists():
        return []
    return json.loads(Path(path).read_text(encoding="utf-8"))["groups"]
