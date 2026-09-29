"""Loaders for the LinkedIn export and the optional side files."""

import csv
import io
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


@dataclass
class Connection:
    first: str
    last: str
    url: str
    email: str
    company: str
    position: str
    connected_on: date | None

    @property
    def name(self) -> str:
        return f"{self.first} {self.last}".strip()


@dataclass
class SecondDegree:
    name: str
    title: str
    url: str
    company: str
    mutuals: list[str] = field(default_factory=list)


DEFAULT_PROFILE = {
    "name": "[Your Name]",
    "headline": "[your current role]",
    "goal": "[what you're looking for, e.g. exploring senior design roles]",
    "functions": [],
    "past_companies": [],
}


def _read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8-sig")


def _parse_date(raw: str) -> date | None:
    raw = (raw or "").strip()
    for fmt in ("%d %b %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def load_connections(path: Path) -> list[Connection]:
    """Read LinkedIn's Connections.csv, skipping the "Notes:" preamble it ships with."""
    lines = _read_text(path).splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("First Name")), None)
    if start is None:
        raise ValueError(f"{path}: no 'First Name,...' header row found - is this a LinkedIn Connections export?")
    rows = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    return [
        Connection(
            first=(r.get("First Name") or "").strip(),
            last=(r.get("Last Name") or "").strip(),
            url=(r.get("URL") or "").strip(),
            email=(r.get("Email Address") or "").strip(),
            company=(r.get("Company") or "").strip(),
            position=(r.get("Position") or "").strip(),
            connected_on=_parse_date(r.get("Connected On", "")),
        )
        for r in rows
        if (r.get("First Name") or r.get("Last Name"))
    ]


def load_second_degree(path: Path, default_company: str) -> list[SecondDegree]:
    """Read a hand-collected list of 2nd-degree people and their mutual connections.

    Columns: Name, Title, URL (optional), Company (optional), Mutual Connections
    (names separated by ';' or '|').
    """
    out = []
    for r in csv.DictReader(io.StringIO(_read_text(path))):
        name = (r.get("Name") or "").strip()
        if not name:
            continue
        mutuals = re.split(r"[;|]", r.get("Mutual Connections") or "")
        out.append(
            SecondDegree(
                name=name,
                title=(r.get("Title") or "").strip(),
                url=(r.get("URL") or "").strip(),
                company=(r.get("Company") or "").strip() or default_company,
                mutuals=[m.strip() for m in mutuals if m.strip()],
            )
        )
    return out


def load_notes(path: Path | None) -> dict[str, str]:
    """Personal shared-history notes keyed by normalized name and by profile URL."""
    if not path or not Path(path).exists():
        return {}
    notes = {}
    for r in csv.DictReader(io.StringIO(_read_text(path))):
        note = (r.get("Note") or "").strip()
        if not note:
            continue
        if (r.get("URL") or "").strip():
            notes[r["URL"].strip().rstrip("/").lower()] = note
        if (r.get("Name") or "").strip():
            notes[normalize_name(r["Name"])] = note
    return notes


def note_for(c: Connection, notes: dict[str, str]) -> str | None:
    return notes.get(c.url.rstrip("/").lower()) or notes.get(normalize_name(c.name))


def load_profile(path: Path | None) -> tuple[dict, bool]:
    """Return (profile, is_real). Falls back to placeholders when no profile exists."""
    if path and Path(path).exists():
        return {**DEFAULT_PROFILE, **json.loads(_read_text(path))}, True
    return dict(DEFAULT_PROFILE), False


def normalize_name(name: str) -> str:
    """Lowercase, strip accents, credentials (', MBA'), emoji and punctuation."""
    name = name.split(",")[0]
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    name = re.sub(r"\(.*?\)", " ", name)
    name = re.sub(r"[^a-zA-Z\s'-]", " ", name).lower()
    return re.sub(r"\s+", " ", name).strip()
