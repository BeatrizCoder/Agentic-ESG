#!/bin/bash
echo ""
echo "Agentic Support Platform"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd /home/beatriz/AAMAD

# Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "   Copy .env.example to .env and add your keys"
    exit 1
fi

# Activate venv
source .venv/bin/activate

# Check API keys
if ! grep -q "ANTHROPIC_API_KEY=sk-" .env 2>/dev/null; then
    echo "WARNING: ANTHROPIC_API_KEY may not be set in .env"
fi

# Kill existing processes
pkill -f uvicorn 2>/dev/null
pkill -f "http.server 5500" 2>/dev/null
sleep 1

# Start backend
echo "Starting FastAPI backend..."
uvicorn aamad.backend:app --reload --port 8000 &
BACKEND_PID=$!
sleep 3

# Health check
if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "Backend ready: http://127.0.0.1:8000"
else
    echo "ERROR: Backend failed to start! Check terminal for errors."
    exit 1
fi

# Start frontend
echo "Starting frontend server..."
python3 -m http.server 5500 &
FRONTEND_PID=$!
sleep 1
echo "Frontend ready: http://localhost:5500/index.html"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Platform ready!"
echo ""
echo "  Customer Portal:   http://localhost:5500/index.html"
echo "  Operator Dashboard: same URL -> click 'Operator View'"
echo "  API Docs:          http://127.0.0.1:8000/docs"
echo ""
echo "  Press Ctrl+C to stop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Keep running
wait
