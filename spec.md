# Model Manager - Specification Document

## Overview
Model Manager is a standalone Python application designed to manage `llama-server` instances running as `systemd` services on a remote server. It provides a graphical user interface for starting, stopping, restarting, and configuring these services, as well as downloading new models from HuggingFace.

## Architecture

The application follows a modular architecture, separating the User Interface, SSH communication layer, and configuration parsing logic.

### 1. User Interface (`main.py`)
- **Framework**: Built using `customtkinter` for a modern, dark-themed UI.
- **Components**:
  - `LoginDialog`: Prompts for SSH credentials (Host, Username, Key Path) and an optional `sudo` password.
  - `DashboardTab`: Discovers and displays all model services. Provides Start, Stop, Restart, and Edit controls.
  - `EditorWindow`: An auto-generated form for editing `llama-server` execution flags.
  - `AddModelTab`: Interface to initiate a model download in a detached `tmux` session and generate a `systemd` template.

### 2. Communication Layer (`ssh_manager.py`)
- **Framework**: `paramiko`
- **Functionality**: Maintains an active SSH session. Handles command execution securely.
- **Sudo Handling**: Instead of requiring `visudo` modifications, the manager accepts the user's sudo password and uses `echo '<password>' | sudo -S <cmd>` to execute privileged commands (e.g., `systemctl restart`).

### 3. Data Processing (`systemd_parser.py`)
- **Functionality**: Reads the raw text of a `.service` file.
- **Parsing**: Extracts the `ExecStart` line, splits it using `shlex`, and parses standard flag arguments (`-m`, `--port`, `--threads`, etc.) into a dictionary.
- **Rebuilding**: Reconstructs the `ExecStart` multiline command with backslashes and preserves the rest of the `systemd` file exactly as it was.

## Data Flow
1. **Discovery**: `SSHManager` runs `grep -l 'llama-server' /etc/systemd/system/*.service` to find active models.
2. **Editing**: 
   - UI requests file content via `SSHManager`.
   - Content is passed to `SystemdParser`.
   - UI generates form inputs based on the parsed dictionary.
   - User saves -> Dictionary is rebuilt into string -> `SSHManager` uses `sudo tee` to write back and run `systemctl daemon-reload`.

## Dependencies
- `customtkinter`: GUI framework
- `paramiko`: SSH client
- `pytest`: For TDD/Unit testing
