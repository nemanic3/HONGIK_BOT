#!/bin/zsh
set -eu
cd "${0:A:h}"
if lsof -nP -iTCP:3000 -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  print "Port 3000 or 8000 is already in use. HONGIK_BOT: http://127.0.0.1:3000"
  exit 1
fi
export TRANSCRIPT_PROCESSING=inline
export TRANSCRIPT_IMAGE_OCR_PROVIDER=transcripts.vision_provider.recognize_png
backend/.venv/bin/python backend/manage.py runserver 127.0.0.1:8000 --noreload &
backend_pid=$!
npm --prefix "frontend/team4-frontend-dev copy" run dev -- --hostname 127.0.0.1 &
frontend_pid=$!
trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM
print "HONGIK_BOT: http://127.0.0.1:3000 — leave this terminal open; Ctrl+C stops both servers."
wait
