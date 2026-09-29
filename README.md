# warmpath - LinkedIn networking workflow

Give it a target company. You get back:

1. **Your 1st-degree connections there**, ranked by how useful and how warm they are (hiring influence, recruiters, same function as you, how long you've been connected, shared employers, your personal notes).
2. **The best 2nd-degree paths**: for each person you want to reach, the connection best placed to introduce you, plus *bridges* (sister-company contacts, alumni, and your warmest insiders who can point you to the right team).
3. **Personalized outreach drafts**: direct asks, recruiter notes, intro requests with a blurb your connector can forward, LinkedIn connect notes that fit the 300-character limit, and bridge asks. Each one opens with a line based on your real shared history.

Only the Python 3.10+ standard library. No API keys, no scraping.

## Setup (once)

1. Export your connections from LinkedIn (Settings → Data privacy → Get a copy of your data → **Connections**) and save the file as `data/Connections.csv`.
2. `cp config/profile.example.json config/profile.json` and fill it in. `functions` are keywords for the kind of work you want (e.g. `brand`, `design`). `past_companies` turns on shared-employer hooks.
3. Optional: add `data/notes.csv` with one line of real shared history per person ("We shipped the 2019 rebrand together").

`data/`, `reports/` and `config/profile.json` are gitignored. **This repo is public, so keep them out of git.**

## Run it for any company

```bash
python3 network.py "Stripe"
```

Writes `reports/stripe-YYYY-MM-DD.md` (ranked tables and drafts) and `reports/stripe-YYYY-MM-DD.csv` (every row, for a spreadsheet or CRM).

In Claude Code you can run **`/company-network Stripe`** instead. The skill runs the script, reviews the results and tightens the drafts with you.

### Getting exact 2nd-degree paths

LinkedIn's export only includes your own connections, so it can't show who *they* know. To get real intro paths:

1. Open the LinkedIn search link in the report (2nd-degree people at the company).
2. For the people you want to reach, copy their name, title and the "*X, Y and N other mutual connections*" line into `data/second_degree_stripe.csv`. The format is in `data/second_degree.example.csv`.
3. Run `python3 network.py "Stripe" --second-degree data/second_degree_stripe.csv`

Each mutual is matched against your export (accents and suffixes like ", MBA" are ignored), and paths are ranked by:
- **Connector strength**: whether they work inside the company, your personal notes, a shared employer, how long you've been connected, whether you have their email, and their seniority.
- **Target relevance**: the target's seniority, whether they're in your function, and whether they're a recruiter.

### Company matching

`config/company_aliases.json` maps each company to its subsidiaries and brands, which count as the same employer (e.g. Block ⇄ Square/Cash App/Afterpay, Meta ⇄ Instagram/WhatsApp, Amazon ⇄ AWS/Audible). It also lists related companies, whose people become *bridges* (e.g. Google → Waymo/Verily). Matching uses whole words, so `Meta` never matches `Metalab`. If a company name only *contains* the target, that person is listed under "Possible matches - verify". Add groups as needed.

### Customizing messages

Edit the files in `templates/`. They use `${placeholders}` and are filled in with the opening line and the details from your profile. Drafts are starting points: add one specific detail before you send.

## Options

```
--second-degree PATH   2nd-degree people + mutual connections CSV
--notes PATH           shared-history notes (default: data/notes.csv if present)
--profile PATH         default: config/profile.json
--connections PATH     default: data/Connections.csv
--top N                drafts per section (default 5)
--out DIR              default: reports/
```

## Tests

```bash
python3 -m unittest
```
