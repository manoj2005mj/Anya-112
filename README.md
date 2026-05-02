# Anya

Anya is an AI-assisted emergency dispatch dashboard for India's `112` response workflow. A caller can type, speak, or upload an image, and the system turns that conversation into actionable dispatch data:

- incident location
- incident type
- threat level
- active response units
- nearest responding facility and ETA

## The Problem We Are Solving

During an emergency call, operators lose time when critical details stay trapped inside free-form conversation. The goal of this project is to convert messy human input into a live operational view that helps dispatch teams react faster and more consistently.

## How Anya Solves It

1. The frontend captures text, voice, and images from the caller.
2. The backend uses Gemini to generate a calm response and extract incident metadata.
3. A normalization layer fills in missing structure so the UI still works even if the model responds imperfectly.
4. The dashboard updates the live map, threat level, active units, and routing ETA.
5. Routing services find the nearest relevant emergency facility and draw the response path.

## Stack

- Frontend: React, TypeScript, Vite, Tailwind CSS, Leaflet
- Backend: FastAPI, Gemini, HTTPX
- Mapping and routing: OpenStreetMap, Nominatim, Overpass, OSRM

## Project Structure

```text
src/
  components/        Frontend dashboard, map, routing modal, unit badges
  lib/               Frontend API helpers
app/                 Older lightweight backend
server2/             Main backend used by the dashboard
main.py              Default backend entrypoint
```

## Run Locally

### Prerequisites

- Python `3.12+`
- Node.js `18+`
- A valid `GEMINI_API_KEY` in `.env`

### 1. Install dependencies

```bash
uv sync
npm install
```

### 2. Configure environment

Create `.env` with at least:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

Optional keys for voice and LiveKit can also be added if you use those features.

### 3. Start the backend

```bash
uv run python main.py
```

This starts the full backend on `http://localhost:8000`.

### 4. Start the frontend

```bash
npm run dev
```

Open `http://localhost:3000`.

## Main API Endpoints

- `POST /chat` for conversational emergency intake
- `POST /image` for image-based incident analysis
- `POST /routing/route` for nearest facility lookup and ETA
- `GET /health` for backend health

## Notes

- The routing and map enrichment features rely on internet access to OpenStreetMap-based services.
- If the model omits structured data, the backend now adds a normalized JSON block so the dashboard can still render correctly.

## Current Focus

The app is optimized for fast emergency triage:

- calm caller interaction
- structured incident extraction
- automatic unit suggestion
- live dispatch visualization
- route and ETA awareness
