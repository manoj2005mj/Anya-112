#!/bin/bash

echo "=============================================="
echo "Server2 Function Call Flow Viewer"
echo "=============================================="
echo ""

# Start server
echo "Starting server..."
python -m server2.main 2>&1 &
SERVER_PID=$!

# Wait for startup
echo "Waiting for server to start..."
sleep 5

echo ""
echo "=============================================="
echo "Server is running. Press Ctrl+C to stop."
echo "=============================================="
echo ""
echo "You will now see:"
echo "  [RAG] - RAG initialization and queries"
echo "  [CHAT] - Chat request processing"
echo "  [TOOL] - Tool calls (rack_tool, alert_tool)"
echo ""

# Test with a sample request
echo "Making sample chat request..."
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Fire emergency", "history": null}' > /dev/null 2>&1

sleep 3

echo ""
echo "Server running. Press Ctrl+C to stop..."
echo ""

# Keep server running until Ctrl+C
wait $SERVER_PID
