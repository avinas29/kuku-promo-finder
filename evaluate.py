"""Compare the tool's promos with a hand-made list of must-have moments.

  python3 evaluate.py outputs/keywords/promos.json

A moment counts as "found" if any promo from that episode contains its timestamp.
"""
import json
import sys

# (episode, seconds, what happens) - picked by reading all 50 screenplays
MUST_HAVE = [
    (1, 39, "Sister: 'Because he is marrying me' at the altar"),
    (3, 84, "Stranger knocks out the guard dragging Juliana"),
    (5, 55, "Stepmother throws mother's ledger into the mud"),
    (11, 95, "Constable pulls the planted gold watch from his coat"),
    (12, 66, "'Fail, or refuse, and your husband hangs'"),
    (13, 56, "Juliana crawls bare-handed into the thorns"),
    (16, 50, "Thug confesses: 'Gerald Harrington paid us!'"),
    (18, 87, "Burning beam crashes, he shields her"),
    (22, 124, "'This isn't ordinary fever'"),
    (23, 87, "'Someone is poisoning her... Arsenic'"),
    (24, 33, "Catherine strikes Juliana with a riding crop"),
    (26, 112, "Duchess: 'Where did you get this ring?'"),
    (27, 125, "Catherine twists her words: 'She admits... poison!'"),
    (31, 133, "Catherine burns the mother's book with a hot iron"),
    (32, 152, "Hot iron stops millimetres from her eye"),
    (36, 162, "'...and killing my wife afterward'"),
    (41, 82, "Cathedral doors explode mid-wedding"),
    (42, 13, "'Who are you?' 'You already know.'"),
    (44, 41, "He refuses Catherine's touch, walks to Juliana"),
    (45, 107, "Priest: 'You are not his lawful wife'"),
]

if __name__ == "__main__":
    promos = json.load(open(sys.argv[1]))
    found = 0
    for ep, t, what in MUST_HAVE:
        hit = [p for p in promos if p["episode"] == ep and p["start"] - 1 <= t <= p["end"] + 1]
        found += bool(hit)
        print(("FOUND " if hit else "MISSED") + f"  Ep{ep:>2} {what}" + (f"  (rank #{hit[0]['rank']})" if hit else ""))

    top20 = promos[:20]
    top_hits = sum(any(p["episode"] == ep and p["start"] - 1 <= t <= p["end"] + 1 for ep, t, _ in MUST_HAVE) for p in top20)
    print(f"\nMust-have moments found: {found}/{len(MUST_HAVE)}")
    print(f"Top-20 ranked promos that contain a must-have moment: {top_hits}/20")
