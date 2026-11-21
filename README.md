# Lobby Ledger NY

A public site that links New York campaign finance and lobbying records, so anyone can click an official, an organization, or a bill and see the money and lobbying around it. City and State are separate tabs. The data rebuilds automatically once a month.

## What's in this repo

| Path | What it does |
| --- | --- |
| `config/sources.yml` | Every dataset used, and which columns the pipeline reads from each |
| `config/settings.yml` | Start year (2019), donor threshold ($2,500), matching sensitivity |
| `config/entity_overrides.csv` | Manual fixes to name matching (see below) |
| `pipeline/` | Downloads the data, matches names, standardizes bills, writes `site/data/*.json` |
| `site/` | The website: plain HTML, CSS and JavaScript, no build step |
| `.github/workflows/update.yml` | Monthly rebuild and publish to GitHub Pages |
| `data/manual/` | Files you add by hand (City super PAC data, see below) |
| `data/review/` | Written by each build: audit report and names to review |
| `data/cache/bill_titles_city.json`, `bill_titles_state.json` | Bill names already looked up, so each month only fetches new bills |

## First-time setup (about 30 minutes)

1. Create a GitHub repository and upload everything in this folder.
2. In the repository: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. Add these free keys under **Settings → Secrets and variables → Actions**:
   - `NYSENATE_API_KEY` from <https://legislation.nysenate.gov/public> (State bill names and links).
   - `LEGISTAR_TOKEN` from the form at <https://council.nyc.gov/legislation/api> (City bill names and links). The Council emails the token, so request it early.
   - `SOCRATA_APP_TOKEN` from <https://data.cityofnewyork.us/profile/edit/developer_settings> (optional; faster, less rate-limited downloads).

   Without the first two, bills show numbers only and the site shows a coverage note.
4. Go to **Actions → Monthly data update → Run workflow**.
5. When it finishes, open `data/review/audit_report.md` in the repo. This is the real-data audit. Check three numbers before sharing the site:
   - **Lobbying clients that also appear as donors.** This is how often the tool can connect lobbying and money for the same organization.
   - **Council-member targets linked to a named official.** Should be above 90%.
   - **Bill-type lobbying rows parsed into bill IDs.** Should be above 90%.
6. If the build fails with "required fields not found", a dataset's column names differ from what `config/sources.yml` expects. The audit report lists the actual columns; add the right name to that field's `candidates` list.

Rename the site, its tagline, the credit line or the corrections address in `site/config.js`.

The site is then live at `https://<your-org>.github.io/<repo-name>/`.

## Running locally

```bash
pip install -r requirements.txt
python -m pipeline.audit                 # measure match rates on live data
python -m pipeline.run --out site/data   # build the data (can take 30+ minutes)
cd site && python -m http.server 8000    # open http://localhost:8000
```

Offline demo with invented data:

```bash
python tests/make_fixtures.py
python -m pipeline.run --fixtures tests/fixtures --out site/data
```

## How the automatic updates work

- The workflow runs **daily**. The data itself is refreshed **once a month**: on the first run of a new month, each dataset starts a fresh download.
- Large downloads (mainly State contributions and lobbying) can take longer than one GitHub job allows. Each run downloads for up to 5 hours, saves its progress, and the next day's run continues where it stopped.
- Until a new month's download finishes, the site keeps using the previous month's data. The very first time, a tab that hasn't finished downloading shows an "on its way" note.
- Saved downloads live in the GitHub Actions cache (`data/raw`, not in the repo). If the cache is ever cleared, the next runs simply download everything again.
- The audit runs on the 5th of each month and whenever you start the workflow by hand.

## Monthly upkeep (about 1 hour)

1. **Read the warnings** at the top of the site and in `site/data/manifest.json`.
2. **Review name matches.** Open `data/review/city_entity_review.csv` and `state_entity_review.csv`. Each row is a pair of names that look similar but weren't merged automatically. For pairs that are the same organization, add a `merge` row to `config/entity_overrides.csv`:

   ```csv
   alias,canonical,action,note
   "Uber Technologies Inc","Uber Technologies, Inc.",merge,confirmed same company
   "Empire State Realty LLC","Empire State Realty Trust Inc",split,different organizations
   ```

   Use `split` to stop two names from ever being merged.
3. **Update City super PAC files** (next section).
4. **Handle corrections** sent to the address in `site/config.js`, usually with an override row.

## City super PAC (independent expenditure) data

The NYC contributions file includes gifts to independent-expenditure committees (super PACs), so super PAC pages and their organization donors appear automatically. What it doesn't include is which candidates each super PAC spent money supporting or opposing. That comes from the Campaign Finance Board's Follow the Money portal: <https://www.nyccfb.info/follow-the-money/follow-the-money/>.

To link super PACs to candidates, export the spending data and save it as `data/manual/city_ie_expenditures.csv` with columns `spender, candidate, support_oppose, amount, date, source_url` (template in the same folder). Until then, officials' pages don't list super PAC donors, and the site shows a coverage note.

Optional: `data/manual/city_ie_contributions.csv` (`spender, contributor, amount, date, source_url`) adds individual donors to super PACs, which the automatic download leaves out.

## How the data is shaped

- **Organizations only.** Individuals are excluded except as donors to super PACs. City law bars corporations, LLCs and partnerships from giving to City candidates, so City donor lists are mostly PACs and unions.
- **$2,500 threshold** applies to an organization's total giving to one official across the years the visitor selects, so it respects the year filter. City per-election limits are below $2,500.
- **Organizations and their PACs** ("Empire Gaming Coalition" and "Empire Gaming Coalition PAC") are linked as affiliates, not merged. The parent's page includes the PAC's giving, labeled.
- **Bills** are standardized to one ID per bill per session. State amendment letters (S1464A) roll up to the base bill. City Intro numbers restart each Council session, so the session is part of the ID; update `council_sessions` in `config/sources.yml` when a new session starts.
- **State bill–official pairs** come from the filing rows, so a bill only appears next to the officials it was lobbied with. City filings list bills and targets separately, so City pages show all bills in a filing next to all officials named in it.
- **Bill names** come from the NYS Senate Open Legislation API and the NYC Council Legistar API, and each bill page links to the official bill record.
- **Charts** are drawn in the browser from the same data as the tables, so they follow the year filter. The home page shows money and lobbying by year, the top givers, and the most-lobbied bills; each official, organization and bill page has its own year charts; each connection page has a timeline of contributions, super PAC spending and lobbying contacts.
- **Positions** (support/oppose) appear only when the filer wrote one into the filing. Neither the City nor the State requires it.

## Known gaps

- City super PAC data requires the manual step above.
- Column names for three datasets were taken from documentation and couldn't be checked against live data during development: the City lobbyist fundraising reports (`7arw-dbem`), the Doing Business summary (`fbkk-n4e3`), and the State contribution office/candidate fields. The first audit run confirms or flags them.
- The State contributions dataset includes county and local candidates. It's filtered to State offices when an office column exists; otherwise committees are kept only when their name matches a State official found in lobbying filings.
- The State super PAC link (committee → candidate it spent on) depends on a candidate column in the disclosure data. If the audit reports it missing, State super PAC donors appear on committee pages but not on officials' pages.
- Agencies update on their own schedules. The NYC contributions dataset, for example, can go months between updates, so a monthly rebuild doesn't guarantee new City money data.

## Tests

```bash
python -m pytest -q tests
```
