"""The Dining Index: a single-screen, interactive Zomato dashboard.

Run locally: python -m streamlit run zomato_app.py
Put Zomato Restaurant Dataset.csv beside this file, or upload it at startup.
The accompanying notebook handles Google Colab upload and preview setup.
"""
from io import BytesIO
from pathlib import Path
import json
import os
import zipfile

import pandas as pd
from plotly.offline import get_plotlyjs
import streamlit as st
import streamlit.components.v1 as components

REQUIRED = ["Restaurant ID", "Restaurant Name", "Country Code", "City", "Cuisines",
    "Average Cost for two", "Currency", "Has Online delivery", "Has Table booking",
    "Aggregate rating", "Rating text", "Votes", "Latitude", "Longitude", "Price range"]
NUMERIC = ["Country Code", "Average Cost for two", "Aggregate rating", "Votes", "Latitude", "Longitude", "Price range"]

@st.cache_data(show_spinner=False)
def load_data(payload: bytes, filename: str):
    """Keep original values; add separate fields used for analysis."""
    if filename.lower().endswith(".zip"):
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            choices = [n for n in archive.namelist() if n.lower().endswith(".csv") and not n.startswith("__MACOSX/")]
            named = [n for n in choices if Path(n).name == "Zomato Restaurant Dataset.csv"]
            if not named and len(choices) != 1:
                raise ValueError("Upload the Zomato CSV directly, or a ZIP containing just that CSV.")
            member = named[0] if named else choices[0]
            if archive.getinfo(member).file_size > 100 * 1024 * 1024:
                raise ValueError("The uncompressed CSV must be smaller than 100 MB.")
            payload = archive.read(member)
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            source = pd.read_csv(BytesIO(payload), encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    source.columns = source.columns.str.strip()
    missing = sorted(set(REQUIRED) - set(source.columns))
    if missing:
        raise ValueError("This dashboard needs the supplied Zomato dataset. Missing columns: " + ", ".join(missing))
    if source.empty:
        raise ValueError("The CSV contains no restaurants.")
    data = source.copy()
    for col in NUMERIC:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    for col in ["Restaurant Name", "City", "Cuisines", "Currency", "Has Online delivery", "Has Table booking", "Rating text"]:
        data[col] = data[col].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
    # The source uses zero and 'Not rated' for unrated restaurants.
    valid_rating = data["Aggregate rating"].between(0, 5, inclusive="right") & data["Rating text"].str.casefold().ne("not rated")
    data["Rating for analysis"] = data["Aggregate rating"].where(valid_rating)
    # Treat zero/negative costs as unspecified, not a free meal.
    data["Cost for analysis"] = data["Average Cost for two"].where(data["Average Cost for two"].gt(0))
    data["Cuisine list"] = data["Cuisines"].apply(lambda x: sorted({v.strip() for v in x.split(",") if v.strip()}))
    return source, data


DASHBOARD_TEMPLATE = r'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Dining Index</title>
<style>
:root{--paper:#f3f1ec;--white:#fffefa;--ink:#202c34;--muted:#728087;--line:#e2e4df;--red:#e34448;--mint:#208b77;--sand:#ecd9b9;--navy:#263d49}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;overflow:hidden}body{background:var(--paper);color:var(--ink);font-family:Inter,"Segoe UI",Arial,sans-serif;font-size:12px}button,input,select{font:inherit}button{cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--mint);outline-offset:2px}button{transition:background .16s,transform .16s}button:hover{filter:brightness(.97)}button:active{transform:translateY(1px)}
.board{height:100dvh;padding:14px 18px 10px;display:grid;grid-template-rows:54px 43px 77px minmax(0,1fr) 145px 20px;gap:10px;max-width:2000px;margin:auto;overflow:hidden}
.masthead{display:flex;align-items:center;justify-content:space-between;gap:20px}.identity{display:flex;align-items:center;gap:12px}.mark{height:41px;width:41px;border-radius:13px 13px 13px 3px;background:var(--red);color:white;display:grid;place-items:center;font:bold italic 31px Georgia}.eyebrow{font-size:9px;letter-spacing:2px;font-weight:700;color:var(--muted);text-transform:uppercase}.identity h1{font:29px/1.05 Georgia,serif;letter-spacing:-.9px;margin:2px 0 0}.identity h1 em{color:var(--red);font-weight:400}.head-right{display:flex;align-items:center;gap:18px}.dataset-count{text-align:right;font-size:11px;color:var(--muted)}.dataset-count strong{display:block;color:var(--ink);font-size:13px;margin-top:2px}.pill{border:1px solid var(--line);background:var(--white);border-radius:8px;padding:8px 12px;color:var(--ink);font-weight:600}.pill.dark{background:var(--ink);border-color:var(--ink);color:white}.live-dot{display:inline-block;width:6px;height:6px;background:var(--mint);border-radius:50%;margin-right:5px}
.controls{display:grid;grid-template-columns:1.35fr .62fr 1.15fr 1.45fr 1fr auto;gap:8px;min-width:0}.field{position:relative;display:flex;align-items:center;border:1px solid var(--line);background:var(--white);border-radius:8px;min-width:0;padding:0 10px;gap:7px}.field label{font-size:9px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;color:var(--muted);white-space:nowrap}.field select,.field input{background:transparent;border:0;color:var(--ink);min-width:0;width:100%;height:35px;outline-offset:0;font-size:11px}.segments{display:flex;align-items:center;gap:3px;background:var(--white);border:1px solid var(--line);border-radius:8px;padding:4px}.segments button{border:0;background:transparent;color:var(--muted);flex:1;height:31px;border-radius:5px;font-size:11px;white-space:nowrap}.segments button.active{background:var(--ink);color:white}.reset{border:1px solid var(--line);background:transparent;border-radius:8px;padding:0 13px;color:var(--ink)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.kpi{padding:11px 15px;background:var(--white);border:1px solid var(--line);border-radius:11px;display:grid;grid-template-columns:1fr auto;align-items:center;min-width:0}.kpi:first-child{background:var(--navy);color:white;border-color:var(--navy)}.k-label{font-size:10px;color:var(--muted);letter-spacing:.2px}.kpi:first-child .k-label,.kpi:first-child .k-note{color:#b9c8d0}.k-value{font-size:29px;font-weight:650;letter-spacing:-1px;line-height:1.12;margin-top:4px}.k-note{font-size:9px;line-height:1.4;color:var(--muted);max-width:140px;text-align:right}.k-icon{font-size:22px;color:var(--red);opacity:.8}
.main{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(0,1fr) minmax(230px,.85fr);gap:10px;min-height:0}.card{background:var(--white);border:1px solid var(--line);border-radius:11px;min-width:0;min-height:0;overflow:hidden}.chart-card{display:flex;flex-direction:column}.card-header{height:51px;padding:12px 15px 2px;display:flex;justify-content:space-between;align-items:flex-start;gap:8px;flex-shrink:0}.section-label{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:1.4px;font-weight:600}.card-title{font-size:14px;font-weight:650;margin-top:4px;letter-spacing:-.2px}.tiny{font-size:9px;color:var(--muted)}.chart{flex:1;min-height:0;width:100%}.chart-foot{height:24px;flex-shrink:0;padding:0 14px;font-size:9px;color:var(--muted);display:flex;align-items:center;gap:7px}.key-dot{width:6px;height:6px;border-radius:50%;display:inline-block}.chip-button{border:1px solid var(--line);background:var(--paper);font-size:9px;border-radius:5px;padding:5px 7px;white-space:nowrap}.chip-button.active{background:#ffe4df;border-color:#eeb1a9;color:#b92c33}.city-clear{color:var(--red);border:0;background:transparent;font-size:10px;padding:0}
.brief{background:var(--navy);color:white;display:flex;flex-direction:column;padding:15px;position:relative}.brief .section-label{color:#9aafb9}.brief-head{display:flex;justify-content:space-between;align-items:center}.brief h2{font:22px/1.2 Georgia,serif;margin:12px 0;color:#fff5e8;letter-spacing:-.5px}.brief-body{min-height:0;flex:1;display:flex;flex-direction:column;justify-content:space-between;gap:10px}.insight-line{padding-top:10px;border-top:1px solid #405763;color:#c4d0d5;font-size:11px;line-height:1.5}.insight-line b{color:white;font-weight:600}.brief-footer{margin-top:10px;color:#91a9b5;font-size:9px;line-height:1.5}.brief-close{border:1px solid #526772;background:transparent;color:white;padding:3px 7px;border-radius:5px;font-size:10px}.restaurant-tags{display:flex;flex-wrap:wrap;gap:5px;margin:6px 0}.restaurant-tags span{border:1px solid #536b78;border-radius:4px;padding:3px 5px;font-size:9px;color:#dce6e9}.restaurant-stats{display:grid;grid-template-columns:1fr 1fr;gap:8px}.restaurant-stats div{padding:10px;background:#334d5a;border-radius:7px}.restaurant-stats strong{font-size:20px;display:block;color:#ffe6c2;letter-spacing:-.3px}.restaurant-stats small{font-size:9px;color:#b8ccd5}.rest-name{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.rest-sub{font-size:10px;color:#b7ccd5;line-height:1.4;margin:-5px 0 5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.bottom{display:grid;grid-template-columns:1.6fr 1fr .9fr;gap:10px;min-height:0}.bottom .card{padding:12px 14px}.bottom-head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:9px}.bottom-title{font-size:12px;font-weight:650}.cuisines{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-template-rows:repeat(2,35px);gap:6px}.cuisine{position:relative;border:1px solid var(--line);border-radius:7px;background:#f8f7f3;padding:5px 8px;display:flex;align-items:center;justify-content:space-between;gap:5px;overflow:hidden;color:var(--ink)}.cuisine::before{content:"";position:absolute;inset:0 auto 0 0;width:var(--share);background:#e3ebe4;opacity:.65}.cuisine span,.cuisine b{position:relative;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cuisine b{color:var(--muted);font-weight:500;overflow:visible}.cuisine.active{border-color:var(--red);background:#fff0ed;color:#bb333d}.cuisine.active::before{background:#f8c9c0}.cuisine.active b{color:#bb333d}.cuisine-foot{font-size:9px;color:var(--muted);margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.price-tiers{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;height:76px}.tier{display:flex;flex-direction:column;justify-content:space-between;align-items:flex-start;position:relative;border:1px solid var(--line);border-radius:7px;background:#f8f7f3;padding:8px;color:var(--ink);overflow:hidden}.tier::before{content:"";position:absolute;inset:auto 0 0;height:var(--share);background:#efdebf;opacity:.7}.tier span,.tier strong{position:relative}.tier span{font-size:10px}.tier strong{font-size:17px;font-weight:600;letter-spacing:-.5px}.tier.active{border-color:var(--red);background:#ffede8}.tier.active::before{background:#f7c3b3}.quality-row{display:flex;justify-content:space-between;gap:5px;font-size:10px;margin-top:9px}.quality-row b{font-weight:600}.quality-track{height:5px;background:#e7e8e1;border-radius:4px;overflow:hidden;margin:9px 0}.quality-fill{height:100%;background:var(--mint);transition:width .3s}.quality-note{font-size:9px;color:var(--muted);line-height:1.45}.footer{display:flex;align-items:center;justify-content:space-between;gap:10px;color:var(--muted);font-size:9px;overflow:hidden}.footer-left{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.text-button{background:transparent;border:0;color:var(--muted);padding:0;font-size:9px;text-decoration:underline;text-underline-offset:3px;white-space:nowrap}.status-focus{color:var(--red);font-weight:600}
dialog{max-width:min(700px,92vw);max-height:88vh;border:1px solid var(--line);border-radius:15px;padding:24px;background:var(--white);color:var(--ink);box-shadow:0 30px 90px #15283240}dialog::backdrop{background:#182b35a6;backdrop-filter:blur(3px)}dialog h2{font:26px Georgia;margin:0 0 10px}dialog p,dialog li{font-size:12px;line-height:1.6;color:#53636c}dialog ul{padding-left:19px}dialog .close-modal{float:right;border:0;background:var(--paper);border-radius:6px;padding:6px 10px}dialog .form-row{margin:17px 0;display:flex;justify-content:space-between;align-items:center;gap:25px;font-size:12px}dialog input[type=number]{width:100px;border:1px solid var(--line);padding:7px;border-radius:5px}dialog input[type=range]{accent-color:var(--red);width:180px}dialog select{max-width:230px;border:1px solid var(--line);padding:7px;background:white;border-radius:5px}.empty{display:flex;align-items:center;justify-content:center;color:var(--muted);font-size:12px;text-align:center;padding:25px;line-height:1.5;height:100%}.tooltip-inline{display:inline-block;padding:3px 7px;background:#e9eee7;border-radius:4px;color:#4b685e;font-size:9px}.pulse{animation:flash .38s ease-out}@keyframes flash{0%{opacity:.4;transform:translateY(3px)}100%{opacity:1;transform:translateY(0)}}
@media(min-height:900px){.board{grid-template-rows:62px 46px 88px minmax(0,1fr) 165px 22px;padding:20px 24px 12px;gap:12px}.identity h1{font-size:32px}.k-value{font-size:34px}.bottom .card{padding:15px 17px}.cuisines{grid-template-rows:repeat(2,41px)}.price-tiers{height:88px}.brief{padding:20px}.brief h2{font-size:27px}.insight-line{font-size:12px;padding-top:15px}.card-title{font-size:16px}}
@media(max-height:700px){.board{padding:8px 12px;grid-template-rows:43px 36px 63px minmax(0,1fr) 124px 16px;gap:7px}.identity h1{font-size:24px}.mark{width:34px;height:34px;font-size:25px}.kpi{padding:8px 11px}.k-value{font-size:25px}.k-note{font-size:8px}.controls .field select,.controls .field input{height:30px}.segments{padding:2px}.segments button{height:28px}.card-header{height:43px;padding:9px 12px 1px}.card-title{font-size:12px}.chart-foot{height:20px;font-size:8px}.brief{padding:12px}.brief h2{font-size:18px;margin:8px 0}.insight-line{font-size:10px;line-height:1.35;padding-top:6px}.brief-body{gap:6px}.brief-footer{font-size:8px;margin-top:5px}.bottom .card{padding:9px 12px}.bottom-head{margin-bottom:6px}.cuisines{grid-template-rows:repeat(2,29px);gap:5px}.price-tiers{height:64px}.restaurant-stats div{padding:7px}.restaurant-stats strong{font-size:17px}.restaurant-tags{margin:3px 0}}
@media(max-width:1100px){.board{padding-left:10px;padding-right:10px}.main{grid-template-columns:minmax(0,1.3fr) minmax(0,.95fr) minmax(200px,.85fr)}.controls{grid-template-columns:1.25fr .7fr 1fr 1.3fr .9fr auto}.field{padding:0 7px;gap:4px}.field label{font-size:8px}.head-right{gap:9px}.k-note{max-width:95px}.cuisines{grid-template-columns:repeat(2,minmax(0,1fr))}.cuisine:nth-child(n+5){display:none}.k-value{font-size:26px}.kpi{padding:10px}.dataset-count{display:none}.bottom{grid-template-columns:1.4fr 1fr .95fr}}
@media(max-width:800px){.main{grid-template-columns:1.4fr 1fr}.brief{display:none}.controls{grid-template-columns:1.2fr .7fr 1fr 1.2fr auto}.search-field{display:none}.k-note{display:none}.head-right .pill{font-size:10px;padding:7px}.identity h1{font-size:24px}.bottom{grid-template-columns:1.3fr 1fr}.quality-card{display:none}.field label{display:none}.k-value{font-size:24px}.footer{font-size:8px}.cuisines{grid-template-columns:repeat(3,minmax(0,1fr))}.cuisine:nth-child(n+5){display:flex}}
@media(min-height:701px) and (max-height:800px){.brief h2{font-size:20px;margin:9px 0}.brief-body{gap:8px}.insight-line{font-size:10.5px;line-height:1.4;padding-top:8px}.brief-footer{font-size:8px;line-height:1.4;margin-top:7px}}
</style>
<script>__PLOTLY_JS__</script>
</head>
<body>
<main class="board">
  <header class="masthead">
    <div class="identity"><div class="mark">z.</div><div><div class="eyebrow">Zomato dataset / interactive atlas</div><h1>The <em>Dining</em> Index</h1></div></div>
    <div class="head-right"><div class="dataset-count"><span class="live-dot"></span>KAGGLE SNAPSHOT<strong id="dataset-count"></strong></div><button class="pill" id="filter-button">Fine-tune ↗</button><button class="pill dark" id="export-button">Export selection ↓</button></div>
  </header>
  <section class="controls" aria-label="Dashboard filters">
    <div class="field"><label for="currency">Currency</label><select id="currency" aria-label="Currency"></select></div>
    <div class="field"><label for="country">Code</label><select id="country" aria-label="Country code"></select></div>
    <div class="field"><label for="city">City</label><select id="city" aria-label="City"></select></div>
    <div class="segments" aria-label="Service filter"><button class="active" data-service="all">All venues</button><button data-service="delivery">Delivery</button><button data-service="booking">Bookable</button></div>
    <div class="field search-field"><label for="search">Find</label><input id="search" placeholder="Restaurant name…" aria-label="Search restaurant name"></div>
    <button class="reset" id="reset" title="Reset filters within this market">Reset ↺</button>
  </section>
  <section class="kpis" aria-live="polite">
    <article class="kpi"><div><div class="k-label">Restaurants in focus</div><div class="k-value" id="k-count">—</div></div><div class="k-note" id="k-count-note"></div></article>
    <article class="kpi"><div><div class="k-label">Average rating <span class="tiny">/ 5</span></div><div class="k-value" id="k-rating">—</div></div><div class="k-note" id="k-rating-note"></div></article>
    <article class="kpi"><div><div class="k-label">Typical cost for two</div><div class="k-value" id="k-cost">—</div></div><div class="k-note" id="k-cost-note"></div></article>
    <article class="kpi"><div><div class="k-label">Online delivery</div><div class="k-value" id="k-delivery">—</div></div><div class="k-note" id="k-delivery-note"></div></article>
  </section>
  <section class="main">
    <article class="card chart-card"><div class="card-header"><div><div class="section-label">01 / Price meets experience</div><div class="card-title">What does a better rating cost?</div></div><button class="chip-button" id="log-toggle" title="Toggle logarithmic cost scale">Log scale</button></div><div id="scatter" class="chart" aria-label="Interactive cost versus rating plot"></div><div class="chart-foot"><span class="key-dot" style="background:#e34448"></span>Delivery <span class="key-dot" style="background:#678c8f;margin-left:5px"></span>No delivery <span style="margin-left:auto">Click a dot for details ↗</span></div></article>
    <article class="card chart-card"><div class="card-header"><div><div class="section-label">02 / Choose a city</div><div class="card-title">Where the listings are</div></div><button class="city-clear" id="clear-city">All cities</button></div><div id="city-chart" class="chart" aria-label="Click a city bar to filter"></div><div class="chart-foot" id="city-foot">Click a bar to focus every panel</div></article>
    <aside class="card brief" id="brief" aria-live="polite"></aside>
  </section>
  <section class="bottom">
    <article class="card"><div class="bottom-head"><span class="bottom-title">03 / Cuisine switchboard</span><button class="text-button" id="more-cuisine">All cuisines ↗</button></div><div class="cuisines" id="cuisines"></div><div class="cuisine-foot" id="cuisine-foot">Click to focus. Click again to clear.</div></article>
    <article class="card"><div class="bottom-head"><span class="bottom-title">04 / Price mix</span><span class="tiny">click a tier</span></div><div class="price-tiers" id="tiers"></div><div class="cuisine-foot">Source tiers 1–4, from lower to higher prices.</div></article>
    <article class="card quality-card"><div class="bottom-head"><span class="bottom-title">Know your sample</span><span class="tooltip-inline" id="sample-badge">—</span></div><div class="quality-row"><span>Rated restaurants</span><b id="quality-rated">—</b></div><div class="quality-track"><div class="quality-fill" id="quality-fill"></div></div><div class="quality-note" id="quality-note"></div></article>
  </section>
  <footer class="footer"><div class="footer-left" id="status"></div><button class="text-button" id="about-button">How to read this dashboard</button></footer>
</main>
<dialog id="filters-modal"><button class="close-modal" data-close>Close ×</button><h2>Fine-tune your view</h2><p>Every change updates the dashboard immediately.</p><div class="form-row"><label for="rating-min">Minimum rating <strong id="rating-value">0.0</strong></label><input id="rating-min" type="range" min="0" max="5" step="0.1" value="0"></div><div class="form-row"><label for="vote-min">Minimum votes</label><input id="vote-min" type="number" min="0" step="25" value="0"></div><div class="form-row"><label for="unrated">Include unrated restaurants, even with a rating filter</label><input id="unrated" type="checkbox" checked></div><div class="form-row"><label for="cost-max">Maximum cost for two (blank = any)</label><input id="cost-max" type="number" min="0" placeholder="Any"></div><div class="form-row"><label for="unknown-cost">Include unspecified costs</label><input id="unknown-cost" type="checkbox" checked></div><div class="form-row"><label for="all-cuisine">Cuisine focus</label><select id="all-cuisine"></select></div><p>Choose country and currency first. Country codes and currency names are retained from the CSV. Zero costs are treated as unspecified.</p></dialog>
<dialog id="about-modal"><button class="close-modal" data-close>Close ×</button><h2>A dashboard you can explore</h2><ul><li><b>Click a city bar, cuisine or price tier</b> to focus the dashboard. Click it again to clear the selection.</li><li><b>Click a dot</b> to reveal a restaurant in the dark insight panel. Close the spotlight to return to the live market brief.</li><li>City bars retain the other cities for navigation. They respect all active filters except the city selection. Cuisine counts similarly omit the cuisine filter; price-tier counts omit the tier filter.</li><li>Rating averages exclude zero and Not rated entries. They are unweighted restaurant averages. Typical cost is the median of positive recorded costs.</li><li>Currency and country are both selected to avoid mixing different countries with the generic Dollar label. Source currency labels are not independently verified.</li><li>A restaurant can have several cuisines, so cuisine counts overlap. Missing cuisine entries are excluded from the switchboard.</li><li>This is a historical dataset snapshot, not live Zomato data. There are no sales, orders or dates. Votes are not revenue or demand. Some source names have damaged characters.</li><li>Cost versus rating uses restaurants with both values. The reported Pearson correlation uses original costs even when the display uses a logarithmic axis; it does not establish causation.</li><li>Export downloads all original CSV columns for matching restaurants. The compact layout is designed for laptop screens of 1280 × 720 and larger.</li></ul></dialog>
<script id="dataset" type="application/json">__DATA_JSON__</script>
<script>
const payload=JSON.parse(document.getElementById('dataset').textContent);
const rows=payload.rows, source=payload.source, $=id=>document.getElementById(id);
const nf=new Intl.NumberFormat('en-IN'), number=n=>nf.format(n), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const currencies=[...new Set(rows.map(r=>r.currency))].sort();
const state={currency:currencies.includes('Indian Rupees(Rs.)')?'Indian Rupees(Rs.)':currencies[0],country:null,city:'',cuisine:'',tier:null,service:'all',search:'',minRating:0,minVotes:0,unrated:true,maxCost:null,unknownCost:true,log:false,restaurant:null};
const currencyLabel=c=>c==='Indian Rupees(Rs.)'?'Indian Rupees (INR)':c;
const mean=a=>a.length?a.reduce((s,v)=>s+v,0)/a.length:null;
const median=a=>{if(!a.length)return null;const b=[...a].sort((x,y)=>x-y),m=Math.floor(b.length/2);return b.length%2?b[m]:(b[m-1]+b[m])/2};
const cash=v=>v==null?'N/A':(state.currency==='Indian Rupees(Rs.)'?'₹':'')+number(Math.round(v));
const counts=(rs,key)=>{const c=new Map();rs.forEach(r=>{for(const v of (Array.isArray(r[key])?r[key]:[r[key]])){if(v!=null&&v!==''&&v!=='Unknown')c.set(v,(c.get(v)||0)+1)}});return [...c].sort((a,b)=>b[1]-a[1]||String(a[0]).localeCompare(String(b[0])))};
const market=()=>rows.filter(r=>r.currency===state.currency&&r.country===state.country);
const selected=(skip='')=>market().filter(r=>(skip==='city'||!state.city||r.city===state.city)&&(skip==='cuisine'||!state.cuisine||r.cuisines.includes(state.cuisine))&&(skip==='tier'||state.tier==null||r.tier===state.tier)&&(state.service==='all'||(state.service==='delivery'?r.delivery:r.booking))&&(!state.search||r.name.toLowerCase().includes(state.search))&&(r.rating==null?state.unrated:r.rating>=state.minRating)&&r.votes>=state.minVotes&&(r.cost==null?state.unknownCost:state.maxCost==null||r.cost<=state.maxCost));
let current=[],renderVersion=0;
function options(el,values,label=x=>x,first=null){el.replaceChildren();if(first!==null){const o=new Option(first,'');el.add(o)}values.forEach(v=>el.add(new Option(label(v),v)))}
function resetFilters(){Object.assign(state,{city:'',cuisine:'',tier:null,service:'all',search:'',minRating:0,minVotes:0,unrated:true,maxCost:null,unknownCost:true,restaurant:null});syncControls();render()}
function syncControls(){options($('currency'),currencies,currencyLabel);$('currency').value=state.currency;const cs=[...new Set(rows.filter(r=>r.currency===state.currency).map(r=>r.country))].sort((a,b)=>a-b);if(!cs.includes(state.country))state.country=cs[0];options($('country'),cs);$('country').value=state.country;options($('city'),[...new Set(market().map(r=>r.city))].sort(),x=>x,'All cities');$('city').value=state.city;options($('all-cuisine'),[...new Set(market().flatMap(r=>r.cuisines))].filter(x=>x!=='Unknown').sort(),x=>x,'All cuisines');$('all-cuisine').value=state.cuisine;$('search').value=state.search;$('rating-min').value=state.minRating;$('rating-value').textContent=state.minRating.toFixed(1);$('vote-min').value=state.minVotes;$('unrated').checked=state.unrated;$('cost-max').value=state.maxCost??'';$('unknown-cost').checked=state.unknownCost;document.querySelectorAll('[data-service]').forEach(b=>b.classList.toggle('active',b.dataset.service===state.service));}
function focus(key,value){state[key]=state[key]===value?(key==='tier'?null:''):value;state.restaurant=null;syncControls();render()}
function animate(el){el.classList.remove('pulse');void el.offsetWidth;el.classList.add('pulse')}
function pearson(rs){if(rs.length<3)return null;const mx=mean(rs.map(r=>r.cost)),my=mean(rs.map(r=>r.rating));let cov=0,vx=0,vy=0;rs.forEach(r=>{let x=r.cost-mx,y=r.rating-my;cov+=x*y;vx+=x*x;vy+=y*y});return vx&&vy?cov/Math.sqrt(vx*vy):null}
function topWithSelection(entries,n,value){let top=entries.slice(0,n);if(value&&!top.some(x=>x[0]===value)){const found=entries.find(x=>x[0]===value);if(found)top=[...top.slice(0,n-1),found]}return top}
function render(){
  current=selected();const n=current.length,rated=current.filter(r=>r.rating!=null),costs=current.filter(r=>r.cost!=null),del=current.filter(r=>r.delivery).length;
  $('k-count').textContent=number(n);$('k-count-note').textContent=`${n?((n/market().length)*100).toFixed(1):'0.0'}% of selected market`;
  $('k-rating').textContent=rated.length?mean(rated.map(r=>r.rating)).toFixed(2):'N/A';$('k-rating-note').textContent=`${number(rated.length)} rated · ${number(n-rated.length)} unrated`;
  $('k-cost').textContent=cash(median(costs.map(r=>r.cost)));$('k-cost-note').textContent=`Median · ${state.currency==='Indian Rupees(Rs.)'?'INR':state.currency}`;
  $('k-delivery').textContent=n?(100*del/n).toFixed(1)+'%':'N/A';$('k-delivery-note').textContent=`${number(del)} of ${number(n)} restaurants`;
  for(const id of ['k-count','k-rating','k-cost','k-delivery'])animate($(id));
  $('quality-rated').textContent=`${number(rated.length)} / ${number(n)}`;$('quality-fill').style.width=(n?100*rated.length/n:0)+'%';$('sample-badge').textContent=n?Math.round(100*rated.length/n)+'% rated':'No matches';
  $('quality-note').textContent=`${number(n-costs.length)} unspecified costs. ${state.minVotes?`Minimum ${number(state.minVotes)} votes.`:'Use Fine-tune to require more votes.'}`;
  document.querySelectorAll('[data-service]').forEach(b=>b.classList.toggle('active',b.dataset.service===state.service));
  $('status').innerHTML=`<span class="status-focus">${esc(state.city||'All cities')}${state.cuisine?' / '+esc(state.cuisine):''}${state.tier?' / Tier '+state.tier:''}</span> · ${esc(currencyLabel(state.currency))} · Country ${state.country} · ${state.minRating?'Rating ≥ '+state.minRating.toFixed(1)+' · ':''}${state.minVotes?'Votes ≥ '+number(state.minVotes)+' · ':''}Click to explore. Every selection recalculates.`;
  $('city-foot').textContent=state.city?`Focused: ${state.city}. Click again to clear.`:'Other filters apply; click a city bar to focus.';
  renderCuisine();renderTiers();renderBrief();renderCharts(++renderVersion);window.__diningState={state:{...state},count:n,rated:rated.length,median:median(costs.map(r=>r.cost)),delivery:del};
}
function renderCuisine(){const cs=topWithSelection(counts(selected('cuisine'),'cuisines'),6,state.cuisine),max=cs[0]?.[1]||1;$('cuisines').replaceChildren();for(const [name,count] of cs){const b=document.createElement('button');b.className='cuisine'+(state.cuisine===name?' active':'');b.style.setProperty('--share',(count/max*100)+'%');b.title=`${name}: ${number(count)} restaurants. Click to ${state.cuisine===name?'clear':'focus'}.`;b.setAttribute('aria-label',`Cuisine ${name}`);b.innerHTML=`<span>${esc(name)}</span><b>${number(count)}</b>`;b.onclick=()=>focus('cuisine',name);$('cuisines').appendChild(b)}if(!cs.length)$('cuisines').innerHTML='<div class="empty">No cuisines match.</div>';$('cuisine-foot').textContent=state.cuisine?`Focused: ${state.cuisine}. Click again to clear.`:'Counts overlap. Other filters apply; click to focus.';}
function renderTiers(){const base=selected('tier');$('tiers').replaceChildren();for(const tier of [1,2,3,4]){const n=base.filter(r=>r.tier===tier).length,share=base.length?n/base.length:0,b=document.createElement('button');b.className='tier'+(state.tier===tier?' active':'');b.style.setProperty('--share',share*100+'%');b.setAttribute('aria-label',`Price tier ${tier}`);b.title=`${number(n)} restaurants · ${(share*100).toFixed(1)}%`;b.innerHTML=`<span>Tier ${tier}</span><strong>${Math.round(share*100)}<small style="font-size:10px">%</small></strong>`;b.onclick=()=>focus('tier',tier);$('tiers').appendChild(b)}}
function renderBrief(){const r=rows.find(r=>r.id===state.restaurant);if(r&&current.some(x=>x.id===r.id)){const fullCuisines=esc(r.cuisines.join(', '));$('brief').innerHTML=`<div class="brief-head"><div class="section-label">Restaurant spotlight</div><button class="brief-close" id="close-spotlight">Back ×</button></div><div class="brief-body"><div><h2 class="rest-name" title="${esc(r.name)}">${esc(r.name)}</h2><p class="rest-sub">${esc(r.locality||r.city)} · ${esc(r.city)}</p><div class="restaurant-tags"><span>${r.delivery?'Delivery available':'No online delivery'}</span><span>${r.booking?'Table booking':'No table booking'}</span></div></div><div class="restaurant-stats"><div><strong>${r.rating==null?'N/A':r.rating.toFixed(1)}</strong><small>rating / 5</small></div><div><strong>${cash(r.cost)}</strong><small>cost for two</small></div></div><div class="insight-line"><b>${number(r.votes)} votes</b><br><span class="rest-sub" style="display:block;margin:4px 0;max-height:35px;overflow:hidden" title="${fullCuisines}">${fullCuisines}</span></div></div><div class="brief-footer">Restaurant ID ${esc(r.id)} · Source snapshot</div>`;$('close-spotlight').onclick=()=>{state.restaurant=null;renderBrief()};return}
  state.restaurant=null;const n=current.length,topCity=counts(current,'city')[0],topCuisine=counts(current,'cuisines')[0],paired=current.filter(r=>r.cost!=null&&r.rating!=null),corr=pearson(paired);
  $('brief').innerHTML=`<div class="brief-head"><div class="section-label">Your live market brief</div><span style="color:#a6c3b1;font-size:14px">✳</span></div><div class="brief-body"><h2>${n?'A closer look at<br>'+esc(state.city||'this market')+'.':'No matches<br>in this view.'}</h2>${n?`<div class="insight-line"><b>${esc(topCity?.[0]||'Unknown city')}</b> accounts for <b>${topCity?Math.round(topCity[1]/n*100):0}%</b> of the selected listings.</div><div class="insight-line">${topCuisine?`<b>${esc(topCuisine[0])}</b> is the most common recorded cuisine, served by <b>${number(topCuisine[1])}</b> restaurants.`:'No cuisines are recorded in this selection.'}</div><div class="insight-line">Price–rating correlation <b>${corr==null?'N/A':corr.toFixed(2)}</b><br><span style="font-size:9px;color:#9cb4c1">${number(paired.length)} comparable records · descriptive only</span></div>`:'<div class="insight-line">Try a lower vote threshold, clear a cuisine, or press <b>Reset</b> to see this market again.</div>'}</div><div class="brief-footer">Click a restaurant dot to replace this brief with its details.</div>`;
}
const config={displayModeBar:false,responsive:true,scrollZoom:false};
const baseLayout={paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{family:'Inter, Segoe UI, Arial',color:'#607078',size:10},hoverlabel:{bgcolor:'#203641',font:{color:'white',size:11},bordercolor:'#203641'}};
async function renderCharts(version){
  const paired=current.filter(r=>r.rating!=null&&r.cost!=null),traces=[];
  for(const online of [false,true]){const set=paired.filter(r=>r.delivery===online);traces.push({type:'scattergl',mode:'markers',name:online?'Delivery':'No delivery',x:set.map(r=>r.cost),y:set.map(r=>r.rating),customdata:set.map(r=>[r.id,r.name,r.city,r.votes]),marker:{color:online?'#e34448':'#678c8f',size:set.map(r=>Math.max(5,Math.min(17,4+Math.sqrt(r.votes)/5))),opacity:.56,line:{width:0}},hovertemplate:'<b>%{customdata[1]}</b><br>%{customdata[2]}<br>Cost for two: %{x:,.0f}<br>Rating: %{y:.1f} / 5<br>Votes: %{customdata[3]:,}<extra></extra>'})}
  const scatterLayout={...baseLayout,autosize:true,margin:{l:42,r:15,t:8,b:37},showlegend:false,xaxis:{title:{text:state.currency==='Indian Rupees(Rs.)'?'Cost for two (INR)':'Cost for two · selected currency',font:{size:10},standoff:8},type:state.log?'log':'linear',gridcolor:'#edf0eb',zeroline:false,tickfont:{size:9},automargin:true},yaxis:{title:{text:'Rating / 5',font:{size:10},standoff:4},range:[1,5.1],gridcolor:'#edf0eb',zeroline:false,tickfont:{size:9},fixedrange:true},annotations:paired.length?[]:[{text:'No restaurants have both a rating and cost.<br>Adjust your filters.',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false,font:{size:12,color:'#728087'}}],hovermode:'closest',dragmode:false};
  const cityEntries=topWithSelection(counts(selected('city'),'city'),7,state.city).reverse();
  const cityTrace={type:'bar',orientation:'h',x:cityEntries.map(x=>x[1]),y:cityEntries.map(x=>x[0]),marker:{color:cityEntries.map(x=>x[0]===state.city?'#e34448':'#d5deda'),line:{width:0}},text:cityEntries.map(x=>number(x[1])),textposition:'outside',textfont:{size:10,color:'#4f606a'},cliponaxis:false,hovertemplate:'<b>%{y}</b><br>%{x:,} restaurants<br>Click to focus<extra></extra>',customdata:cityEntries.map(x=>x[0])};
  const cityLayout={...baseLayout,autosize:true,margin:{l:12,r:42,t:7,b:15},xaxis:{visible:false,range:[0,Math.max(1,...cityEntries.map(x=>x[1]))*1.18],fixedrange:true},yaxis:{automargin:true,tickfont:{size:10},fixedrange:true},bargap:.38,showlegend:false,dragmode:false,annotations:cityEntries.length?[]:[{text:'No matching cities',xref:'paper',yref:'paper',x:.5,y:.5,showarrow:false}]};
  await Promise.all([Plotly.react($('scatter'),traces,scatterLayout,config),Plotly.react($('city-chart'),[cityTrace],cityLayout,config)]);
  if(version!==renderVersion)return;
  $('scatter').removeAllListeners('plotly_click');$('scatter').on('plotly_click',event=>{const point=event.points[0];state.restaurant=point.customdata[0];renderBrief();if(innerWidth<=800){$('spotlight-modal')?.remove();const d=document.createElement('dialog');d.id='spotlight-modal';d.innerHTML='<button class="close-modal">Close ×</button><h2>'+esc(point.customdata[1])+'</h2><p>'+esc(point.customdata[2])+' · Rating '+point.y.toFixed(1)+' / 5<br>Cost for two '+cash(point.x)+'<br>'+number(point.customdata[3])+' votes</p>';document.body.append(d);d.querySelector('button').onclick=()=>d.close();d.showModal()}});
  $('city-chart').removeAllListeners('plotly_click');$('city-chart').on('plotly_click',event=>focus('city',event.points[0].customdata));
}
$('currency').onchange=()=>{state.currency=$('currency').value;state.country=null;resetFilters()};$('country').onchange=()=>{state.country=Number($('country').value);resetFilters()};$('city').onchange=()=>{state.city=$('city').value;state.restaurant=null;render()};$('clear-city').onclick=()=>{state.city='';$('city').value='';state.restaurant=null;render()};
document.querySelectorAll('[data-service]').forEach(b=>b.onclick=()=>{state.service=b.dataset.service;state.restaurant=null;render()});
let searchTimer;$('search').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{state.search=$('search').value.trim().toLowerCase();state.restaurant=null;render()},180)};
$('reset').onclick=resetFilters;$('log-toggle').onclick=()=>{state.log=!state.log;$('log-toggle').classList.toggle('active',state.log);renderCharts(++renderVersion)};
$('filter-button').onclick=()=>$('filters-modal').showModal();$('more-cuisine').onclick=()=>{$('filters-modal').showModal();$('all-cuisine').focus()};$('about-button').onclick=()=>$('about-modal').showModal();document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>b.closest('dialog').close());document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close()}}));
$('rating-min').oninput=()=>{state.minRating=Number($('rating-min').value);$('rating-value').textContent=state.minRating.toFixed(1);state.restaurant=null;render()};$('vote-min').oninput=()=>{state.minVotes=Math.max(0,Number($('vote-min').value)||0);state.restaurant=null;render()};$('unrated').onchange=()=>{state.unrated=$('unrated').checked;state.restaurant=null;render()};$('cost-max').oninput=()=>{state.maxCost=$('cost-max').value===''?null:Math.max(0,Number($('cost-max').value));state.restaurant=null;render()};$('unknown-cost').onchange=()=>{state.unknownCost=$('unknown-cost').checked;state.restaurant=null;render()};$('all-cuisine').onchange=()=>{state.cuisine=$('all-cuisine').value;state.restaurant=null;render()};
$('export-button').onclick=()=>{const encode=v=>'"'+String(v??'').replaceAll('"','""')+'"';const records=[source.columns,...current.map(r=>source.rows[r.index])];const csv='\uFEFF'+records.map(row=>row.map(encode).join(',')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'})),a=document.createElement('a');a.href=url;a.download='zomato_selection.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)};
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{Plotly.Plots.resize($('scatter'));Plotly.Plots.resize($('city-chart'))},120)});
$('dataset-count').textContent=number(rows.length)+' restaurants · '+new Set(rows.map(r=>r.country)).size+' country codes';syncControls();render();
</script>
</body></html>
'''


@st.cache_data(show_spinner=False)
def make_dashboard(payload: bytes, filename: str) -> str:
    source, data = load_data(payload, filename)
    if data["Restaurant ID"].isna().any() or data["Restaurant ID"].duplicated().any():
        raise ValueError("Restaurant IDs must be present and unique. Resolve missing or repeated IDs before analysing this file.")
    if data["Country Code"].isna().any():
        raise ValueError("Country codes are missing or invalid in this CSV.")
    records = []
    for index, row in data.iterrows():
        records.append({
            "index": int(index), "id": str(row["Restaurant ID"]),
            "name": str(row["Restaurant Name"]), "city": str(row["City"]),
            "locality": str(row.get("Locality", row["City"])),
            "country": int(row["Country Code"]), "currency": str(row["Currency"]),
            "cuisines": row["Cuisine list"],
            "rating": float(row["Rating for analysis"]) if pd.notna(row["Rating for analysis"]) else None,
            "cost": float(row["Cost for analysis"]) if pd.notna(row["Cost for analysis"]) else None,
            "votes": max(0, int(row["Votes"])) if pd.notna(row["Votes"]) else 0,
            "delivery": row["Has Online delivery"] == "Yes", "booking": row["Has Table booking"] == "Yes",
            "tier": int(row["Price range"]) if pd.notna(row["Price range"]) else None,
        })
    original = json.loads(source.to_json(orient="split", force_ascii=False))
    browser_data = {"rows": records, "source": {"columns": original["columns"], "rows": original["data"]}}
    serialized = json.dumps(browser_data, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    # Bundle Plotly with the app, so chart scripts do not depend on a CDN.
    plotly_script = get_plotlyjs().replace("</script", "<\\/script")
    return DASHBOARD_TEMPLATE.replace("__PLOTLY_JS__", plotly_script).replace("__DATA_JSON__", serialized)


def main():
    st.set_page_config(page_title="The Dining Index", page_icon="🍽️", layout="wide", initial_sidebar_state="collapsed")
    path = Path(os.environ.get("ZOMATO_CSV", str(Path(__file__).parent / "Zomato Restaurant Dataset.csv")))
    if path.is_file():
        content, filename = path.read_bytes(), path.name
    else:
        st.title("The Dining Index")
        st.write("Upload the Zomato CSV or its ZIP to open your dashboard.")
        uploaded = st.file_uploader("Zomato dataset", type=["csv", "zip"])
        if uploaded is None:
            st.stop()
        content, filename = uploaded.getvalue(), uploaded.name
    try:
        dashboard = make_dashboard(content, filename)
    except (ValueError, OSError, zipfile.BadZipFile, pd.errors.ParserError) as exc:
        st.error(str(exc))
        st.stop()
    # Fill the browser viewport with one responsive dashboard component.
    st.markdown("""<style>
      html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"],
      [data-testid="stMain"] {height:100dvh!important;overflow:hidden!important;}
      [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stSidebar"],
      #MainMenu, footer, [data-testid="stDecoration"] {display:none!important;}
      [data-testid="stMainBlockContainer"] {padding:0!important;max-width:100%!important;}
      [data-testid="stVerticalBlock"] {gap:0!important;}
      [data-testid="stElementContainer"]:has(style) {display:none!important;}
      iframe {width:100%!important;height:100dvh!important;border:0!important;display:block!important;}
    </style>""", unsafe_allow_html=True)
    if hasattr(st, "iframe"):
        st.iframe(dashboard, height=900)
    else:
        components.html(dashboard, height=900, scrolling=False)


if __name__ == "__main__":
    main()
