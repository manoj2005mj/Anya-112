# Anya — 112 Emergency Dispatch Agent · Handoff Document

> **Date:** 2026-02-23  
> **Status:** Core architecture complete — ready for integration testing  
> **Model:** `gemini-2.5-flash-native-audio-preview-12-2025` (single model for everything)

---

## 1. Project Overview

**Anya** is a real-time emergency dispatch agent for India's 112 system. A caller connects via a browser, speaks (or types), and Anya:

1. Responds with **voice** (via Gemini Live API native audio)
2. Extracts structured emergency data (location, disaster type, severity, departments)
3. Updates a **live dashboard** with a map, department badges, and threat level
4. Accepts **image uploads** for visual emergency assessment
5. Receives **RAG context injections** (simulated system updates) mid-conversation

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│                     Browser (React)                  │
│  Dashboard.tsx  ←→  WebSocket  ←→  voice.py (relay)  │
│       │                                    │         │
│       │ REST fallback (/chat, /image)      │         │
│       └──────────► FastAPI ◄───────────────┘         │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
              Gemini Live API Session
        (single model, single session per call)
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single model** (`gemini-2.5-flash-native-audio-preview-12-2025`) for Live API, REST chat, and image analysis | Unified behaviour, consistent capabilities, no model drift |
| **Single Live session per WebSocket** | All audio + typed text + RAG updates share context in one session |
| **Backend relay** (browser → FastAPI → Gemini) | API key stays server-side; enables logging, rate limiting, RAG injection |
| **REST fallback** for text chat | Graceful degradation when WebSocket is unavailable |
| **REST for image upload** | Images are uploaded via `multipart/form-data` → Gemini Files API; result is also injected into the Live session for context continuity |

---

## 3. File Map

### Backend (Python / FastAPI)

| File | Purpose |
|------|---------|
| `main.py` (root) | Entry point — runs `uvicorn app.main:app --reload` on port 8000 |
| `app/main.py` | FastAPI app creation, CORS config, router mounting, logging setup |
| `app/config.py` | Pydantic Settings — reads `GEMINI_API_KEY` from `.env` |
| `app/services/gemini.py` | **Core** — Gemini client, system prompt, model constant (`MODEL`), `LIVE_CONNECT_CONFIG`, REST helpers (`get_chat_response`, `get_image_analysis`) |
| `app/routers/voice.py` | WebSocket `/voice/ws` — bidirectional relay between browser and Gemini Live API session |
| `app/routers/chat.py` | REST `POST /chat` — text-only fallback via `get_chat_response()` |
| `app/routers/image.py` | REST `POST /image` — accepts image upload, calls `get_image_analysis()` |

### Frontend (React / TypeScript / Vite)

| File | Purpose |
|------|---------|
| `src/main.tsx` | React entry point |
| `src/App.tsx` | Renders `<Dashboard />` |
| `src/components/Dashboard.tsx` | **Core UI** — WebSocket lifecycle, audio recording (push-to-talk), text input, image upload, PCM audio playback (Web Audio API), transcript display, JSON extraction for dashboard updates, REST fallback |
| `src/components/LiveMap.tsx` | Leaflet map with dark tiles, incident marker, fly-to animation |
| `src/components/DepartmentBadges.tsx` | Severity bar + department badge grid (Police, Fire, Ambulance, etc.) |
| `src/lib/gemini.ts` | REST `/chat` fallback client — used only when WebSocket is down |

### Config

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python deps (FastAPI, google-genai, uvicorn, pydantic-settings, python-multipart) |
| `package.json` | Node deps (React 19, Vite, Tailwind CSS v4, Leaflet, Framer Motion, Lucide, react-markdown) |
| `vite.config.ts` | Vite + React + Tailwind plugin |
| `tsconfig.json` | TypeScript config |
| `.env` | `GEMINI_API_KEY=…` (not committed) |

---

## 4. How to Run

### Prerequisites

