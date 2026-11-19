@echo off
cd /d "%~dp0"
echo Starting the local LSS research demo.
echo Open http://127.0.0.1:8765 in Chrome or Edge.
echo Keep this window open. Press Ctrl+C to stop the server.
python server.py --demo
pause
