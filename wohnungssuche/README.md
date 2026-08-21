# Wohnungssuche Wiesbaden

An agent-based apartment search for Wiesbaden: scrapes the big German rental
portals, normalises what it finds, flags scam adverts, filters against a fixed
set of criteria and produces a daily HTML report with **real, clickable links
and real listing photos**.

It never contacts a landlord. Matches land in an approval queue; sending the
enquiry stays a manual step you perform yourself.

## Criteria

| Kriterium | Wert |
|---|---|
| Stadt / Umkreis | Wiesbaden, max. 4 km vom Zentrum (50.0826, 8.2400) |
| Zimmer | mind. 3 |
| Wohnfläche | mind. 70 m² |
| Warmmiete | max. 1.600 € |
| Küche | keine Kochnische / Miniküche / Pantry / Singleküche |
| Stellplatz | nice-to-have, wird nur markiert |
| Ausgeschlossene Stadtteile | Erbenheim, Mainz-Kastel, Kastel |
| Ausgeschlossene Angebote | WG-Zimmer, Untermiete, Zwischenmiete, Wohnen auf Zeit |
| Mieter | Paar, Nichtraucher, keine Haustiere |

Everything above lives in `wohnungssuche/config.py` and can be overridden with
a JSON file (`--config example-config.json`).

## Install

```bash
cd wohnungssuche
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Use

```bash
# Full pipeline against the bundled HTML fixtures - no network at all
python run.py run --mock

# Live run (respects robots.txt, 4-5 s between requests)
python run.py run

# Only one portal, two result pages, no expose detail pages
python run.py run --platforms is24 --pages 2 --no-details

# What is waiting for your decision?
python run.py queue

# Record YOUR decision (this sends nothing)
python run.py approve <hash> --note "Besichtigung anfragen"
python run.py reject  <hash> --note "zu laut"

# Print an enquiry draft to copy into the portal yourself
python run.py draft <hash>

python run.py history            # past runs
python run.py schedule --at 07:30  # daily loop; also prints the crontab line
```

The report is written to `reports/wohnungssuche_<date>.html` (plus a stable
`reports/latest.html` and a JSON snapshot). Open it in any browser - it is
self-contained apart from `reports/static/style.css`, which is copied next to it.

### Daily runs via cron

```
30 7 * * *  cd /path/to/wohnungssuche && /path/to/.venv/bin/python -m wohnungssuche.main run >> reports/cron.log 2>&1
```

## Safety rules baked in

- **No automatic contact.** There is no mail client, no form submission, no
  POST anywhere in the package - `tests/test_pipeline.py` asserts this.
- **Approval queue.** Matches are stored as `pending`. `approve` only records a
  decision; `draft` only prints text.
- **Scam detection.** Western Union / crypto, Vorkasse, landlord "abroad", keys
  by post, urgency pressure, ID copies upfront, implausible prices and
  inconsistent figures. Flagged adverts get their own report section and never
  appear among the matches.
- **Live viewing first.** Every report repeats it: view the flat in person, and
  never transfer money before the viewing.
- **Politeness.** robots.txt is honoured (an unreachable robots.txt counts as
  "do not crawl"), 4-5 s of jittered delay between requests, rotating
  User-Agent, exponential backoff (2/4/8 s), a page cap per portal and a cap on
  expose detail fetches.

## Discovery sources

Scraping the portals directly is fragile: IS24 sits behind active bot
protection and robots.txt disallows the search paths (which this tool honours
rather than evades). Two scraping-free sources fix that:

- **`email`** - the portals' own Suchagent alert mails, read via IMAP. Save a
  search on [IS24](https://www.immobilienscout24.de/suchende.html),
  [Immowelt](https://www.immowelt.de/suchauftrag/anlegen) and Kleinanzeigen,
  let them mail every new listing, and configure:

  ```json
  { "platforms": ["email"],
    "imap_host": "imap.gmail.com", "imap_user": "you@example.com" }
  ```

  The password is read from the environment variable named by
  `imap_password_env` (default `WOHNUNGSSUCHE_IMAP_PASSWORD`) - it is never
  stored in a file. Listings get their real portal (`is24`/`immowelt`/
  `kleinanzeigen`) so cross-source de-duplication just works.

- **`fredy`** - imports from a local [Fredy](https://github.com/orangecoding/fredy)
  installation, which watches 17 German portals (including IS24 via their
  mobile API) and stores everything in `db/listings.db`. Point
  `fredy_db_path` at that file; it is opened strictly read-only (SQLite WAL
  allows this while Fredy runs). Fredy stores one price per listing (usually
  the Kaltmiete), so warm rents from this source are estimates and marked as
  such.

  ```json
  { "platforms": ["fredy"], "fredy_db_path": "/opt/fredy/db/listings.db" }
  ```

Sources and portal scrapers mix freely: `--platforms is24 email fredy`. Both
sources feed the identical validation → filter → link-check → report pipeline.

## Architecture

```
Orchestrator                     state, persistence, approval queue
  ├── DiscoveryAgent    → fetches search-result pages per portal
  ├── ExtractionAgent   → parses raw HTML into ApartmentListing, de-duplicates
  ├── ValidationAgent   → scam indicators + plausibility
  ├── EnrichmentAgent   → expose details, district, coordinates, distance
  ├── FilterAgent       → hard criteria, records why anything was dropped
  ├── LinkCheckAgent    → HEAD-checks match URLs, flags offline exposes
  └── ReportingAgent    → Jinja2 HTML report + JSON snapshot