- **Python 3.12+** with `uv` (or `pip`)
- **Node.js 18+** with `npm`
- A **Gemini API key** with access to `gemini-2.5-flash-native-audio-preview-12-2025`

### Steps

```bash
# 1. Clone & enter
cd /home/victus/Desktop/anya

# 2. Create .env
echo "GEMINI_API_KEY=your-key-here" > .env

# 3. Install Python deps
uv sync              # or: pip install -e .

# 4. Start backend
python main.py       # → http://localhost:8000

# 5. Install frontend deps (separate terminal)
npm install

# 6. Start frontend
npm run dev          # → http://localhost:3000
```

Open **http://localhost:3000** in Chrome (microphone + Web Audio API required).

---

## 5. Data Flow (detailed)

### 5a. Voice Conversation

```
Browser mic  →  MediaRecorder (webm/opus, 100ms chunks)
             →  base64 encode
             →  WebSocket { realtime_input: { media_chunks: [...] } }
             →  voice.py: session.send_realtime_input(audio=Blob(...))
             →  Gemini Live API processes audio
             →  session.receive() yields:
                  • inline_data (PCM audio)  → WS { audio: "base64" }  → playPcmChunk()
                  • output_transcription     → WS { transcript: "..." } → chat bubble
                  • input_transcription      → WS { input_transcript: "..." } → replaces "🎤 Speaking…"
                  • turn_complete            → WS { turn_complete: true } → flush buffers
```

### 5b. Typed Text

```
User types + Enter  →  WS { text: "..." }
                    →  voice.py: session.send_client_content(turns=Content(...))
                    →  same Gemini session responds (audio + transcript)
                    →  same flow as above
```

### 5c. Image Upload

```
User selects image  →  POST /image (multipart/form-data)
                    →  image.py: saves temp file → get_image_analysis()
                    →  gemini.py: client.files.upload() → client.models.generate_content()
                    →  response text returned to frontend
                    →  Dashboard also injects result into Live session via WS { text: "[Image analysis result]: ..." }
```

### 5d. RAG Injection (simulated)

```
After 45 seconds (if >2 messages):
  Dashboard sends WS { text: "SYSTEM UPDATE: ..." }
  →  voice.py forwards to Gemini session as user turn
  →  Anya weaves the update into her next spoken response
```

### 5e. REST Fallback

```
If WebSocket is down:
  User types + Enter  →  gemini.ts: POST /chat { message, history }
                      →  chat.py → get_chat_response() → REST Gemini API
                      →  response displayed as chat bubble (no audio)
```

---

## 6. Gemini Configuration

### Model

```python
MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
```

Used for **all** code paths: Live API session, REST chat, and image analysis.

### Live Connect Config

```python
LiveConnectConfig(
    response_modalities  = [Modality.AUDIO],          # model speaks back
    speech_config        = SpeechConfig(voice="Aoede"),# female voice
    system_instruction   = Content(text=SYSTEM_INSTRUCTION),
    output_audio_transcription = AudioTranscriptionConfig(),  # what Anya said
    input_audio_transcription  = AudioTranscriptionConfig(),  # what user said
    enable_affective_dialog    = True,                 # emotion-aware
)
```

### System Prompt Highlights

- **Persona:** Calm, professional Indian female dispatch agent
- **Turn structure:** Acknowledge → Safety instruction → One follow-up question
- **Multi-language:** Defaults to English, responds in Hindi/Tamil/Telugu if spoken to
- **RAG-aware:** Seamlessly incorporates `SYSTEM UPDATE:` injections
- **NER extraction:** Outputs JSON block at the end of every response with:
  - `incident_location`, `disaster_type`, `departments_required`, `severity`, `extracted_entities`

---

## 7. Frontend Dashboard Details

### State Management

| State | Purpose |
|-------|---------|
| `messages` | Chat history (user, model, system) |
| `extractedData` | Parsed NER JSON → drives map, badges, severity bar |
| `isRecording` | Push-to-talk active |
| `isProcessing` | Waiting for model response |
| `wsConnected` | WebSocket connection status (shown as LIVE/OFFLINE) |
| `audioEnabled` | Toggle speaker output |
| `permissionGranted` | Microphone permission obtained |

