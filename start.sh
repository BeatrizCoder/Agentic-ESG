#!/bin/bash
echo "🚀 Iniciando Agentic Support Platform..."
cd /home/beatriz/AAMAD
source .venv/bin/activate
uvicorn aamad.backend:app --reload --port 8000 --log-level info
