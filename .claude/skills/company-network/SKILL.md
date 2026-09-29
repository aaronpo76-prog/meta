---
name: company-network
description: Find warm paths into a target company from the user's LinkedIn connections export - 1st-degree connections there, best 2nd-degree intro paths, and personalized outreach drafts. Use when the user names a company and wants to network, get a referral, or find an intro (e.g. "/company-network Stripe", "who do I know at Figma?").
---

# Company network workflow

Arguments: the target company name (e.g. `Stripe`). Optionally a path to a 2nd-degree CSV.

## 1. Preflight

- `data/Connections.csv` must exist. If it doesn't, ask the user to upload their LinkedIn export
  (Settings → Data privacy → Get a copy of your data → Connections) and copy it there.
  **Never commit anything under `data/` or `reports/` - this repo is public and those files hold other people's personal data.** `.gitignore` already covers them; don't override it.
- If `config/profile.json` is missing, ask the user for: name, one-line headline, what they're looking for,
  2-5 function keywords (e.g. brand, design), and past employers. Write it (it is gitignored).
  If they'd rather skip, run anyway - drafts will contain `[placeholders]`.
- If `data/notes.csv` exists it adds personal shared-history lines (format: `data/notes.example.csv`).

## 2. Run

```bash
python3 network.py "<Company>"                                  # 1st-degree + inferred bridges
python3 network.py "<Company>" --second-degree data/second_degree_<slug>.csv   # + exact intro paths
```

Outputs `reports/<slug>-<date>.md` (ranked tables + drafts) and a matching `.csv`.

If the company is a subsidiary/brand that isn't matching (e.g. results look thin), check
`config/company_aliases.json` and add a group - `members` count as the same employer,
`related` become bridges. Re-run after editing.

## 3. Review and present

Read the Markdown report, then give the user:

1. **1st-degree** - the top ~5 with one line each on why (role, hiring influence, relationship length).
   Call out any rows under "Possible matches - verify".
2. **2nd-degree** - if a `--second-degree` file was used, the top paths (target ← connector) and why that
   connector is the best one. If not, explain that LinkedIn's export has no 2nd-degree data, give them the
   search link from the report, and offer to turn what they paste (names, titles, "mutual connections" lines)
   into `data/second_degree_<slug>.csv` and re-run.
3. **Outreach** - the drafts for the top 3 people. Tighten them, but **only use shared history that comes from
   the data** (connection date, shared employer, notes.csv, or what the user tells you). Never invent
   past collaboration. Ask the user for one specific detail per person if the hook is generic.

Keep the full tables in the report file; link to it rather than pasting everything.
