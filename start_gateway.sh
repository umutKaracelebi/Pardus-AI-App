#!/bin/bash
# Start the qwen-free-api server for Pardus AI Assistant

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QWEN_DIR="$SCRIPT_DIR/qwen_free"
NODE=$(which node)

# Check if qwen-free-api is already running
if curl -s --max-time 3 "http://localhost:3264/api/status" > /dev/null 2>&1; then
    echo "✅ qwen-free-api zaten çalışıyor (port 3264)"
else
    echo "🚀 qwen-free-api başlatılıyor (port 3264)..."
    cd "$QWEN_DIR" && SKIP_ACCOUNT_MENU=true PORT=3264 "$NODE" index.js > /dev/null 2>&1 &

    # Wait for it to come up
    for i in {1..20}; do
        sleep 1
        if curl -s --max-time 2 "http://localhost:3264/api/status" > /dev/null 2>&1; then
            echo "✅ qwen-free-api hazır! (port 3264)"
            break
        fi
        if [ "$i" -eq 20 ]; then
            echo "❌ qwen-free-api başlatılamadı."
            exit 1
        fi
    done
fi

echo ""
echo "📡 Qwen API Durumu:"
echo "   API: http://localhost:3264/api"
echo "   Modeller: http://localhost:3264/api/models"
echo "   Durum: http://localhost:3264/api/status"
echo ""
