# LiveKit Agents Backend (server2/)

A completely separate FastAPI backend that integrates **LiveKit Agents** with custom tools for real-time emergency response coordination.

## What is server2/?

This is a **new, independent backend server** that runs alongside your existing `app/main.py` backend. It does **not modify any existing code**.

## Folder Structure

```
server2/
├── __init__.py          # Package initialization
├── main.py              # FastAPI app entry point (port 8000)
├── worker.py            # LiveKit worker entry point
├── config.py            # Configuration/Settings
├── models.py            # Pydantic data models
├── events.py            # Event broadcasting system
├── tools/               # Custom tools directory
│   ├── __init__.py
│   └── registry.py      # rack_tool, alert_tool
├── agents/              # LiveKit agents directory
│   ├── __init__.py
│   └── emergency.py     # EmergencyDispatchAgent
└── routers/             # FastAPI routers
    ├── __init__.py
    ├── alerts.py        # Alert endpoints
    ├── racks.py         # Rack data endpoints
    └── events.py        # WebSocket & SSE endpoints
```

## Features

- ✅ **FastAPI Backend** - RESTful API with async/await
- ✅ **LiveKit Agents Integration** - Voice AI agent with custom tools
- ✅ **Custom Tools** - `rack_tool` and `alert_tool` for emergency operations
- ✅ **Real-time Events** - WebSocket and SSE endpoints for tool invocations
- ✅ **Clean Architecture** - Modular, separated concerns
- ✅ **HTTP Endpoints** - Manual trigger endpoints for testing

## Installation

1. Install the required dependencies:

```bash
pip install "livekit-agents>=0.12.0" aiohttp>=3.10.0
```

Or using pip with the optional dependencies:

```bash
pip install -e ".[livekit]"
```

2. Copy the environment example and configure:

```bash
cp .env.example.server2 .env
# Edit .env with your LiveKit credentials
```

## Configuration

Add the following to your `.env` file:

```bash
# LiveKit Configuration
LIVEKIT_URL="wss://your-cluster.livekit.cloud"
LIVEKIT_API_KEY="your_livekit_api_key"
LIVEKIT_API_SECRET="your_livekit_api_secret"
LIVEKIT_ROOM_NAME="emergency-room"

# Server Configuration
HOST="0.0.0.0"
PORT="8000"

# LLM Configuration (for LiveKit Agents)
LLM_MODEL="gpt-4o"
LLM_API_KEY="your_openai_api_key"
LLM_PROVIDER="openai"

# External API Configuration
RACK_API_BASE_URL="https://api.example.com/racks"
ALERT_WEBHOOK_URL=""
```

## Running the Server

### Option 1: Run FastAPI Server (HTTP Endpoints)

```bash
# Run directly
python -m server2.main

# Or using uvicorn
uvicorn server2.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start on `http://localhost:8000`

### Option 2: Run LiveKit Worker (Voice Agent)

```bash
# Using LiveKit CLI
livekit-agent run --url $LIVEKIT_URL --api-key $LIVEKIT_API_KEY --api-secret $LIVEKIT_API_SECRET

# Or specify the worker entrypoint
livekit-agent run --url $LIVEKIT_URL --api-key $LIVEKIT_API_KEY --api-secret $LIVEKIT_API_SECRET server2/worker.py
```

## API Endpoints

### HTTP Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Server information |
| GET | `/health` | Health check |
| POST | `/alerts/trigger` | Trigger an emergency alert |
| POST | `/racks/query` | Fetch rack data from external API |
| GET | `/events/history` | Get tool invocation history |
| GET | `/livekit/status` | LiveKit agent server status |

### WebSocket & SSE

| Endpoint | Type | Description |
|----------|------|-------------|
| `/events/ws` | WebSocket | Real-time tool invocation events |
| `/events/sse` | SSE | Server-Sent Events for tool events |

## Frontend Integration

### WebSocket Example

