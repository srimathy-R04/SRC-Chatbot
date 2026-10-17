# SRC SmartBot — Setup Guide

A multilingual (English / Tamil / Telugu / Tanglish) chatbot that answers
questions about Srinivasa Ramanujan Centre (SRC), SASTRA, using only the
information in your `knowledge_base/` text files.

## Project layout

```
SRC Chatbot/
└── backend/
    ├── app.py              <- Flask server (chat endpoint)
    ├── rag.py               <- searches knowledge_base/*.txt for relevant text
    ├── index.html            <- chat UI (open this in a browser)
    ├── requirements.txt
    ├── .env                  <- holds your GEMINI_API_KEY (you create this)
    └── knowledge_base/
        ├── about_src.txt
        ├── contacts.txt
        ├── fees.txt
        ├── programmes.txt
        └── academic_calendar_2026-27.txt
```

`index.html` can live anywhere convenient — even outside `backend/` — since
it just calls `http://127.0.0.1:5000/chat` over the network. Keeping it next
to `app.py` is simplest.

## 1. Install dependencies

From inside `backend/`:

```
pip install -r requirements.txt
```

## 2. Add your Gemini API key

Create a file named `.env` inside `backend/` (same folder as `app.py`) with:

```
GEMINI_API_KEY=your_key_here
```

Get a key from https://aistudio.google.com/apikey if you don't have one yet.

## 3. Start the backend

```
cd backend
python app.py
```

You should see:

```
SRC SmartBot Backend is running!
```

in the terminal, and Flask will say it's listening on `http://127.0.0.1:5000`.
Leave this terminal running.

## 4. Open the chat UI

Double-click `index.html` (or right-click → Open with → your browser). No
separate server is needed for the frontend — it's a single self-contained
HTML file.

Try asking:
- `what is the fee for BTech CSE` (English)
- `BTech CSE fee evlo?` (Tanglish)
- a question typed in Tamil or Telugu script

The bot detects the language of your question and replies in the same
language, using only the facts in your knowledge_base files.

## Notes / known limits

- **Location questions** (e.g. "where is the library") are not yet
  supported — the knowledge base doesn't contain campus location data.
  Add that as a new `.txt` file (e.g. `campus_map.txt`) in `knowledge_base/`
  and it'll automatically be picked up by `rag.py` on the next server
  restart — no code changes needed.
- **CORS** is already enabled in `app.py` via `flask-cors`, so `index.html`
  can call the backend even though it's a local file, not a served page.
- If the frontend shows "Could not reach the SRC SmartBot server," it means
  `python app.py` isn't running, or it crashed — check that terminal first.
