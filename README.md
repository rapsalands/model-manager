# Model Manager

A standalone Python application to manage `llama.cpp` server models on remote Linux instances via SSH.

## Features
- **Dashboard**: Start, stop, and restart model services running via systemd.
- **Model Editor**: Edit `llama-server` flags directly from the UI without touching the remote shell.
- **Model Downloader**: Initiate HuggingFace downloads in detached `tmux` sessions and automatically generate `systemd` service files.

## Development

```bash
# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
python main.py
```

## Distribution

To build a standalone executable for distribution:
```bash
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --add-data "/path/to/customtkinter:customtkinter/" main.py
```
*(Note: PyInstaller requires pointing to the customtkinter module data path on your system)*
