#!/bin/bash

# Pardus AI Asistanı Başlatıcı Scripti
# Bu scripti Klavye Kısayolları ayarlarından Ctrl+Alt+M tuşuna bağlayabilirsiniz.

# Absolute path to the script directory
SCRIPT_DIR="$(dirname "$(realpath "$0")")"
cd "$SCRIPT_DIR"

# Activate virtual environment and run the script
# We explicitly call a terminal emulator to ensure it opens in a new window
# Try different terminal emulators
if command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- bash -c "./venv/bin/python3 main.py --chat; exec bash"
elif command -v xfce4-terminal &> /dev/null; then
    xfce4-terminal --execute bash -c "./venv/bin/python3 main.py --chat; exec bash"
elif command -v x-terminal-emulator &> /dev/null; then
    x-terminal-emulator -e bash -c "./venv/bin/python3 main.py --chat; exec bash"
elif command -v konsole &> /dev/null; then
    konsole -e bash -c "./venv/bin/python3 main.py --chat; exec bash"
else
    # Fallback: try to just run it, assuming it's already in a terminal or user handles it
    ./venv/bin/python3 main.py --chat
fi
