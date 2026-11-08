"""Build the two submission PDFs from the latest results.

  python3 make_pdfs.py            -> submission/Solution_Doc.pdf and submission/Results.pdf

Uses outputs/gemini-3.1-flash-lite/ if it exists, otherwise outputs/keywords/.
"""
import html
import json
import subprocess
from pathlib import Path

from evaluate import MUST_HAVE
from promo_finder import mmss

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
OUT = Path("submission")


def load(name):
    p = Path("outputs") / name / "promos.json"
    return json.loads(p.read_text()) if p.exists() else None


def score(promos):
    hit = lambda p, ep, t: p["episode"] == ep and p["start"] - 1 <= t <= p["end"] + 1
    found = [m for m in MUST_HAVE if any(hit(p, m[0], m[1]) for p in promos)]
    top = sum(any(hit(p, ep, t) for ep, t, _ in MUST_HAVE) for p in promos[:20])
    clean = sum(1 for p in promos if not p["failed_checks"])
    return found, top, clean


def to_pdf(html_text, pdf_name):
    src = Path("/tmp") / ("build_" + pdf_name.replace(".pdf", ".html"))
    src.write_text(html_text)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={(OUT / pdf_name).resolve()}", src.resolve().as_uri()],
                   check=True, capture_output=True)
    print("wrote", OUT / pdf_name)


kw = load("keywords")
ai = load("gemini-3.1-flash-lite")
if ai and all(p["source"].startswith("keywords") for p in ai):
    ai = None  # every AI call failed, so these are really keyword results
main, label = (ai, "Gemini 3.1 Flash-Lite") if ai else (kw, "Keyword method (no AI)")
kw_found, kw_top, kw_clean = score(kw)

# ---------------------------------------------------------------- solution doc
doc = Path("doc_template.html").read_text()
top5 = "".join(
    f"<tr><td>{p['rank']}</td><td>Ep {p['episode']} {mmss(p['start'])}-{mmss(p['end'])} ({p['length']:.0f}s)</td>"
    f"<td>{html.escape(p['hook'][:110])}</td><td>{html.escape(p['cliffhanger'][:110])}</td></tr>" for p in main[:5])
results = (f"Ran <b>{label}</b> on all 50 episodes: <b>{len(main)} promos</b> (2 per episode), ranked. "
           f"Full list with hook, cliffhanger and why: <i>Results.pdf</i>. The five I would post first:"
           f"<table><tr><th>#</th><th>Clip</th><th>Hook (first 3s)</th><th>Cliffhanger</th></tr>{top5}</table>"
           "The ranking puts first the clips with the strongest hook and cliffhanger scores, a small bonus for early "
           "episodes (a new viewer lands on Ep 1, so the payoff is close and twists stay unspoiled), and no failed checks.")
if not ai:
    results += (" <b>Note:</b> the Gemini run on the full pack did not finish before the deadline, so the numbers "
                "here are from the keyword method. The website runs the AI version when a key is entered.")
doc = doc.replace("[[AI_RESULTS]]", results)

if ai:
    a_found, a_top, a_clean = score(ai)
    row = f"<td>Gemini 3.1 Flash-Lite + code checks</td><td>{len(a_found)} / 20</td><td>{a_top} / 20</td><td>{a_clean} / {len(ai)}</td>"
    moved = [p for p in ai if abs(p["proposed_start"] - p["start"]) > 1 or abs(p["proposed_end"] - p["end"]) > 1]
    wrong = (f"Gemini proposed start/end times that were not real camera cuts in {len(moved)} of {len(ai)} promos "
             f"(off by more than 1 second), and {sum(1 for p in ai if not 20 <= p['proposed_end'] - p['proposed_start'] <= 60)} "
             "were outside 20-60s. That is why snapping and checking are code, not AI.")
    missed = [m for m in MUST_HAVE if m not in a_found]
else:
    row = "<td colspan=4>AI run not completed before the deadline (see note above)</td>"
    wrong = ""
    missed = [m for m in MUST_HAVE if m not in kw_found]
app_url = Path("app_url.txt").read_text().strip() if Path("app_url.txt").exists() else "see README"
doc = doc.replace("[[AI_ROW]]", row).replace("[[AI_WRONG]]", wrong).replace("[[APP_URL]]", app_url)
doc = doc.replace("[[KW_FOUND]]", str(len(kw_found))).replace("[[KW_TOP]]", str(kw_top)).replace("[[KW_CLEAN]]", f"{kw_clean} / {len(kw)}")

fails = []
if missed:
    fails.append("<li><b>Missed must-have moments:</b> " + "; ".join(f"Ep {e} ({html.escape(w)})" for e, _, w in missed[:5]) + ".</li>")
bad = [p for p in main if p["failed_checks"]]
if bad:
    fails.append(f"<li><b>Failed code checks:</b> {len(bad)} of {len(main)} promos, e.g. "
                 + "; ".join(f"Ep {p['episode']} {mmss(p['start'])}: {p['failed_checks']}" for p in bad[:3])
                 + ". They stay in the output but drop in the ranking.</li>")
doc = doc.replace("[[FAILURES]]", "".join(fails))
to_pdf(doc, "Solution_Doc.pdf")

# ---------------------------------------------------------------- results pdf
rows = "".join(
    f"<tr><td>{p['rank']}</td><td>{p['episode']}</td><td>{mmss(p['start'])}<br>{mmss(p['end'])}</td><td>{p['length']:.0f}</td>"
    f"<td>{p['score']}</td><td>{html.escape(p['hook'])}</td><td>{html.escape(p['cliffhanger'])}</td>"
    f"<td>{html.escape(p['why'])}</td><td>{html.escape(p['failed_checks']) or '✓'}</td></tr>" for p in main)
must = "".join(
    f"<li>{'✓' if any(p['episode'] == e and p['start'] - 1 <= t <= p['end'] + 1 for p in main) else '✗'} Ep {e}: {html.escape(w)}</li>"
    for e, t, w in MUST_HAVE)
found, top, clean = score(main)
to_pdf(f"""<!doctype html><meta charset=utf-8><style>
@page{{size:A4 landscape;margin:10mm}} body{{font:8.5pt/1.3 Helvetica,Arial,sans-serif}}
table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ccc;padding:2px 4px;vertical-align:top}}
th{{background:#eee}} tr{{page-break-inside:avoid}} h1{{font-size:14pt;margin:0}} ul{{columns:2;font-size:8.5pt}}</style>
<h1>Promo Finder - raw results (unedited)</h1>
<p>Show: <i>I Married a Broken Soldier. He was a Duke</i>, all 50 episodes · Picker: <b>{label}</b> ·
{len(main)} promos · ranked best first · times are MM:SS.ss inside the episode.</p>
<p><b>Quality summary:</b> must-have moments found {len(found)}/20 · top-20 promos that are must-haves {top}/20 ·
promos passing all 5 code checks {clean}/{len(main)}.</p><ul>{must}</ul>
<table><tr><th>Rank</th><th>Ep</th><th>Start<br>End</th><th>Sec</th><th>Score</th><th>Hook (first 3s)</th>
<th>Cliffhanger</th><th>Why it works</th><th>Failed checks</th></tr>{rows}</table>""", "Results.pdf")
