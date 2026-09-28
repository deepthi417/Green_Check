"""GreenCheck dashboard: greenwashing risk for scraped product claims.

Read-only view over greencheck.db (SQLite). Run the scraper/scorer locally
(python main.py), commit the updated greencheck.db, and the deployed app
will show the latest run.
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "greencheck.db"
BAND_ORDER = ["low", "moderate", "high", "severe"]
BAND_ICON = {"low": "🟢", "moderate": "🟡", "high": "🟠", "severe": "🔴"}

st.set_page_config(page_title="GreenCheck", page_icon="🌿", layout="wide")


def pretty_terms(value) -> str:
    """matched_* columns may be JSON lists or plain text; show them as a clean string."""
    if value is None or value == "":
        return "none"
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return ", ".join(map(str, parsed)) if parsed else "none"
    except (TypeError, ValueError):
        pass
    return str(value)


@st.cache_data(show_spinner=False)
def load_data(db_mtime: float):
    """db_mtime is only used so the cache refreshes when the DB file changes."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(
            """
            SELECT p.title, p.price, p.url,
                   s.intensity_score, s.verification_confidence,
                   s.greenwash_risk_score, s.risk_band,
                   s.matched_certifications, s.matched_vague_terms,
                   c.claim_text, c.run_id
            FROM scores s
            JOIN claims c   ON c.claim_id   = s.claim_id
            JOIN products p ON p.product_id = s.product_id
            WHERE c.run_id = (SELECT MAX(run_id) FROM claims)
            ORDER BY s.greenwash_risk_score DESC
            """,
            conn,
        )
        run = conn.execute(
            "SELECT run_id, finished_at FROM scrape_runs ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return df, run


st.title("🌿 GreenCheck")
st.caption("Greenwashing risk scoring for product marketing claims")

if not DB_PATH.exists():
    st.error("greencheck.db not found. Run `python main.py` first and commit the database.")
    st.stop()

df, run = load_data(DB_PATH.stat().st_mtime)

if df.empty:
    st.warning("The database has no scored claims yet.")
    st.stop()

if run:
    st.caption(f"Showing scrape run {run[0]}" + (f" · finished {run[1]}" if run[1] else ""))

# ---- Sidebar filters ----
st.sidebar.header("Filters")
bands_present = [b for b in BAND_ORDER if b in set(df["risk_band"])] or sorted(df["risk_band"].unique())
selected_bands = st.sidebar.multiselect("Risk band", bands_present, default=bands_present)
min_risk = st.sidebar.slider("Minimum risk score", 0, 100, 0)
search = st.sidebar.text_input("Search product name")

view = df[df["risk_band"].isin(selected_bands) & (df["greenwash_risk_score"] >= min_risk)]
if search:
    view = view[view["title"].str.contains(search, case=False, na=False)]

# ---- Summary metrics ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Products scored", len(df))
c2.metric("Average risk", f"{df['greenwash_risk_score'].mean():.1f}")
c3.metric("Severe / high", int(df["risk_band"].isin(["severe", "high"]).sum()))
c4.metric("With any verification", int((df["verification_confidence"] > 0).sum()))

# ---- Band distribution ----
st.subheader("Risk band distribution")
counts = df["risk_band"].value_counts().reindex(bands_present, fill_value=0)
st.bar_chart(counts)

# ---- Ranked table ----
st.subheader(f"Ranked products ({len(view)})")
table = view[["title", "risk_band", "greenwash_risk_score",
              "intensity_score", "verification_confidence", "price", "url"]].copy()
table["risk_band"] = table["risk_band"].map(lambda b: f"{BAND_ICON.get(b, '')} {b}")

st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
    column_config={
        "title": st.column_config.TextColumn("Product", width="large"),
        "risk_band": "Band",
        "greenwash_risk_score": st.column_config.ProgressColumn(
            "Greenwash risk", min_value=0, max_value=100, format="%.1f"),
        "intensity_score": st.column_config.NumberColumn("Intensity", format="%.0f"),
        "verification_confidence": st.column_config.NumberColumn("Verification", format="%.0f"),
        "price": "Price",
        "url": st.column_config.LinkColumn("Link", display_text="Open"),
    },
)

# ---- Claim details ----
st.subheader("Claim details")
for _, r in view.iterrows():
    icon = BAND_ICON.get(r["risk_band"], "")
    with st.expander(f"{icon} {r['greenwash_risk_score']:.1f} · {r['title']}"):
        st.write(r["claim_text"])
        st.markdown(
            f"**Vague terms:** {pretty_terms(r['matched_vague_terms'])}  \n"
            f"**Certifications found:** {pretty_terms(r['matched_certifications'])}"
        )

with st.expander("How the score works"):
    st.markdown(
        """
**Intensity** measures how strong or absolute the claim language is
(e.g. "100%", "zero waste", "eco-friendly").
**Verification confidence** measures how much real evidence backs it
(certifications, specific checkable numbers).

`greenwash risk = intensity × (1 − verification_confidence / 100)`

Strong claims with no evidence score highest.
"""
    )