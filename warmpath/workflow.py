"""End-to-end: connections export + target company -> ranked insiders, paths, bridges."""

from datetime import date
from pathlib import Path

from .data import load_connections, load_notes, load_profile, load_second_degree
from .match import DIRECT, FAMILY, NAME_MATCH, RELATED, CompanyMatcher
from .report import Result
from .score import build_paths, relationship, score_insider, Scored

MAX_BRIDGES = 12


def run(
    company: str,
    connections_path: Path,
    profile_path: Path | None = None,
    aliases_path: Path | None = None,
    second_degree_path: Path | None = None,
    notes_path: Path | None = None,
    today: date | None = None,
) -> Result:
    today = today or date.today()
    connections = load_connections(connections_path)
    profile, profile_is_real = load_profile(profile_path)
    notes = load_notes(notes_path)
    matcher = CompanyMatcher(company, aliases_path)
    warnings = []
    if not profile_is_real:
        warnings.append("No config/profile.json found - messages use placeholders and 'shared employer' matching is off.")

    insiders, bridges = [], []
    for c in connections:
        where = matcher.classify(c.company)
        if where in (DIRECT, FAMILY, NAME_MATCH):
            insiders.append(score_insider(c, where, profile, notes, today))
        elif where == RELATED:
            bridges.append(_bridge(c, f"works at {c.company}, a sister/partner company of {matcher.canonical}", profile, notes, today, 4))
        elif matcher.alumni_mention(c.position):
            bridges.append(_bridge(c, f"headline mentions past time at {matcher.canonical}", profile, notes, today, 6))
    insiders.sort(key=lambda s: -s.score)

    # Your warmest insiders are also your best connectors to everyone else inside.
    for s in sorted((s for s in insiders if s.match != NAME_MATCH), key=lambda s: -relationship(s.person, profile, notes, today)[0])[:3]:
        bridges.append((s, f"insider at {s.person.company} - ask who they'd recommend you talk to on the team"))
    bridges.sort(key=lambda b: -b[0].score)

    paths, orphans = [], []
    if second_degree_path:
        second = load_second_degree(second_degree_path, company)
        paths, orphans = build_paths(second, connections, matcher, profile, notes, today)
        if not second:
            warnings.append(f"{second_degree_path} has no rows.")

    return Result(
        company=company,
        insiders=insiders,
        paths=paths,
        orphans=orphans,
        bridges=bridges[:MAX_BRIDGES],
        had_second_degree=bool(second_degree_path),
        profile=profile,
        profile_is_real=profile_is_real,
        total_connections=len(connections),
        today=today,
        warnings=warnings,
    )


def _bridge(c, why, profile, notes, today, bonus) -> tuple[Scored, str]:
    score, reasons, rel = relationship(c, profile, notes, today)
    return Scored(c, round(score + bonus, 1), reasons, None, rel["note"], rel["shared"], [], rel["years"]), why
