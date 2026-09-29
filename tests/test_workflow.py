import tempfile
import unittest
from datetime import date
from pathlib import Path

import network
from warmpath.data import load_connections, normalize_name
from warmpath.match import DIRECT, FAMILY, NAME_MATCH, RELATED, CompanyMatcher, normalize_company
from warmpath.report import render_markdown
from warmpath.score import seniority
from warmpath.workflow import run

ROOT = Path(__file__).resolve().parents[1]
FX = ROOT / "tests" / "fixtures"
ALIASES = ROOT / "config" / "company_aliases.json"
TODAY = date(2026, 9, 29)


def _run(company="Block", **kw):
    return run(company, FX / "connections_sample.csv", FX / "profile.json", ALIASES,
               kw.get("second"), kw.get("notes", FX / "notes.csv"), TODAY)


class LoaderTests(unittest.TestCase):
    def test_skips_preamble_and_blank_rows(self):
        people = load_connections(FX / "connections_sample.csv")
        self.assertEqual(len(people), 9)
        self.assertEqual(people[0].connected_on, date(2012, 3, 12))

    def test_normalize_name(self):
        self.assertEqual(normalize_name("José Núñez, MBA"), "jose nunez")


class MatchTests(unittest.TestCase):
    def test_classification(self):
        m = CompanyMatcher("Block", ALIASES)
        self.assertEqual(m.classify("Block, Inc."), DIRECT)
        self.assertEqual(m.classify("Square"), FAMILY)
        self.assertEqual(m.classify("Block Party Events"), NAME_MATCH)
        self.assertIsNone(m.classify("Metalab"))

    def test_word_boundary(self):
        self.assertIsNone(CompanyMatcher("Meta", ALIASES).classify("Metalab"))
        self.assertEqual(CompanyMatcher("Square", ALIASES).classify("Afterpay"), RELATED)

    def test_alumni(self):
        self.assertTrue(CompanyMatcher("Square", ALIASES).alumni_mention("Designer, ex-Square"))

    def test_normalize_company(self):
        self.assertEqual(normalize_company("DEPT®"), "dept")
        self.assertEqual(normalize_company("The Walt Disney Company"), "walt disney")

    def test_seniority(self):
        self.assertGreater(seniority("Head of Design"), seniority("Senior Designer"))


class WorkflowTests(unittest.TestCase):
    def test_insiders_ranked_and_scoped(self):
        r = _run()
        names = [s.person.name for s in r.insiders]
        self.assertEqual(names[0], "Pat Sample")  # note + seniority + function + 14y
        self.assertIn("Riley Recruiter", names)
        self.assertNotIn("Morgan Metalab", names)
        verify = [s.person.name for s in r.insiders if s.match == NAME_MATCH]
        self.assertEqual(verify, ["Sam Blockparty"])

    def test_bridges_for_subsidiary_target(self):
        r = _run("Square")
        why = {s.person.name: w for s, w in r.bridges}
        self.assertIn("sister/partner company", why["Taylor Sister"])
        self.assertIn("past time", why["Jamie Alum"])

    def test_second_degree_paths(self):
        r = _run(second=FX / "second_degree_sample.csv")
        best = {}
        for p in r.paths:
            best.setdefault(p.target.name, p.connector.person.name)
        self.assertEqual(best["Jordan Target"], "Pat Sample")  # insider beats outside connector
        self.assertEqual(best["Lee Target"], "José Núñez")  # accent-insensitive resolution
        self.assertEqual([t.name for t, _ in r.orphans], ["Unknown Person"])

    def test_messages_personalized(self):
        md = render_markdown(_run(second=FX / "second_degree_sample.csv"), ROOT / "templates", top=5)
        self.assertIn("We shipped the 2019 rebrand together.", md)
        self.assertIn("since our Acme Studio days", md)  # shared employer for Casey
        self.assertIn("Alex Rivera", md)
        self.assertNotIn("${", md)
        for block in md.split("LinkedIn connect note")[1:]:
            note = block.split("```text\n")[1].split("\n```")[0]
            self.assertLessEqual(len(note), 300)

    def test_cli_writes_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            rc = network.main(["Block", "--connections", str(FX / "connections_sample.csv"),
                               "--profile", str(FX / "profile.json"), "--out", d, "--today", "2026-09-29"])
            self.assertEqual(rc, 0)
            self.assertTrue((Path(d) / "block-2026-09-29.md").exists())
            self.assertTrue((Path(d) / "block-2026-09-29.csv").exists())


if __name__ == "__main__":
    unittest.main()
