# data/ (gitignored)

Private inputs live here and are **never committed** - this repo is public.

| File | Required | What it is |
|---|---|---|
| `Connections.csv` | yes | LinkedIn export: Settings → Data privacy → Get a copy of your data → Connections |
| `second_degree_<company>.csv` | no | 2nd-degree people you collected from LinkedIn search, with their mutual connections. Format: `second_degree.example.csv` |
| `notes.csv` | no | Personal shared history per connection, used as the opening line of drafts. Format: `notes.example.csv` (match by `Name` or `URL`) |
