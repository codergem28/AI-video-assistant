# 🎬 AI Video Assistant

**Transcribe · Summarise · Chat with your meetings**

Turn a YouTube URL or a local audio/video file into a structured meeting report — title, summary, action items, key decisions and open questions — then chat with the transcript using RAG.

## How it works

1. **Audio** — downloads/extracts audio (yt-dlp → pydub → ffmpeg)
2. **Transcription** — local Whisper (`english`) or Sarvam STT which translates to English (`hinglish`)
3. **Analysis** — one LLM pass (`core/llm.py` → `core/analyzer.py`) produces title, summary, action items, key decisions and open questions
4. **RAG chat** — the transcript is embedded locally (Chroma + `all-MiniLM-L6-v2`) and questions are answered by the LLM with retrieval

## Prerequisites

- **Python 3.10+** (tested on 3.11)
- **FFmpeg** on your PATH — [ffmpeg.org](https://ffmpeg.org/download.html)
- A **free Groq API key** — [console.groq.com](https://console.groq.com) → *API Keys*

## Setup

```bash
git clone https://github.com/codergem28/AI-video-assistant.git
cd AI-video-assistant

python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r Requirements.txt
```

## Configure your API key (.env)

Create a file named `.env` in the project root (it is git-ignored — never commit it):

```
GROQ_API_KEY=gsk_your_key_here
```

| Key | Required? | Purpose |
|---|---|---|
| `GROQ_API_KEY` | **Yes** | Powers analysis + RAG chat via Groq |
| `GROQ_MODEL` | No | Override the default model (`qwen/qwen3.8-27b`) |
| `SARVAM_API_KEY` | Only for `hinglish` | Sarvam STT that translates Hindi → English |
| `WHISPER_MODEL` | No | Local Whisper size (default `small`) |
| `LLM_RPS` | No | Client rate limit, requests/sec (default `1.0`) |

> **Note:** The app originally used Mistral, but its free tier rate-limited every run (HTTP 429), so the LLM was switched to **Groq** (`qwen/qwen3.8-27b` by default). `MISTRAL_API_KEY` is no longer used.

## Run

**Streamlit UI:**

```bash
streamlit run app.py
```

**CLI:**

```bash
python main.py
```

Paste a YouTube URL or a local file path, pick a language, and hit **Analyse**. Once the report renders, use the chat box at the bottom to ask questions about the meeting.

## Project structure

```
app.py                  # Streamlit UI + pipeline orchestration
main.py                 # CLI entry point
core/
  llm.py                # ChatGroq factory + rate limiter + retry
  analyzer.py           # Single-pass report generation (title/summary/...)
  transcriber.py        # Whisper (local) / Sarvam (cloud) transcription
  rag_engine.py         # RAG chain (retriever + prompt + LLM)
  vector_store.py       # Chroma + HuggingFace embeddings
  summarizer.py         # Legacy map-reduce summariser
  extractor.py          # Legacy per-section extractors
utils/
  audio_processor.py    # Download / extract / chunk audio
Requirements.txt
```

## Troubleshooting

- **`429 Rate limit exceeded` (Mistral)** — legacy issue; the app now runs on Groq. Make sure `GROQ_API_KEY` is set.
- **`model_not_found` on Groq** — the configured model isn't available to your key; set `GROQ_MODEL` in `.env` to one your key can access.
- **`GROQ_API_KEY ... must be set`** — the `.env` file is missing or the key line is misspelled.
- **FFmpeg errors during audio processing** — install FFmpeg and make sure `ffmpeg -version` works in your terminal.
