"""Fill message templates with shared-history hooks."""

from pathlib import Path
from string import Template

from .match import normalize_company
from .score import IntroPath, Scored

LINKEDIN_NOTE_LIMIT = 300


def _load(templates_dir: Path, name: str) -> Template:
    return Template((templates_dir / f"{name}.txt").read_text(encoding="utf-8").strip())


def hook(s: Scored) -> str:
    """The opening line, built from the strongest shared-history signal available."""
    c, company = s.person, s.person.company or "your team"
    if s.note:
        return s.note if s.note.endswith((".", "!", "?")) else s.note + "."
    parts = []
    if s.shared:
        what = "the team" if normalize_company(s.shared) == normalize_company(company) else company
        parts.append(f"Having spent time at {s.shared} myself, I've enjoyed following what {what} has been shipping.")
    if s.years >= 8 and c.connected_on:
        parts.append(f"We've been connected since {c.connected_on.year}, which is hard to believe.")
    elif s.years >= 2 and c.connected_on and not parts:
        parts.append(f"Hope you've been well since we connected back in {c.connected_on.year}.")
    elif s.years < 1:
        parts.append("Thanks again for connecting recently.")
    if s.functions and not s.shared:
        parts.append(f"I've been following the {s.functions[0]} work coming out of {company}.")
    return " ".join(parts) or f"Hope all is well at {company}."


def _role_phrase(position: str, company: str) -> str:
    return f"{position} at {company}" if position else f"at {company}"


def _me(profile: dict) -> dict:
    headline = profile["headline"]
    goal = profile["goal"]
    return {
        "my_name": profile["name"],
        "my_first": profile["name"].split()[0],
        "my_headline": headline,
        "my_headline_short": profile.get("headline_short") or headline.split(",")[0].split("|")[0].strip(),
        "goal": goal,
        "goal_short": goal.split(",")[0].strip(),
    }


def insider_message(s: Scored, company: str, profile: dict, templates_dir: Path) -> str:
    name = "talent_ask" if s.talent else "insider_ask"
    return _load(templates_dir, name).safe_substitute(
        _me(profile),
        first_name=s.person.first,
        company=company,
        hook=hook(s),
        their_role_phrase=_role_phrase(s.person.position, s.person.company),
        shared_line=f" (and we overlapped at {s.shared})" if s.shared else "",
    )


def path_messages(p: IntroPath, company: str, profile: dict, templates_dir: Path) -> tuple[str, str]:
    """(intro request to the connector, LinkedIn connect note to the target)."""
    me = _me(profile)
    target_first = p.target.name.split()[0]
    c = p.connector.person
    forwardable = _load(templates_dir, "intro_forwardable").safe_substitute(me, target_first=target_first, company=company)
    request = _load(templates_dir, "intro_request").safe_substitute(
        me,
        first_name=c.first,
        hook=hook(p.connector),
        target_first=target_first,
        target_name=p.target.name,
        target_title=p.target.title or "role unknown",
        target_company_phrase=f" at {p.target.company}" if p.target.company else "",
        company=company,
        forwardable=forwardable,
    )
    note = _load(templates_dir, "connect_note").safe_substitute(
        me,
        target_first=target_first,
        mutual_first=c.first,
        connector_name_last_initial=(c.last[:1] + ".") if c.last else "",
        company=company,
    )
    note = " ".join(note.split())
    if len(note) > LINKEDIN_NOTE_LIMIT:
        note = note[: LINKEDIN_NOTE_LIMIT - 1].rsplit(" ", 1)[0] + "…"
    return request, note


def bridge_message(s: Scored, company: str, reason: str, profile: dict, templates_dir: Path) -> str:
    funcs = profile.get("functions") or []
    return _load(templates_dir, "bridge_ask").safe_substitute(
        _me(profile),
        first_name=s.person.first,
        company=company,
        hook=hook(s),
        bridge_reason=reason,
        function_phrase=funcs[0] if funcs else "relevant",
    )
