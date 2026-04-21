# Model Manager

A standalone Python application to manage `llama.cpp` server models on remote Linux instances via SSH.

## Features
- **Dashboard**: Start, stop, and restart model services running via systemd.
- **Model Editor**: Edit `llama-server` flags directly from the UI without touching the remote shell.
- **Model Downloader**: Initiate HuggingFace downloads in detached `tmux` sessions and automatically generate `systemd` service files.

## Installation and Usage

You can download the pre-compiled binary from the [Releases](https://github.com/rapsalands/model-manager/releases) page.

```bash
# Download the binary
wget https://github.com/rapsalands/model-manager/releases/download/v1.0.0/model-manager

# Make it executable
chmod +x model-manager

# Run the app
./model-manager
```

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
pyinstaller model_manager.spec
```
