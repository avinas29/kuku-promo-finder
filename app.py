"""The website. Run with:  streamlit run app.py"""
import json

import pandas as pd
import streamlit as st

from promo_finder import PROVIDERS, find_promos, mmss, parse_screenplay

st.set_page_config(page_title="Promo Finder", layout="wide")
st.title("🎬 Promo Finder")
st.write("Upload microdrama screenplays. The tool finds the best 20-60 second promos, "
         "with a hook in the first 3 seconds and a cliffhanger ending, and ranks them.")

# ---- Sidebar: which AI model to use
st.sidebar.header("AI model")
provider = st.sidebar.selectbox("Provider", list(PROVIDERS) + ["Custom (OpenAI-compatible)", "No API key (keywords only)"])
default_url, default_model = PROVIDERS.get(provider, ("", ""))
if provider.startswith("No API"):
    api_key, base_url, model = "", "", ""
else:
    api_key = st.sidebar.text_input("API key", type="password")
    base_url = st.sidebar.text_input("Base URL", default_url)
    model = st.sidebar.text_input("Model", default_model)
count = st.sidebar.slider("Promos per episode", 1, 3, 2)

# ---- Input: upload files or paste one screenplay
files = st.file_uploader("Screenplay files (.txt), one per episode", type="txt", accept_multiple_files=True)
pasted = st.text_area("...or paste one screenplay here", height=150)

if st.button("Find promos", type="primary"):
    episodes = [parse_screenplay(f.read().decode("utf-8"), f.name) for f in files or []]
    if pasted.strip():
        episodes.append(parse_screenplay(pasted, "pasted"))
    episodes = [e for e in episodes if e["lines"]]
    if not episodes:
        st.error("No readable screenplay found.")
        st.stop()
    if provider != "No API key (keywords only)" and not api_key:
        st.warning("No API key entered, so the keyword method is used.")

    bar = st.progress(0.0, text="Reading episodes...")
    promos = find_promos(sorted(episodes, key=lambda e: e["number"]), api_key, base_url, model, count,
                         on_progress=lambda n, total: bar.progress(n / total, text=f"Episode {n}/{total}"))
    bar.empty()
    st.session_state["promos"] = promos

promos = st.session_state.get("promos")
if promos:
    st.subheader(f"{len(promos)} promos, best first")
    table = pd.DataFrame([{
        "Rank": p["rank"], "Episode": p["episode"], "Start": mmss(p["start"]), "End": mmss(p["end"]),
        "Seconds": p["length"], "Score": p["score"], "Hook": p["hook"], "Cliffhanger": p["cliffhanger"],
        "Why": p["why"], "Failed checks": p["failed_checks"],
    } for p in promos])
    st.dataframe(table, hide_index=True, width="stretch")
    st.download_button("Download CSV", table.to_csv(index=False), "promos.csv")
    st.download_button("Download JSON", json.dumps(promos, indent=2), "promos.json")

    st.subheader("Details")
    for p in promos[:20]:
        with st.expander(f"#{p['rank']}  Ep {p['episode']}  {mmss(p['start'])}-{mmss(p['end'])}  ({p['length']}s)"):
            st.write(f"**Hook:** {p['hook']}")
            st.write(f"**Cliffhanger:** {p['cliffhanger']}")
            st.write(f"**Why:** {p['why']}")
            st.write({k: ("✅" if v else "❌") for k, v in p["checks"].items()})
            st.code(p["script"], language=None)
