# GreenCheck

A greenwashing-intelligence pipeline: scrapes product data from a
Shopify store, scores each product's sustainability marketing claims
on an **Intensity vs. Verification Confidence** framework, and stores
everything in a database — SQLite by default (zero setup), MySQL if
you switch to it later.

This version was built step-by-step, testing each piece against real
live data before formalizing it into reusable files — so every design
choice below has a reason you've already seen play out.

## How it works

```
Shopify /products.json  --->  scraper/store_scraper.py
                                      |
                                      v
                            db/db_utils.py (SQLite/MySQL)
                                      |
                                      v
                            scoring/scorer.py
                                      |
                                      v
                       v_product_scores (SQL view)
```

**The scoring framework:**
- **Intensity** — how strong/absolute the claim's language is
  ("100% recycled" vs. "partially recycled")
- **Verification Confidence** — how much real evidence backs it
  (recognized certifications like GOTS, Fair Trade, B Corp; specific
  checkable numbers)
- **Greenwash Risk** = Intensity × (1 − Verification Confidence / 100)
  — a bold, unproven claim scores high risk; a bold, well-certified
  claim scores low risk.

## A design decision worth knowing about: target store

**EarthHero.com sits behind Cloudflare's bot-protection (Turnstile
challenge)**, which blocks automated requests — even `cloudscraper`
couldn't get past it, since Turnstile specifically detects that kind
of tool. Rather than fight an anti-bot arms race, this project targets
**greenarys.com** instead (also a real, live Shopify eco-store, with
no such protection), configurable via `TARGET_STORE_BASE_URL` in
`.env`. All the code is store-agnostic — pointing it at any other
Shopify store (protected or not) is just a URL change.

If you want to revisit EarthHero later, the honest options are: a
browser-automation tool like Playwright (drives real Chrome, so the
challenge resolves naturally), or simply picking a different,
unprotected store — which is what we did here.

## Setup

```bash
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt

cp .env.example .env             # defaults already work — SQLite needs no editing

python main.py                   # full pipeline: scrape -> store -> score
python main.py --show-top        # print highest-risk scored products
```

No database server, no password, no `CREATE DATABASE` step — the
SQLite file (`greencheck.db`) and all its tables are created
automatically the first time `main.py` runs.

## Testing without hitting the network

`tests/test_scorer.py` exercises the scoring engine on real claim text
you already validated by hand — including a regression test that locks
in the exact result you got in your notebook (intensity 66,
verification 0, risk 66.0) for the Greenarys seed pencil claim:

```bash
python tests/test_scorer.py
# or: python -m pytest tests/test_scorer.py -v
```

## Switching to MySQL later

Change one line in `.env`:
```
DATABASE_URL=mysql+mysqlconnector://user:password@localhost:3306/greencheck
```
then `pip install mysql-connector-python`. Nothing else in the code
changes — `db_utils.py` was written against SQLAlchemy specifically so
this swap is trivial once you're ready to set up a MySQL server.

## Project layout

```
greencheck-v2/
├── config/settings.py       # env-driven configuration
├── scraper/store_scraper.py # Shopify /products.json scraper, any store
├── db/schema.sql            # table + view definitions
├── db/db_utils.py           # SQLAlchemy data-access layer (upsert-safe)
├── scoring/scorer.py        # Intensity / Verification / Risk scoring
├── tests/test_scorer.py     # unit tests, incl. regression test
├── main.py                  # CLI pipeline orchestrator
├── requirements.txt
└── .env.example
```

## What each design choice fixes (things we hit and fixed live)

- **`shopify_id` is `UNIQUE`** — without this, re-running the pipeline
  creates duplicate rows for the same product every time (this
  happened during development — confirmed and fixed).
- **`if not claim_text: skip`** — some products (like a store's
  internal "Partial Payment" utility product) have `body_html: null`.
  Scoring empty text as a real claim would be meaningless.
- **`html.parser` instead of `lxml`** for BeautifulSoup — `lxml` needs
  a C compiler to install on some Windows setups; `html.parser` is
  built into Python and needs nothing extra.
- **`?` placeholders / SQLAlchemy `text()` params, never f-strings**
  in SQL — protects against SQL injection from scraped text you don't
  control.
