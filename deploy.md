# 🚀 Deployment Guide — AI Video Assistant

This guide covers every practical way to deploy this project, from a single developer machine to a public server.

---

## 1. What you are deploying

| Component | Tech | Notes |
|---|---|---|
| Web UI | Streamlit (`app.py`) | Default port **8501** |
| CLI | `main.py` | Interactive terminal app |
| Audio pipeline | `yt-dlp` + `pydub` + **FFmpeg** | Downloads/converts audio, splits into 10-min chunks |
| Transcription | local **Whisper** (default `small`) or Sarvam STT | Whisper downloads its model on first run |
| LLM | **Groq API** (`langchain-groq`) | Requires `GROQ_API_KEY`, network egress to `api.groq.com` |
| RAG | **Chroma** (`vector_db/`) + `all-MiniLM-L6-v2` | Embedding model downloads from HuggingFace on first run |

**Key deployment facts:**

- Python **3.10+** required (tested on 3.11).
- **FFmpeg binary must be installed on the host** (not just the pip package).
- First run downloads two models (~460 MB Whisper + ~90 MB embeddings) — plan disk/bandwidth or pre-warm.
- Runs fine on **CPU only** — no GPU required.
- The UI input takes a **YouTube URL or a server-side file path** (there is no file-upload widget), so on a hosted deployment the primary input is URLs.

---

## 2. Deployment options at a glance

| Option | Best for | Effort | Public URL |
|---|---|---|---|
| **A. Local machine** | Trying it out, personal use | Minutes | No |
| **B. Linux VPS (systemd + nginx)** | Self-hosting for a team | ~30 min | Yes |
| **C. Docker / Docker Compose** | Reproducible servers, any host | ~30 min | Yes |
| **D. Streamlit Community Cloud** | Free demo, zero ops | ~10 min | Yes |
| **E. Windows server / LAN** | Intranet use | ~20 min | LAN |

---

## 3. Prerequisites (all options)

