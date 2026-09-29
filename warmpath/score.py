"""Scoring for insiders (1st-degree at target) and warm-intro paths (connector -> 2nd-degree)."""

import re
from dataclasses import dataclass, field
from datetime import date

from .data import Connection, SecondDegree, normalize_name, note_for
from .match import DIRECT, FAMILY, NAME_MATCH, CompanyMatcher, normalize_company

_SENIORITY = [
    (5, r"\b(chief|ceo|cto|cmo|cpo|cdo|coo|cco|founder|co founder|president|partner)\b"),
    (4, r"\b(svp|evp|vp|vice president|head of|head)\b"),
    (3, r"\b(director|general manager|gm)\b"),
    (2, r"\b(principal|staff|lead|manager)\b"),
    (1, r"\b(senior|sr)\b"),
]
_TALENT = r"\b(recruit\w*|talent|sourc\w*|people partner|hr|human resources)\b"


def seniority(title: str) -> int:
    t = normalize_company(title)
    return max((lvl for lvl, pat in _SENIORITY if re.search(pat, t)), default=0)


def is_talent(title: str) -> bool:
    return re.search(_TALENT, normalize_company(title)) is not None


def function_overlap(title: str, functions: list[str]) -> list[str]:
    t = normalize_company(title)
    return [f for f in functions if re.search(rf"\b{re.escape(normalize_company(f))}", t)]


def years_connected(c: Connection, today: date) -> float:
    return (today - c.connected_on).days / 365.25 if c.connected_on else 0.0


def shared_employer(c: Connection, profile: dict) -> str | None:
    """A past employer of yours that appears in their current company or headline."""
    haystack = " " + normalize_company(f"{c.company} {c.position}") + " "
    for past in profile.get("past_companies", []):
        if f" {normalize_company(past)} " in haystack:
            return past
    return None


@dataclass
class Scored:
    person: Connection
    score: float
    reasons: list[str]
    match: str | None = None
    note: str | None = None
    shared: str | None = None
    functions: list[str] = field(default_factory=list)
    years: float = 0.0
    talent: bool = False


def relationship(c: Connection, profile: dict, notes: dict, today: date) -> tuple[float, list[str], dict]:
    """How warm is your tie to this person? Shared by insider and connector scoring."""
    score, reasons = 0.0, []
    years = years_connected(c, today)
    note = note_for(c, notes)
    shared = shared_employer(c, profile)
    if note:
        score += 12
        reasons.append("personal history note")
    if shared:
        score += 6
        reasons.append(f"shared employer: {shared}")
    if years >= 1:
        score += min(years, 12)
        reasons.append(f"connected {int(years)}y")
    else:
        reasons.append("connected <1y")
    if c.email:
        score += 2
        reasons.append("email on file")
    return score, reasons, {"note": note, "shared": shared, "years": years}


def score_insider(c: Connection, match: str, profile: dict, notes: dict, today: date) -> Scored:
    score, reasons, rel = relationship(c, profile, notes, today)
    lvl = seniority(c.position)
    talent = is_talent(c.position)
    funcs = function_overlap(c.position, profile.get("functions", []))
    score += 10 + lvl * 3
    if lvl >= 3:
        reasons.insert(0, "senior / hiring influence")
    if talent:
        score += 8
        reasons.insert(0, "recruiting / talent")
    if funcs:
        score += 6
        reasons.insert(0, f"same function ({', '.join(funcs)})")
    if match == NAME_MATCH:
        score -= 5
        reasons.append("company name match - verify")
    return Scored(c, round(score, 1), reasons, match, rel["note"], rel["shared"], funcs, rel["years"], talent)


@dataclass
class IntroPath:
    target: SecondDegree
    connector: Scored
    score: float
    unresolved: list[str]


def build_paths(
    second: list[SecondDegree],
    connections: list[Connection],
    matcher: CompanyMatcher,
    profile: dict,
    notes: dict,
    today: date,
) -> tuple[list[IntroPath], list[tuple[SecondDegree, list[str]]]]:
    """Resolve each 2nd-degree person's mutuals to your connections and rank the paths.

    Returns (all paths sorted best-first, people with no resolvable mutual).
    """
    by_full: dict[str, list[Connection]] = {}
    by_first_last: dict[str, list[Connection]] = {}
    for c in connections:
        full = normalize_name(c.name)
        by_full.setdefault(full, []).append(c)
        toks = full.split()
        if len(toks) >= 2:
            by_first_last.setdefault(f"{toks[0]} {toks[-1]}", []).append(c)

    def resolve(name: str) -> Connection | None:
        n = normalize_name(name)
        hits = by_full.get(n)
        if not hits:
            toks = n.split()
            hits = by_first_last.get(f"{toks[0]} {toks[-1]}") if len(toks) >= 2 else None
        return hits[0] if hits and len(hits) == 1 else None

    paths, orphans = [], []
    for person in second:
        target_lvl = seniority(person.title)
        target_fn = function_overlap(person.title, profile.get("functions", []))
        resolved, unresolved = [], []
        for m in person.mutuals:
            c = resolve(m)
            (resolved if c else unresolved).append(c or m)
        if not resolved:
            orphans.append((person, unresolved))
            continue
        for c in resolved:
            score, reasons, rel = relationship(c, profile, notes, today)
            where = matcher.classify(c.company)
            if where in (DIRECT, FAMILY):
                score += 10
                reasons.insert(0, f"works at {c.company} (inside intro)")
            score += seniority(c.position)
            connector = Scored(c, round(score, 1), reasons, where, rel["note"], rel["shared"], [], rel["years"])
            total = score + target_lvl * 2 + (6 if target_fn else 0) + (4 if is_talent(person.title) else 0)
            paths.append(IntroPath(person, connector, round(total, 1), unresolved))
    paths.sort(key=lambda p: -p.score)
    return paths, orphans
