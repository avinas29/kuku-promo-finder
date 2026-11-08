"""
Promo Finder: reads microdrama screenplays and finds the best 20-60 second promos.

How it works (5 simple steps):
  1. PARSE  - read each screenplay into a list of timed lines (code, no AI)
  2. ASK AI - send one episode at a time to an AI model, ask for the best promos
  3. SNAP   - move start/end to real camera cut points (code)
  4. CHECK  - test each promo with simple rules: length, hook, ending, safety (code)
  5. RANK   - give each promo one score and sort (code)

If no API key is given, step 2 uses a simple keyword method instead, so it always runs.
"""
import json
import re
import requests

# ---------------------------------------------------------------- 1. PARSE

TIME = re.compile(r"Start:\s*\((\d+):([\d.]+)\)\s*\|\s*End:\s*\((\d+):([\d.]+)\)")
HEADER = re.compile(r"^\*\*(.+?):\*\*\s*$")   # e.g. **CAMERA:**  or  **JULIANA (Angry):**


def to_seconds(minutes, seconds):
    return int(minutes) * 60 + float(seconds)


def mmss(t):
    """75.5 -> '01:15.50'"""
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def parse_screenplay(text, name="episode"):
    """Turn one screenplay file into {number, logline, lines:[{kind, who, start, end, text}]}."""
    rows = text.splitlines()
    number = re.search(r"Episode\s*(\d+)", text)
    logline = re.search(r"EPISODE LOGLINE:\s*(.*)", text)
    episode = {
        "number": int(number.group(1)) if number else 0,
        "name": name,
        "logline": logline.group(1).strip() if logline else "",
        "lines": [],
    }
    i = 0
    while i < len(rows) - 1:
        header = HEADER.match(rows[i].strip())
        times = TIME.search(rows[i + 1])
        if header and times:
            label = header.group(1)
            kind = label.split("(")[0].strip().upper()
            if kind not in ("CAMERA", "ACTION", "SOUND FX"):
                kind = "DIALOGUE"
            who = label.split("(")[0].strip() if kind == "DIALOGUE" else ""
            # the text is every non-empty line after the time line
            j, words = i + 2, []
            while j < len(rows) and rows[j].strip() and not HEADER.match(rows[j].strip()):
                words.append(rows[j].strip())
                j += 1
            episode["lines"].append({
                "kind": kind, "who": who, "text": " ".join(words).strip('"'),
                "start": to_seconds(*times.group(1, 2)), "end": to_seconds(*times.group(3, 4)),
            })
            i = j
        else:
            i += 1
    episode["lines"].sort(key=lambda x: x["start"])
    episode["length"] = max((x["end"] for x in episode["lines"]), default=0)
    return episode


def cut_points(episode):
    """An editor can only cut where a camera shot starts or ends."""
    points = {0.0, episode["length"]}
    for x in episode["lines"]:
        if x["kind"] == "CAMERA":
            points.update([x["start"], x["end"]])
    return sorted(points)


def script_text(episode, start=0, end=99999):
    """Readable script with timestamps (camera directions left out to save tokens)."""
    out = []
    for x in episode["lines"]:
        if x["kind"] == "CAMERA" or x["end"] < start or x["start"] > end:
            continue
        who = x["who"] if x["kind"] == "DIALOGUE" else x["kind"]
        out.append(f"[{mmss(x['start'])}-{mmss(x['end'])}] {who}: {x['text']}")
    return "\n".join(out)


# ---------------------------------------------------------------- 2. ASK AI

PROVIDERS = {  # all of these speak the same "OpenAI-compatible" format, so swapping is easy
    "Gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.1-flash-lite"),
    "Groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "OpenAI": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "Claude": ("https://api.anthropic.com/v1", "claude-sonnet-4-5"),
}

PROMPT = """You are a promo editor for short vertical drama apps like ReelShort and DramaBox.
Find the best promos in this episode. A promo is a 20-60 second clip cut straight from the show
and posted on Instagram, TikTok or YouTube to pull in new viewers.

A good promo:
1. HOOK: opens on something in the first 3 seconds that stops a scrolling viewer
   (a slap, a reveal, a shocking line). Never open on a slow, calm shot.
2. CLIFFHANGER: ends at an unresolved moment, so the viewer needs to know what happens next.
3. STANDALONE: makes sense to someone who has never seen the show.
Also say if it spoils a big twist, and if it has sexual or graphic content that ad platforms might reject.

Episode {number}. Summary: {logline}
Episode length: {length} seconds.

SCRIPT (times are MM:SS.ss):
{script}

Give up to {count} promos, best first. Use only times from the script.
Reply with JSON only, in exactly this shape:
{{"promos": [{{
  "start": "MM:SS.ss", "end": "MM:SS.ss",
  "hook": "what happens in the first 3 seconds",
  "cliffhanger": "the unresolved moment it ends on",
  "why": "one line on why it works",
  "hook_score": 1-10, "cliffhanger_score": 1-10, "standalone_score": 1-10,
  "spoiler": true or false, "ad_safe": true or false
}}]}}"""


def ask_ai(episode, api_key, base_url, model, count=2):
    """Send one episode to the AI and get back its promo ideas."""
    prompt = PROMPT.format(number=episode["number"], logline=episode["logline"],
                           length=round(episode["length"]), script=script_text(episode), count=count)
    reply = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "temperature": 0.2,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=120,
    )
    reply.raise_for_status()
    text = reply.json()["choices"][0]["message"]["content"]
    text = text[text.find("{"): text.rfind("}") + 1]      # keep only the JSON part
    promos = json.loads(text)["promos"]
    for p in promos:
        p["start"], p["end"] = read_time(p["start"]), read_time(p["end"])
        p["source"] = model
    return promos


