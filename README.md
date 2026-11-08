# Promo Finder (Kuku AI Generalist Assignment, Problem 1)

**Live app:** https://avinas29-kuku-promo-finder-app-zmhns1.streamlit.app

Reads microdrama screenplays and finds the best 20-60 second promos: where to start, where to end,
the hook, the cliffhanger, why it works, and a ranking of which to post first.

## Run the website

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then in the browser:
1. Pick a provider in the sidebar (Gemini, Groq, OpenAI, Claude or Custom) and paste the API key.
   Any OpenAI-compatible API works: change the Base URL and Model name. No key? Pick "No API key".
2. Upload the episode `.txt` files (or paste one screenplay).
3. Click **Find promos**. Download the result as CSV or JSON.

## Run on a whole folder (terminal)

```bash
python3 run_folder.py <folder_with_txt_files> Gemini YOUR_KEY
python3 run_folder.py <folder_with_txt_files>          # no key: keyword method
```
Results go to `outputs/<model>/promos.csv` and `promos.json`.

## How it works (5 steps, all in `promo_finder.py`)

| Step | Who does it | What |
|---|---|---|
| 1. Parse | code | Read each screenplay into timed lines (dialogue, action, sound, camera) |
| 2. Ask AI | AI model | One episode at a time: "find the best promos, give start, end, hook, cliffhanger, scores" |
| 3. Snap | code | Move start/end to the nearest camera cut, so the editor can actually cut there |
| 4. Check | code | 20-60s? Something in first 3s? Ends right after a line? No line cut in half? Ad safe? |
| 5. Rank | code | 35% hook + 35% cliffhanger + 20% standalone + 10% early-episode bonus, minus failed checks |

Without an API key, step 2 uses a keyword method (dramatic words at the start and end of each window).

The input screenplays are Kuku's confidential content and are not in this repo.
