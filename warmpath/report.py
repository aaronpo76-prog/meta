"""Assemble the Markdown report and CSV export."""

import csv
import urllib.parse
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .match import NAME_MATCH
from .outreach import bridge_message, insider_message, path_messages
from .score import IntroPath, Scored


@dataclass
class Result:
    company: str
    insiders: list[Scored]
    paths: list[IntroPath]
    orphans: list
    bridges: list[tuple[Scored, str]]
    had_second_degree: bool
    profile: dict
    profile_is_real: bool
    total_connections: int
    today: date
    warnings: list[str] = field(default_factory=list)


def _cell(s: str) -> str:
    return (s or "").replace("|", "/").replace("\n", " ")


def _since(s: Scored) -> str:
    c = s.person.connected_on
    return c.strftime("%b %Y") if c else "?"


def _link(name: str, url: str) -> str:
    return f"[{_cell(name)}]({url})" if url else _cell(name)


def best_path_per_target(paths: list[IntroPath]) -> list[IntroPath]:
    seen, out = set(), []
    for p in paths:
        if p.target.name not in seen:
            seen.add(p.target.name)
            out.append(p)
    return out


def search_url(company: str) -> str:
    q = urllib.parse.urlencode({"keywords": company, "network": '["S"]', "origin": "FACETED_SEARCH"})
    return f"https://www.linkedin.com/search/results/people/?{q}"