```

Agents exchange `AgentMessage` envelopes. Each one logs start, duration and
outcome, and converts an exception into an error on the envelope, so a failing
portal degrades the run instead of ending it - the report shows per-platform
status.

```
wohnungssuche/
├── config.py         search criteria
├── models.py         dataclasses (+ URL/image guards)
├── parsing.py        German number, price, room, area and feature parsing
├── geo.py            haversine, Wiesbaden district table, Nominatim fallback
├── filters.py        criteria engine
├── validation.py     scam detection
├── storage.py        SQLite: listings, runs, approval queue
├── reporting.py      Jinja2 rendering
├── main.py           CLI
├── scrapers/         base + card parser + is24/immowelt/kleinanzeigen + mock
├── sources/          scraping-free discovery: Suchagent mails (IMAP), Fredy DB
├── templates/        report.html, anfrage.txt
├── static/style.css  all styling, never inlined in Python
└── fixtures/         saved-shape HTML used by the mock scraper and the tests
```

### Mock vs. live

The transport is injected. `HttpFetcher` talks to the portals, `FixtureFetcher`
serves the HTML files in `wohnungssuche/fixtures/`. **The same parsers run in
both cases**, so `--mock` exercises the production code path rather than a
parallel fake one, and switching to live data changes nothing but the fetcher.

## Tests

```bash
python -m unittest discover -s tests -t . -v
```

126 tests, no network required: parsing, geo, filters, scam detection, storage,
report rendering (including HTML escaping and the "no fake links" guarantee)
and a full pipeline run including a deliberately broken portal.

## Adding a portal

Subclass `ResultCardScraper`, declare selectors and query parameters (see
`scrapers/immowelt.py` - it is ~40 lines), register it in
`agents/orchestrator.py::SCRAPER_CLASSES`, and drop a saved result page into
`fixtures/` so the parser is covered by tests.

## Known limitations

- **Portal access is not guaranteed.** The portals' robots.txt may disallow
  their search paths, and they use bot protection and JavaScript rendering. The
  scraper honours robots.txt and reports a platform as failed rather than
  working around a block. If a portal cannot be crawled politely, use its
  official search alerts, or point the parsers at a page you saved yourself.
  There is no evasion code here on purpose.
- Portal markup changes regularly. Selectors are layered (specific → generic →
  "any link to an expose"), but a redesign will eventually need new selectors;
  the fixtures make that a small, testable change.
- **`--mock` produces demo data.** The bundled fixtures are hand-written in
  the shape of real result pages, but their listing IDs, links and image paths
  are synthetic - the links 404 on purpose. Demo reports carry a banner saying
  exactly that, the JSON snapshot has `"demo": true`, and the CLI prints a
  warning. Only a run **without** `--mock` produces clickable real listings.
- In live runs the LinkCheckAgent HEAD-checks every match before reporting:
  reachable exposes get a "Link geprüft" badge, 404/410 gets "Inserat
  offline?" plus a warning (listings are often taken down within hours), and
  an inconclusive answer (bot protection, robots.txt) claims nothing.
- Warm rent is estimated (cold rent × 1.25) when a listing publishes only the
  cold rent. Such listings are marked "geschätzt" in the report and in the
  criteria check.
- Coordinates come from a district centroid table (offline). Nominatim is only
  queried for addresses that cannot be resolved locally, rate-limited to one
  request per second per their usage policy.