### Audio Playback

- Gemini Live returns **24 kHz, 16-bit, mono PCM** audio
- Decoded from base64 → `Float32Array` → `AudioBuffer` → scheduled via Web Audio API
- Chunks are queued sequentially (`nextPlayTime`) to avoid overlap
- Queue resets on `turn_complete`

### JSON Extraction

The `parseResponse()` function looks for ` ```json ... ``` ` blocks in Anya's transcript, parses them, and merges into `extractedData` (departments and entities are union-merged to accumulate over the conversation).

---

## 8. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `WS` | `/voice/ws` | Bidirectional Live API relay (primary path) |
| `POST` | `/chat/` | REST text chat fallback |
| `POST` | `/image/` | Image upload + analysis |
| `GET` | `/` | Health check (returns `{ status: "ok" }`) |
| `GET` | `/health` | Health check |

---

## 9. Known Limitations & Future Work

### Current Limitations

1. **Image upload is REST-only** — images go through a separate `generate_content` call, not the Live session directly. The result is injected into the session as text for context continuity.
2. **RAG is simulated** — the 45-second timer injects a hardcoded system update. Replace with a real vector database query (e.g., from an emergency protocols database).
3. **No persistent session** — refreshing the browser starts a new Gemini Live session (no conversation history recovery).
4. **Single concurrent call** — each WebSocket connection creates its own Live session; there's no dispatcher queue or multi-agent orchestration.
5. **Location is placeholder** — the map always defaults to New Delhi coordinates. Real geocoding from extracted location text is not yet implemented.
6. **Linter warnings on `LiveConnectConfig`** — Pylance/Pyright type stubs don't recognize some fields (`response_modalities`, `speech_config`, etc.) but they are valid at runtime (confirmed via SDK introspection).

### Suggested Next Steps

- [ ] **Real geocoding** — use Google Maps Geocoding API to convert extracted location text → lat/lng
- [ ] **RAG pipeline** — connect to a vector DB (e.g., Pinecone, Weaviate) of emergency SOPs and inject relevant protocols
- [ ] **Multi-language TTS** — test and configure voices for Hindi, Tamil, Telugu
- [ ] **Call recording** — save audio streams for audit/training
- [ ] **Department dispatch API** — integrate with actual 112 dispatch systems
- [ ] **Authentication** — add auth for dispatch operators
- [ ] **Session persistence** — store conversation state in Redis for reconnection
- [ ] **Load testing** — verify concurrent WebSocket sessions under load
- [ ] **Production deployment** — Dockerize, add HTTPS/WSS, deploy behind a reverse proxy

---

## 10. Dependencies

### Python (`pyproject.toml`)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ≥0.131.0 | Web framework |
| `google-genai` | ≥1.64.0 | Gemini SDK (Live API + REST) |
| `uvicorn[standard]` | ≥0.41.0 | ASGI server with WebSocket support |
| `pydantic-settings` | ≥2.13.1 | Settings from `.env` |
| `python-dotenv` | ≥1.2.1 | `.env` file loading |
| `python-multipart` | ≥0.0.22 | File upload parsing |

### Node.js (`package.json`)

| Package | Purpose |
|---------|---------|
| `react` / `react-dom` 19 | UI framework |
| `vite` 6 | Dev server + bundler |
| `tailwindcss` 4 | Styling |
| `leaflet` / `react-leaflet` | Map component |
| `motion` (Framer Motion) | Animations |
| `lucide-react` | Icons |
| `react-markdown` | Markdown rendering in chat |
| `clsx` | Conditional class names |
| `@google/genai` | (Installed but unused — all Gemini calls go through backend) |

---

## 11. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Google AI Studio API key with access to the native audio preview model |

Set in `.env` at project root. Read by `app/config.py` via Pydantic Settings.

---

*End of handoff.*
