"""Run on a whole folder from the terminal and save the raw outputs.

  python3 run_folder.py <folder> [provider] [api_key]
  e.g. python3 run_folder.py ../ Gemini YOUR_KEY
       python3 run_folder.py ../                    (no key -> keyword method)
"""
import csv
import json
import sys
import time
from pathlib import Path

import promo_finder as pf

folder = Path(sys.argv[1])
provider = sys.argv[2] if len(sys.argv) > 2 else ""
key = sys.argv[3] if len(sys.argv) > 3 else (Path("api_key.txt").read_text().strip() if Path("api_key.txt").exists() else "")
url, model = pf.PROVIDERS.get(provider, ("", ""))

episodes = [pf.parse_screenplay(f.read_text(encoding="utf-8"), f.name) for f in sorted(folder.glob("*.txt"))]
episodes = sorted([e for e in episodes if e["lines"]], key=lambda e: e["number"])
print(f"{len(episodes)} episodes, model: {model or 'keywords'}")

# test the key on one episode first, so a bad key stops here instead of silently using keywords
if key:
    try:
        pf.ask_ai(episodes[0], key, url, model)
        print("API key works.")
    except Exception as err:
        sys.exit(f"The AI call failed: {err}\nCheck the key (copy it again) and the provider name.")

# free tiers allow ~10 requests a minute, so wait a little between episodes
slow = lambda n, total: (print(f"  episode {n}/{total}"), time.sleep(6 if key else 0))
promos = pf.find_promos(episodes, key, url, model, 2, on_progress=slow)

out = Path("outputs") / (model or "keywords")
out.mkdir(parents=True, exist_ok=True)
(out / "promos.json").write_text(json.dumps(promos, indent=2))
with open(out / "promos.csv", "w", newline="") as f:
    cols = ["rank", "score", "episode", "start", "end", "length", "hook", "cliffhanger", "why",
            "hook_score", "cliffhanger_score", "standalone_score", "spoiler", "failed_checks", "source"]
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for p in promos:
        w.writerow({**p, "start": pf.mmss(p["start"]), "end": pf.mmss(p["end"])})
print(f"Saved {len(promos)} promos to {out}/")