```typescript
const ws = new WebSocket('ws://localhost:8000/events/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Tool event:', data);

  // Handle different event types
  switch (data.event_type) {
    case 'tool_invoked':
      console.log(`Tool ${data.tool_name} was invoked`);
      break;
    case 'tool_completed':
      console.log(`Tool ${data.tool_name} completed successfully`);
      break;
    case 'tool_failed':
      console.error(`Tool ${data.tool_name} failed:`, data.error);
      break;
    case 'agent_started':
      console.log('LiveKit agent session started');
      break;
    case 'agent_stopped':
      console.log('LiveKit agent session ended');
      break;
  }
};
```

### Server-Sent Events Example

```typescript
const eventSource = new EventSource('http://localhost:8000/events/sse');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Tool event:', data);
};
```

### Manual Alert Trigger Example

```typescript
const triggerAlert = async () => {
  const response = await fetch('http://localhost:8000/alerts/trigger', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      incident_type: 'fire',
      location: '123 Main Street, Building 5',
      severity: 'high',
      description: 'Fire reported in the server room',
      coordinates: [12.9716, 77.5946] // [lat, lng]
    })
  });

  const result = await response.json();
  console.log('Alert triggered:', result);
};
```

## Event Format

All events follow this JSON structure:

```json
{
  "event_type": "tool_invoked | tool_completed | tool_failed | agent_started | agent_stopped",
  "tool_name": "rack_tool | alert_tool | agent_lifecycle",
  "timestamp": "2026-02-25T12:34:56.789Z",
  "payload": {
    // Event-specific data
  },
  "error": "null or error message"
}
```

## Custom Tools

### rack_tool

Fetches rack data from external database/API.

**Parameters:**
- `query` (str): Search query for rack data
- `rack_id` (optional str): Specific rack identifier
- `location` (optional str): Location filter
- `department` (optional str): Department filter

**Returns:**
```json
{
  "racks": [
    {
      "rack_id": "RACK-001",
      "location": "Data Center A",
      "department": "IT",
      "status": "operational",
      "temperature": 22.5,
      "power_usage": 450,
      "last_updated": "2026-02-25T12:34:56.789Z"
    }
  ],
  "query": "server status",
  "total": 1
}
```

### alert_tool

Triggers emergency alerts when AI detects incidents.

**Parameters:**
- `incident_type` (str): Type of emergency (fire, medical, accident, crime, etc.)
- `location` (str): Location description
- `severity` (str): Severity level (low, medium, high, critical)
- `description` (optional str): Additional details
- `coordinates` (optional list): [latitude, longitude]

**Returns:**
```json
{
  "success": true,
  "alert_id": "ALT-20260225123456",
  "message": "Emergency alert 'fire' has been triggered for 123 Main Street",
  "data": {
    "alert_id": "ALT-20260225123456",
    "incident_type": "fire",
    "location": "123 Main Street",
    "severity": "high",
    "description": "Fire in server room",
    "coordinates": [12.9716, 77.5946],
    "timestamp": "2026-02-25T12:34:56.789Z",
    "status": "active"
  }
}
```

## Architecture

```
server2/
├── main.py           # FastAPI app entry point
├── worker.py         # LiveKit worker entry point
├── config.py         # Settings configuration
├── models.py         # Pydantic models
├── events.py         # EventBroadcaster (WebSocket manager)
├── tools/
│   └── registry.py   # ExternalDataTools (rack_tool, alert_tool)
├── agents/
│   └── emergency.py  # EmergencyDispatchAgent
└── routers/
    ├── alerts.py     # Alert endpoints
    ├── racks.py      # Rack data endpoints
    └── events.py     # WebSocket & SSE endpoints
```

## Notes

- This server runs on port 8000 (configurable via `PORT` env var)
- The original backend (app/main.py) is not modified
- Both servers can run simultaneously
- LiveKit credentials are required for agent functionality
- The agent will work with HTTP endpoints even without LiveKit configured

## References

- [LiveKit Agents - External Data and RAG](https://docs.livekit.io/agents/logic/external-data/)
- [LiveKit Agents - Agent Builder](https://docs.livekit.io/agents/start/builder/)
- [LiveKit Python SDK](https://docs.livekit.io/agents/frameworks/python/)
