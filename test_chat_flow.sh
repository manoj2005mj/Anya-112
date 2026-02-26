#!/bin/bash

echo "=========================================="
echo "Testing Server2 Chat Function Flow"
echo "=========================================="
echo ""

# Start server in background
python -m server2.main &
SERVER_PID=$!
echo "Server started (PID: $SERVER_PID)"
echo "Waiting for server to be ready..."
sleep 4

echo ""
echo "=========================================="
echo "Sending chat request..."
echo "=========================================="
echo ""

# Make chat request
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "There is a fire at my house, please help!", "history": null}' | python3 -m json.tool | head -20

echo ""
echo ""
echo "=========================================="
echo "Server logs (function calls):"
echo "=========================================="

# Wait a bit and show server output
sleep 2
echo ""
echo "Done. Stopping server..."
kill $SERVER_PID 2>/dev/null
