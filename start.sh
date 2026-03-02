#!/usr/bin/env bash
# =====================================================
#  BREAKEON - Start script for Mac/Linux
# =====================================================

echo ""
echo "  ____                 _                    "
echo " | __ ) _ __ ___  __ _| | _____ ___  _ __  "
echo " |  _ \| '__/ _ \/ _\` | |/ / _ \ _ \| '_ \ "
echo " | |_) | | |  __/ (_| |   <  __/ (_) | | | |"
echo " |____/|_|  \___|\__,_|_|\_\___|\___/|_| |_|"
echo ""
echo "  Play games while Claude thinks."
echo "  Press Ctrl+C to stop."
echo ""

cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found. Install it from python.org or your package manager."
    exit 1
fi

# Figure out the right open command
if [[ "$OSTYPE" == "darwin"* ]]; then
    OPEN_CMD="open"
elif command -v xdg-open &> /dev/null; then
    OPEN_CMD="xdg-open"
else
    OPEN_CMD=""
fi

# Open browser after a short delay
if [ -n "$OPEN_CMD" ]; then
    (sleep 2 && $OPEN_CMD "http://localhost:3000") &
fi

# Start the server
python3 server.py