def read_time(t):
    """'01:15.50' or 75.5 -> 75.5"""
    t = str(t).strip()
    if ":" in t:
        m, s = t.split(":")
        return to_seconds(m, s)
    return float(t)


# ------------------------------------------ 2b. NO-KEY FALLBACK (keywords)

DRAMA_WORDS = ["slap", "strike", "punch", "scream", "explo", "gasp", "knee", "ring", "poison",
               "arrest", "guard", "fire", "blood", "dead", "alive", "witch", "execut", "hang",
               "burn", "iron", "chain", "disown", "marry", "betray", "stole", "duke", "thorn",
               "drag", "whip", "sword", "kill", "die", "who are you", "not anymore", "!"]


def drama(line):
    t = line["text"].lower()
    return sum(t.count(w) for w in DRAMA_WORDS)


def keyword_promos(episode, count=2):
    """Try every legal 20-60s window; score = drama in the first 3s + drama in the last 6s."""
    cuts, lines = cut_points(episode), [x for x in episode["lines"] if x["kind"] != "CAMERA"]
    options = []
    for s in cuts:
        for e in cuts:
            if 20 <= e - s <= 60:
                opening = [x for x in lines if s <= x["start"] <= s + 3]
                closing = [x for x in lines if e - 6 <= x["end"] <= e]
                if opening and closing:
                    score = max(map(drama, opening)) + max(map(drama, closing))
                    score += 2 if e >= episode["length"] - 1 else 0  # episodes end on cliffhangers
                    options.append((score, s, e, opening[0], closing[-1]))
    options.sort(key=lambda o: o[0], reverse=True)
    picks = []
    for score, s, e, first, last in options:
        if all(e <= p["start"] or s >= p["end"] for p in picks):   # no overlaps
            sc = min(10, 3 + score)
            picks.append({"start": s, "end": e, "hook": first["text"], "cliffhanger": last["text"],
                          "why": "Keyword method: most dramatic words at the start and the end.",
                          "hook_score": sc, "cliffhanger_score": sc, "standalone_score": 5,
                          "spoiler": False, "ad_safe": True, "source": "keywords (no API key)"})
        if len(picks) == count:
            break
    return picks


# ----------------------------------------------------- 3. SNAP + 4. CHECK

UNSAFE_WORDS = ["naked", "bare chest", "shirtless", "carnal", "chemise", "in this bed"]


def snap_and_check(promo, episode):
    """Move start/end to the nearest camera cut, then run simple rule checks."""
    cuts = cut_points(episode)
    promo["proposed_start"], promo["proposed_end"] = promo["start"], promo["end"]   # keep what the AI said
    promo["start"] = min(cuts, key=lambda c: abs(c - promo["start"]))
    promo["end"] = min(cuts, key=lambda c: abs(c - promo["end"]))
    length = promo["end"] - promo["start"]
    inside = [x for x in episode["lines"] if x["kind"] != "CAMERA"
              and x["start"] >= promo["start"] - 0.01 and x["end"] <= promo["end"] + 0.01]
    all_text = " ".join(x["text"].lower() for x in inside)
    dialogue = [x for x in episode["lines"] if x["kind"] == "DIALOGUE"]

    promo["episode"] = episode["number"]
    promo["length"] = round(length, 1)
    promo["checks"] = {
        "20-60 seconds": 20 <= length <= 60,
        "something happens in first 3s": any(x["start"] <= promo["start"] + 3 for x in inside),
        "ends right after a line/action": any(x["end"] >= promo["end"] - 4 for x in inside),
        "no line cut in half": not any(x["start"] < c < x["end"] - 0.05
                                       for x in dialogue for c in (promo["start"], promo["end"])),
        "ad safe": bool(promo.get("ad_safe", True)) and not any(w in all_text for w in UNSAFE_WORDS),
    }
    promo["script"] = script_text(episode, promo["start"], promo["end"])
    return promo


# ------------------------------------------------------------------ 5. RANK

def rank(promos, total_episodes):
    """One score per promo. Higher = post it first."""
    for p in promos:
        early_bonus = 10 * (1 - (p["episode"] - 1) / max(total_episodes, 1))  # new viewers start at Ep 1
        score = (0.35 * float(p["hook_score"]) + 0.35 * float(p["cliffhanger_score"])
                 + 0.2 * float(p["standalone_score"]) + 0.1 * early_bonus)
        if p.get("spoiler"):
            score -= 1.5
        failed = [name for name, ok in p["checks"].items() if not ok]
        score -= 2 * len(failed)
        if not p["checks"]["ad safe"]:
            score -= 20                       # never post first
        p["score"] = round(score, 2)
        p["failed_checks"] = ", ".join(failed)
    promos.sort(key=lambda p: p["score"], reverse=True)
    for i, p in enumerate(promos, 1):
        p["rank"] = i
    return promos


# --------------------------------------------------------------- ALL TOGETHER

def find_promos(episodes, api_key="", base_url="", model="", count=2, on_progress=None):
    """Run all 5 steps on a list of parsed episodes."""
    results = []
    for n, ep in enumerate(episodes, 1):
        if api_key:
            try:
                ideas = ask_ai(ep, api_key, base_url, model, count)
            except Exception as err:            # one bad reply should not stop the whole show
                print(f"Episode {ep['number']}: AI failed ({err}); using keywords")
                ideas = keyword_promos(ep, count)
        else:
            ideas = keyword_promos(ep, count)
        results += [snap_and_check(p, ep) for p in ideas]
        if on_progress:
            on_progress(n, len(episodes))
    total = max((e["number"] for e in episodes), default=1)
    return rank(results, total)