- **Python 3.10+** — [python.org](https://www.python.org/downloads/)
- **FFmpeg** on `PATH`:
  ```bash
  # Debian/Ubuntu
  sudo apt update && sudo apt install -y ffmpeg
  # macOS
  brew install ffmpeg
  # Windows: download from https://ffmpeg.org/download.html and add to PATH
  ffmpeg -version   # must print a version
  ```
- **Groq API key** (free) — [console.groq.com](https://console.groq.com) → *API Keys*
- *(Optional)* **Sarvam API key** — only if you will use the `hinglish` language option

---

## 4. Environment configuration

Create a file named **`.env`** in the project root (same directory as `app.py`). It is git-ignored — **never commit it**.

```env
# Required
GROQ_API_KEY=gsk_your_key_here

# Optional overrides
GROQ_MODEL=qwen/qwen3.8-27b     # any Groq model your key can access
WHISPER_MODEL=small             # tiny | base | small | medium | large
LLM_RPS=1.0                     # client-side rate limit, requests/sec
SARVAM_API_KEY=                 # only needed for language = "hinglish"
SARVAM_STT_MODEL=saaras:v2.5
```

| Key | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | **Yes** | Powers analysis + RAG chat |
| `GROQ_MODEL` | No (default `qwen/qwen3.8-27b`) | Override LLM model |
| `WHISPER_MODEL` | No (default `small`) | Local Whisper size — use `tiny` on small hosts |
| `LLM_RPS` | No (default `1.0`) | LLM request rate limit |
| `SARVAM_API_KEY` | Only for `hinglish` | Hindi → English cloud STT |
| `SARVAM_STT_MODEL` | No (default `saaras:v2.5`) | Sarvam STT model |

> On servers, you can also inject these as **real environment variables** (systemd `Environment=`, Docker `-e`, host exports) — `python-dotenv` won't override variables that already exist.

---

## 5. Build & verify (common to Options A/B/C/E)

```bash
git clone https://github.com/codergem28/AI-video-assistant.git
cd AI-video-assistant

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
```

> ⚠️ `requirements.txt` installs PyTorch + Whisper — expect **2–3 GB** of installed packages and several minutes on a small VPS.

Pre-flight checks:

```bash
ffmpeg -version                          # FFmpeg present
python -c "import whisper, streamlit, chroma, yt_dlp; print('imports ok')"
```

Optional model pre-warm (removes first-request latency; saves models to disk):

```bash
python -c "import whisper; whisper.load_model('small')"
python -c "from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')"
```

Smoke test:

```bash
streamlit run app.py --server.port 8501
# then, in another terminal:
curl http://localhost:8501/_stcore/health     # expect: ok
```

---

## Option A — Local machine

```bash
source venv/bin/activate
streamlit run app.py        # UI at http://localhost:8501
# or
python main.py              # CLI
```

---

## Option B — Linux VPS (systemd + nginx)

Tested-style setup for Ubuntu/Debian. Assumes the app lives at `/opt/ai-video-assistant`.

### 1. Install system deps

```bash
sudo apt update && sudo apt install -y ffmpeg python3.11 python3.11-venv nginx
```

### 2. App user + code

```bash
sudo useradd -r -m -d /opt/ai-video-assistant appuser
sudo -u appuser git clone https://github.com/codergem28/AI-video-assistant.git /opt/ai-video-assistant/app
cd /opt/ai-video-assistant/app
sudo -u appuser python3.11 -m venv venv
sudo -u appuser venv/bin/pip install --upgrade pip
sudo -u appuser venv/bin/pip install -r requirements.txt
sudo -u appuser cp /path/on/your/machine/.env /opt/ai-video-assistant/app/.env
sudo chmod 600 /opt/ai-video-assistant/app/.env
```

### 3. systemd service

`/etc/systemd/system/ai-video-assistant.service`:

```ini
[Unit]
Description=AI Video Assistant (Streamlit)
After=network.target

[Service]
Type=simple
User=appuser
WorkingDirectory=/opt/ai-video-assistant/app
ExecStart=/opt/ai-video-assistant/app/venv/bin/streamlit run app.py \
          --server.port=8501 --server.address=127.0.0.1 --server.headless=true
Restart=on-failure
RestartSec=5
# Whisper + torch need headroom; raise if you use a larger WHISPER_MODEL
MemoryMax=3G

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ai-video-assistant
sudo systemctl status ai-video-assistant
```

### 4. nginx reverse proxy (HTTPS)

`/etc/nginx/sites-available/ai-video-assistant`:

```nginx
server {
    listen 80;
    server_name assistant.example.com;

    # Websocket upgrade headers are REQUIRED for Streamlit
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;   # long: transcription can take minutes
        client_max_body_size 50m;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/ai-video-assistant /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5. Firewall + TLS

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable

# TLS (free, auto-renewing)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d assistant.example.com
```

Your app is now live at `https://assistant.example.com`.

---

## Option C — Docker / Docker Compose

### Dockerfile

```dockerfile
FROM python:3.11-slim

# FFmpeg is mandatory (yt-dlp post-processing + pydub)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Optional: bake models into the image (adds ~600 MB, removes first-run downloads)
# RUN python -c "import whisper; whisper.load_model('small')" \
#  && python -c "from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')"

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
```

### docker-compose.yml

```yaml
services:
  app:
    build: .
    ports:
      - "8501:8501"
    env_file:
      - .env
    volumes:
      - ./vector_db:/app/vector_db         # persist Chroma data
      - hf-cache:/root/.cache/huggingface  # persist embedding model
      - whisper-cache:/root/.cache/whisper # persist Whisper model
    restart: unless-stopped

volumes:
  hf-cache:
  whisper-cache:
```

### Run

```bash
docker compose up -d --build
docker compose ps
curl http://localhost:8501/_stcore/health   # expect: ok
docker compose logs -f app
```

> **Note:** YouTube frequently changes its APIs — rebuild/pull the image periodically (`yt-dlp` is pinned by `>=`, so a fresh build picks up fixes).

---

## Option D — Streamlit Community Cloud (free)

Fastest way to get a public demo.

1. Push the repo to GitHub (this repo already ships lowercase `requirements.txt` and an `apt.txt`, so Streamlit Cloud detects everything automatically).
2. Go to [share.streamlit.io](https://share.streamlit.io) → *Create app* → pick the repo → main file path **`app.py`**.
3. Under **App settings → Secrets**, add:
   ```
   GROQ_API_KEY = "gsk_your_key_here"
   WHISPER_MODEL = "tiny"
   ```
4. Deploy. First boot downloads the Whisper + embedding models, so allow 2–5 minutes.

⚠️ **Caveats for this option:**

- Community Cloud has ~1 GB RAM — use `WHISPER_MODEL=tiny` (or `base`). `small` may run out of memory on long recordings.
- Model caches are **not persistent** across restarts → slower cold starts.
- Ephemeral disk → `vector_db` resets on restart (acceptable; it is rebuilt per analysis anyway).
- Long transcriptions can hit idle/time limits; very long videos may time out.

---

## Option E — Windows server / LAN

```powershell
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
# FFmpeg: install and add its bin folder to the system PATH

streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
```

- Open firewall port 8501: `netsh advfirewall firewall add rule name="Streamlit" dir=in action=allow protocol=TCP localport=8501`
- Other machines on the LAN reach it at `http://<your-ip>:8501`.
- For background/uncrashable operation, register it with **NSSM** or a Windows Task Scheduler "at startup" task:
  ```powershell
  nssm install AIVideoAssistant "C:\path\to\venv\Scripts\streamlit.exe" "run app.py --server.headless true --server.port 8501"
  nssm start AIVideoAssistant
  ```

---

## 6. Persistent data & caches

| Path | Contents | Persist? |
|---|---|---|
| `.env` | API keys | ✅ yes — keep out of git, chmod 600 |
| `vector_db/` | Chroma embeddings (git-ignored) | ⚠️ optional — rebuilt on each analysis |
| `~/.cache/whisper` | Whisper weights | ✅ recommended (volume/persistent disk) |
| `~/.cache/huggingface` | `all-MiniLM-L6-v2` embeddings | ✅ recommended |
| temp dirs (`video_assistant_*`) | Downloaded/chunked audio | ❌ auto-deleted after transcription (`cleanup_files`) |

Pre-download models onto a persistent volume at build time if your host has ephemeral disk (see Option C Dockerfile comments).

---

## 7. Security checklist

- [ ] `.env` is **never** committed (already in `.gitignore`) and is `chmod 600` on servers.
- [ ] Prefer **environment variables / secrets manager** over shipping `.env` files to hosts.
- [ ] Put the app behind **nginx + HTTPS**; do not expose port 8501 publicly if avoidable.
- [ ] Streamlit's XSRF/CORS protection is **on by default** — leave it on.
- [ ] Run as a **non-root** user (systemd `User=`, Docker non-root if you harden further).
- [ ] Restrict outbound access if required: egress needed for `api.groq.com`, `api.sarvam.ai`, YouTube, HuggingFace.
- [ ] This is currently a **single-user design** (shared session state and one `vector_db` collection) — do not expose it to untrusted users without adding auth (e.g., nginx `auth_basic`, OAuth proxy, or Streamlit's own auth options).

---

## 8. Post-deployment verification

Run these from your machine against the deployed host:

```bash
# 1. Health endpoint
curl https://assistant.example.com/_stcore/health          # → ok

# 2. UI loads
#    open https://assistant.example.com in a browser

# 3. End-to-end: paste a short YouTube URL in the sidebar → language "english" → Analyse
#    Expect the pipeline status dots in the sidebar to go green and a report to render.

# 4. RAG chat: ask "What were the main decisions?" in the chat box → get an answer.

# 5. Service health (VPS)
sudo systemctl status ai-video-assistant
journalctl -u ai-video-assistant -n 100 --no-pager
```

---

## 9. Updating a deployment

```bash
sudo systemctl stop ai-video-assistant       # or: docker compose stop app
cd /opt/ai-video-assistant/app
sudo -u appuser git pull
sudo -u appuser venv/bin/pip install -r requirements.txt
sudo systemctl start ai-video-assistant      # or: docker compose up -d --build
```

Keep `.env` out of the way of `git pull` (it is git-ignored, so it will never be overwritten).

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `GROQ_API_KEY ... must be set` | `.env` missing or not in working dir | Place `.env` next to `app.py`; check `WorkingDirectory` in systemd |
| `model_not_found` on Groq | Model unavailable to your key | Set `GROQ_MODEL` to a model your key can access |
| `429 Rate limit exceeded` | Legacy Mistral issue / too many LLM calls | Ensure `GROQ_API_KEY` is set; lower `LLM_RPS` |
| FFmpeg errors during download/convert | ffmpeg binary missing | `apt install ffmpeg` / `brew install ffmpeg`; verify `ffmpeg -version` |
| `SARVAM_API_KEY is not set` | `hinglish` selected without key | Set `SARVAM_API_KEY` or use `english` |
| Streamlit loads but UI is blank/spins behind nginx | Missing websocket upgrade headers | Copy the `proxy_set_header Upgrade/Connection` block exactly |
| `Killed` / OOM on long videos | Too little RAM for torch+Whisper | Use `WHISPER_MODEL=tiny`/`base`, add swap, or raise `MemoryMax` |
| First request takes minutes | Models downloading | Pre-warm at build time (Section 5) or bake into image |
| `yt-dlp` HTTP 403 / download errors | YouTube changed; stale yt-dlp | `pip install -U yt-dlp` and restart |
| Port unreachable | Firewall | Open 8501 (direct) or 80/443 (nginx) in `ufw`/cloud security group |
| Health check fails right after start | Slow model load | Increase `--start-period` / `RestartSec`; check `journalctl` |

---

## 11. Quick reference commands

```bash
# Local dev
streamlit run app.py
python main.py

# Production (server)
streamlit run app.py --server.port=8501 --server.address=127.0.0.1 --server.headless=true

# Health
curl http://localhost:8501/_stcore/health

# Docker
docker compose up -d --build && docker compose logs -f app
```