def render_markdown(r: Result, templates_dir: Path, top: int) -> str:
    confirmed = [s for s in r.insiders if s.match != NAME_MATCH]
    possible = [s for s in r.insiders if s.match == NAME_MATCH]
    best_paths = best_path_per_target(r.paths)
    senior = sum(1 for s in confirmed if "senior / hiring influence" in s.reasons)
    talent = sum(1 for s in confirmed if s.talent)

    out = [f"# Warm paths into {r.company}", ""]
    out.append(f"_Generated {r.today.isoformat()} from {r.total_connections:,} LinkedIn connections._")
    out.append("")
    for w in r.warnings:
        out += [f"> ⚠️ {w}", ""]
    out += [
        "| 1st-degree at company | Senior / hiring influence | Recruiting | 2nd-degree targets with a warm path | Bridges |",
        "|---|---|---|---|---|",
        f"| {len(confirmed)} (+{len(possible)} to verify) | {senior} | {talent} | "
        f"{len(best_paths) if r.had_second_degree else 'n/a - see §2'} | {len(r.bridges)} |",
        "",
    ]

    # 1. First-degree
    out += [f"## 1. Your 1st-degree connections at {r.company}", ""]
    if not confirmed:
        out += [f"No connections list {r.company} (or a known subsidiary) as their current company.", ""]
    else:
        out += ["| # | Name | Role | Listed company | Connected | Why they rank here | Score |", "|---|---|---|---|---|---|---|"]
        for i, s in enumerate(confirmed, 1):
            c = s.person
            out.append(
                f"| {i} | {_link(c.name, c.url)} | {_cell(c.position)} | {_cell(c.company)} | {_since(s)} | "
                f"{_cell('; '.join(s.reasons))} | {s.score} |"
            )
        out.append("")
    if possible:
        out += ["**Possible matches - verify** (company name contains the target but isn't a known subsidiary):", ""]
        out += [f"- {_link(s.person.name, s.person.url)} - {_cell(s.person.position)} @ {_cell(s.person.company)}" for s in possible]
        out.append("")

    # 2. Second-degree
    out += ["## 2. Best 2nd-degree paths (warm introductions)", ""]
    if r.had_second_degree:
        if best_paths:
            out += ["| # | Target | Their role | Best path via | Also via | Path score | Why this connector |", "|---|---|---|---|---|---|---|"]
            for i, p in enumerate(best_paths, 1):
                alts = [q.connector.person.name for q in r.paths if q.target.name == p.target.name and q is not p]
                out.append(
                    f"| {i} | {_link(p.target.name, p.target.url)} | {_cell(p.target.title)} | "
                    f"{_link(p.connector.person.name, p.connector.person.url)} ({_cell(p.connector.person.position)}) | "
                    f"{_cell(', '.join(alts[:3])) or '-'} | {p.score} | {_cell('; '.join(p.connector.reasons))} |"
                )
            out.append("")
        if r.orphans:
            out += ["**No resolvable mutual connection** (names didn't match your export - check spelling):", ""]
            out += [f"- {_cell(t.name)} - listed mutuals: {_cell(', '.join(u)) or 'none'}" for t, u in r.orphans]
            out.append("")
    else:
        out += [
            "LinkedIn's export only contains your 1st-degree network, so exact 2nd-degree paths need one extra input.",
            f"Open [this LinkedIn search]({search_url(r.company)}) (2nd-degree people matching \"{r.company}\"; "
            "add the *Current company* filter for precision), then copy each person's name, title and the "
            "\"X, Y and N other mutual connections\" line into `data/second_degree_<company>.csv` "
            "(format: `data/second_degree.example.csv`) and re-run with `--second-degree`.",
            "",
            "Until then, the bridges below are your best warm routes in.",
            "",
        ]

    out += ["### Inferred bridges", ""]
    if r.bridges:
        out += ["| # | Name | Role @ company | Why they can bridge | Connected |", "|---|---|---|---|---|"]
        for i, (s, why) in enumerate(r.bridges, 1):
            out.append(
                f"| {i} | {_link(s.person.name, s.person.url)} | {_cell(s.person.position)} @ {_cell(s.person.company)} | "
                f"{_cell(why)} | {_since(s)} |"
            )
        out.append("")
    else:
        out += ["No sister-company, alumni, or insider bridges found.", ""]

    # 3. Outreach
    out += ["## 3. Outreach drafts", ""]
    if not r.profile_is_real:
        out += ["> Fill in `config/profile.json` (copy `config/profile.example.json`) to replace the `[placeholders]` below.", ""]
    out += ["Drafts are starting points - read each one and add a specific detail before sending.", ""]
    if confirmed:
        out += [f"### Direct asks (top {min(top, len(confirmed))} insiders)", ""]
        for s in confirmed[:top]:
            out += [f"#### {s.person.name} - {s.person.position}", "", "```text", insider_message(s, r.company, r.profile, templates_dir), "```", ""]
    if best_paths:
        out += [f"### Intro requests (top {min(top, len(best_paths))} paths)", ""]
        for p in best_paths[:top]:
            req, note = path_messages(p, r.company, r.profile, templates_dir)
            out += [
                f"#### {p.target.name} via {p.connector.person.name}", "",
                f"**1) To {p.connector.person.first} (intro request):**", "", "```text", req, "```", "",
                f"**2) LinkedIn connect note to {p.target.name.split()[0]} after the intro ({len(note)}/300 chars):**", "",
                "```text", note, "```", "",
            ]
    if r.bridges:
        out += [f"### Bridge asks (top {min(3, len(r.bridges))})", ""]
        for s, why in r.bridges[:3]:
            out += [f"#### {s.person.name} - {why}", "", "```text", bridge_message(s, r.company, why, r.profile, templates_dir), "```", ""]
    return "\n".join(out)


def write_csv(r: Result, path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["type", "rank", "name", "company", "position", "url", "email", "connected_on", "score", "via", "reasons"])
        for i, s in enumerate(r.insiders, 1):
            c = s.person
            kind = "1st-degree (verify)" if s.match == NAME_MATCH else "1st-degree"
            w.writerow([kind, i, c.name, c.company, c.position, c.url, c.email, c.connected_on or "", s.score, "", "; ".join(s.reasons)])
        for i, p in enumerate(r.paths, 1):
            t, c = p.target, p.connector.person
            w.writerow(["2nd-degree path", i, t.name, t.company, t.title, t.url, "", "", p.score, c.name, "; ".join(p.connector.reasons)])
        for i, (s, why) in enumerate(r.bridges, 1):
            c = s.person
            w.writerow(["bridge", i, c.name, c.company, c.position, c.url, c.email, c.connected_on or "", s.score, "", why])
