#!/bin/bash
# Pardus AI Asistanı – Evrensel Başlatıcı
# Bu script her yerden "pardus-ai" yazarak uygulamayı başlatmayı sağlar.

APP_DIR="/home/umut/pardus_ai_app"
VENV_PYTHON="$APP_DIR/venv/bin/python3"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Sanal ortam bulunamadı: $VENV_PYTHON"
    exit 1
fi

cd "$APP_DIR"

# CLI modu: pardus-ai --cli
# GUI modu (varsayılan): pardus-ai
exec "$VENV_PYTHON" main.py "$@"
