import customtkinter as ctk
import tkinter as tk
from ssh_manager import SSHManager
from systemd_parser import SystemdParser
import json
import os
import threading
import re
import urllib.request

# --- Linux bindings fix for CTkEntry ---
_orig_entry_init = ctk.CTkEntry.__init__

def _patched_entry_init(self, *args, **kwargs):
    _orig_entry_init(self, *args, **kwargs)
    
    def select_all(event):
        event.widget.select_range(0, 'end')
        event.widget.icursor('end')
        return 'break'
        
    def jump_left(event):
        idx = event.widget.index("insert")
        txt = event.widget.get()[:idx]
        matches = list(re.finditer(r'\b\w+\b|\s+', txt))
        new_idx = matches[-2].start() if len(matches) > 1 else 0
        event.widget.icursor(new_idx)
        return 'break'
        
    def jump_right(event):
        idx = event.widget.index("insert")
        txt = event.widget.get()[idx:]
        matches = list(re.finditer(r'\b\w+\b|\s+', txt))
        new_idx = idx + (matches[1].end() if len(matches) > 1 else len(txt))
        event.widget.icursor(new_idx)
        return 'break'
        
    self.bind('<Control-a>', select_all)
    self.bind('<Control-A>', select_all)
    self.bind('<Control-Left>', jump_left)
    self.bind('<Control-Right>', jump_right)

ctk.CTkEntry.__init__ = _patched_entry_init
# ---------------------------------------


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ── Premium Color Palette ──
COLOR_BG_DARK = "#0F1117"
COLOR_CARD = "#1A1D27"
COLOR_CARD_HOVER = "#22263A"
COLOR_SIDEBAR = "#141620"
COLOR_ACCENT = "#6C5CE7"
COLOR_ACCENT_HOVER = "#5A4BD1"
COLOR_SUCCESS = "#00D68F"
COLOR_SUCCESS_HOVER = "#00B87A"
COLOR_DANGER = "#FF6B6B"
COLOR_DANGER_HOVER = "#EE5A5A"
COLOR_WARNING = "#FDCB6E"
COLOR_WARNING_HOVER = "#E0B050"
COLOR_INFO = "#74B9FF"
COLOR_INFO_HOVER = "#5AA0E6"
COLOR_TEXT = "#E8E8F0"
COLOR_TEXT_DIM = "#6C7293"
COLOR_INPUT_BG = "#252836"
COLOR_BORDER = "#2D3045"

APP_VERSION = "v1.1.0"

class LoginDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_login_success):
        super().__init__(parent)
        self.title("Model Manager — Connect")
        self.geometry("500x620")
        self.configure(fg_color=COLOR_BG_DARK)
        self.on_login_success = on_login_success
        self.protocol("WM_DELETE_WINDOW", parent.quit)
        self.resizable(False, False)

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - 250
        y = (self.winfo_screenheight() // 2) - 320
        self.geometry(f'500x640+{x}+{y}')

        # Card container
        self.card = ctk.CTkFrame(self, corner_radius=20, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER)
        self.card.pack(fill="both", expand=True, padx=30, pady=30)

        # Icon / branding
        ctk.CTkLabel(self.card, text="🧠", font=ctk.CTkFont(size=40)).pack(pady=(30, 5))
        ctk.CTkLabel(self.card, text="Model Manager", font=ctk.CTkFont(size=26, weight="bold"), text_color=COLOR_TEXT).pack(pady=(0, 5))
        ctk.CTkLabel(self.card, text="Connect to your GPU server", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_DIM).pack(pady=(0, 25))

        entry_kwargs = dict(height=44, corner_radius=10, fg_color=COLOR_INPUT_BG, border_color=COLOR_BORDER, border_width=1, text_color=COLOR_TEXT)

        self.host_entry = ctk.CTkEntry(self.card, placeholder_text="Host (e.g. 192.168.0.28)", **entry_kwargs)
        self.host_entry.pack(pady=6, padx=35, fill="x")

        self.user_entry = ctk.CTkEntry(self.card, placeholder_text="Username", **entry_kwargs)
        self.user_entry.pack(pady=6, padx=35, fill="x")

        self.key_entry = ctk.CTkEntry(self.card, placeholder_text="Path to SSH Key (~/.ssh/id_rsa)", **entry_kwargs)
        self.key_entry.pack(pady=6, padx=35, fill="x")

        self.sudo_entry = ctk.CTkEntry(self.card, placeholder_text="Sudo Password (Required)", show="•", **entry_kwargs)
        self.sudo_entry.pack(pady=6, padx=35, fill="x")

        self.load_settings()

        # Focus the first empty field; if all filled, go straight to sudo
        self.after(100, self._focus_first_empty)

        self.error_label = ctk.CTkLabel(
            self.card, text="", text_color=COLOR_DANGER,
            font=ctk.CTkFont(size=12), wraplength=400, justify="center"
        )
        self.error_label.pack(pady=(6, 2))

        self.connect_btn = ctk.CTkButton(self.card, text="Connect Securely  →", command=self.do_login, height=48, corner_radius=12, font=ctk.CTkFont(size=15, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.connect_btn.pack(pady=(5, 30), padx=35, fill="x")

        self.bind('<Return>', lambda event: self.do_login())

    def _focus_first_empty(self):
        """Place cursor in the first field that has no value."""
        for entry in [self.host_entry, self.user_entry, self.key_entry, self.sudo_entry]:
            if not entry.get().strip():
                entry.focus_set()
                return
        # All pre-filled — go to sudo password
        self.sudo_entry.focus_set()

    def get_config_path(self):
        return os.path.expanduser("~/.model_manager_settings.json")

    def load_settings(self):
        try:
            with open(self.get_config_path(), 'r') as f:
                settings = json.load(f)
                self.host_entry.insert(0, settings.get("host", "localhost"))
                self.user_entry.insert(0, settings.get("user", ""))
                self.key_entry.insert(0, settings.get("key", ""))
                self.master.app_settings = settings
        except FileNotFoundError:
            self.host_entry.insert(0, "localhost")
            self.master.app_settings = {}

    def save_settings(self, host, user, key):
        settings = getattr(self.master, "app_settings", {})
        settings.update({"host": host, "user": user, "key": key})
        self.master.app_settings = settings
        try:
            with open(self.get_config_path(), 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def do_login(self):
        host = self.host_entry.get().strip()
        user = self.user_entry.get().strip()
        key  = self.key_entry.get().strip()
        sudo = self.sudo_entry.get()          # optional

        if not host or not user or not key:
            self.error_label.configure(text="Host, username and SSH key are required.", text_color=COLOR_DANGER)
            self._focus_first_empty()
            return

        self.error_label.configure(text="Connecting...", text_color=COLOR_INFO)
        self.connect_btn.configure(state="disabled", text="Connecting...")
        self.update()

        ssh = SSHManager()
        success, msg = ssh.connect(host, user, key, sudo or None)

        if success:
            self.save_settings(host, user, key)
            self.master.app_settings["connected_user"] = user
            self.master.sudo_password = sudo   # may be empty string
            self.on_login_success(ssh)
            self.destroy()
        else:
            short_msg = msg if len(msg) <= 80 else msg[:77] + "..."
            self.error_label.configure(text=short_msg, text_color=COLOR_DANGER)
            self.connect_btn.configure(state="normal", text="Connect Securely  →")
            self.sudo_entry.focus_set()

class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, ssh_manager, app):
        super().__init__(master, fg_color="transparent")
        self.ssh = ssh_manager
        self.app = app
        
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 14))
        
        self.title_label = ctk.CTkLabel(header_frame, text="Active Models", font=ctk.CTkFont(size=28, weight="bold"), text_color=COLOR_TEXT)
        self.title_label.pack(side="left")
        
        self.refresh_btn = ctk.CTkButton(header_frame, text="↻  Refresh", command=self.load_services, width=130, height=40, corner_radius=10, font=ctk.CTkFont(size=13, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.refresh_btn.pack(side="right")

        # GPU Health button — opens metrics popup on click
        self.vram_btn = ctk.CTkButton(
            header_frame, text="🖥  GPU Health",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#FFFFFF",
            fg_color=COLOR_INFO, hover_color=COLOR_INFO_HOVER,
            corner_radius=8, height=36,
            command=self._open_gpu_metrics
        )
        self.vram_btn.pack(side="right", padx=14)

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", scrollbar_button_color=COLOR_BORDER)
        self.scroll_frame.pack(fill="both", expand=True)
        
    def load_services(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        loading = ctk.CTkLabel(self.scroll_frame, text="⏳  Scanning for services...", font=ctk.CTkFont(size=15), text_color=COLOR_TEXT_DIM)
        loading.pack(pady=40)
        self.update()
        
        raw_keywords = self.app.app_settings.get("docker_keywords", "llm_, llama, vllm, ollama, comfy, wan")
        keywords = "|".join([k.strip() for k in raw_keywords.split(",") if k.strip()])
        if not keywords: keywords = "llm_|llama"
        
        services_status = self.ssh.get_services_with_status(docker_keywords=keywords)
        loading.destroy()
        
        if not services_status:
            ctk.CTkLabel(self.scroll_frame, text="No model services detected on this server.", font=ctk.CTkFont(size=15), text_color=COLOR_TEXT_DIM).pack(pady=60)
            return
            
        for service, status in services_status.items():
            self.create_service_row(service, status)

    def _open_gpu_metrics(self):
        GpuMetricsWindow(self, self.ssh)

    def create_service_row(self, service, status):
        is_running = status == "Running"
        is_failed = status == "Failed"

        card = ctk.CTkFrame(self.scroll_frame, fg_color=COLOR_CARD, corner_radius=14, border_width=1, border_color=COLOR_BORDER)
        card.pack(fill="x", pady=8, padx=4)

        # Inner row with consistent padding on all sides
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x")

        # Left accent bar
        accent_color = COLOR_SUCCESS if is_running else COLOR_DANGER if is_failed else COLOR_TEXT_DIM
        bar = ctk.CTkFrame(inner, width=5, corner_radius=4, fg_color=accent_color)
        bar.pack(side="left", fill="y", padx=(12, 0), pady=18)

        # Name + subtitle
        info_frame = ctk.CTkFrame(inner, fg_color="transparent")
        info_frame.pack(side="left", padx=18, pady=18)

        raw = service.replace("llm_", "").replace(".service", "")
        is_docker = raw.startswith("docker:")
        icon = "🐳" if is_docker else "⚙️"
        display_name = icon + "  " + (raw.replace("docker:", ""))

        ctk.CTkLabel(info_frame, text=display_name, font=ctk.CTkFont(size=18, weight="bold"), text_color=COLOR_TEXT).pack(anchor="w")
        type_label = "Docker Container" if is_docker else "systemd Service"
        ctk.CTkLabel(info_frame, text=type_label, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(2, 0))

        # Status badge
        status_dot = "●" if is_running else "●" if is_failed else "○"
        status_color = COLOR_SUCCESS if is_running else COLOR_DANGER if is_failed else COLOR_TEXT_DIM
        status_text = f"{status_dot}  {status}"
        ctk.CTkLabel(inner, text=status_text, text_color=status_color, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=20)

        # Buttons
        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(side="right", padx=16, pady=14)

        btn_h, btn_w, btn_r = 34, 95, 8
        btn_font = ctk.CTkFont(size=12, weight="bold")

        if is_docker:
            edit_btn = ctk.CTkButton(btn_frame, text="Edit Config", width=btn_w, height=btn_h, corner_radius=btn_r, font=btn_font, fg_color=COLOR_BORDER, hover_color=COLOR_BORDER, state="disabled", text_color=COLOR_TEXT_DIM)
        else:
            edit_btn = ctk.CTkButton(btn_frame, text="✏️  Edit", width=btn_w, height=btn_h, corner_radius=btn_r, font=btn_font, fg_color="#2D3045", hover_color="#3D4060", command=lambda: self.open_editor(service))
        edit_btn.pack(side="left", padx=4)

        restart_btn = ctk.CTkButton(btn_frame, text="🔄  Restart", width=btn_w, height=btn_h, corner_radius=btn_r, font=btn_font, fg_color=COLOR_INFO, hover_color=COLOR_INFO_HOVER)
        restart_btn.configure(command=lambda b=restart_btn: self.service_action(service, "restart", b))
        restart_btn.pack(side="left", padx=4)

        stop_btn = ctk.CTkButton(btn_frame, text="⏹️  Stop", width=btn_w, height=btn_h, corner_radius=btn_r, font=btn_font, fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER)
        stop_btn.configure(command=lambda b=stop_btn: self.service_action(service, "stop", b))
        stop_btn.pack(side="left", padx=4)

        start_btn = ctk.CTkButton(btn_frame, text="▶️  Start", width=btn_w, height=btn_h, corner_radius=btn_r, font=btn_font, fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER, text_color="#0A2A1F")
        start_btn.configure(command=lambda b=start_btn: self.service_action(service, "start", b))
        start_btn.pack(side="left", padx=4)

        # Logs button — only for systemd services (journalctl)
        logs_btn = ctk.CTkButton(btn_frame, text="📔  Logs", width=btn_w, height=btn_h, corner_radius=btn_r, font=btn_font, fg_color="#2A2040", hover_color="#3A3060", command=lambda: self.open_logs(service))
        logs_btn.pack(side="left", padx=4)

        if is_running:
            chat_btn = ctk.CTkButton(btn_frame, text="💬  Chat", width=btn_w, height=btn_h, corner_radius=btn_r, font=btn_font, fg_color="#6C5CE7", hover_color="#5A4BD1", command=lambda: self.open_chat(service))
            chat_btn.pack(side="left", padx=4)

    def service_action(self, service, action, btn):
        if not self.app.is_admin():
            # Show a temporary warning on the button itself
            orig = btn.cget("text")
            orig_color = btn.cget("fg_color")
            btn.configure(text="⚠  Need Admin Mode", fg_color=COLOR_WARNING,
                          text_color="#1A1000", state="disabled")
            self.after(2500, lambda: btn.configure(
                text=orig, fg_color=orig_color,
                text_color="#FFFFFF" if action == "start" else "#FFFFFF",
                state="normal"
            ))
            return

        original_text = btn.cget("text")
        btn.configure(text=f"⏳  {action.title()}ing...", state="disabled", fg_color=COLOR_BORDER)
        self.update()

        def run_action():
            if action in ["start", "stop", "restart"]:
                if service.startswith("docker:"):
                    container = service.split(":")[1]
                    self.ssh.run_command(f"docker {action} {container}", use_sudo=True)
                else:
                    self.ssh.run_command(f"systemctl {action} {service}", use_sudo=True)
            self.after(0, self.load_services)

        threading.Thread(target=run_action, daemon=True).start()

    def open_editor(self, service):
        EditorWindow(self, self.ssh, service)

    def open_logs(self, service):
        LogsWindow(self, self.ssh, service)

    def open_chat(self, service):
        ChatWindow(self, self.ssh, service)
        
class ChatWindow(ctk.CTkToplevel):
    """Chat interface that automatically discovers port and API key to talk to local models."""

    def __init__(self, parent, ssh_manager, service):
        super().__init__(parent)
        self.ssh = ssh_manager
        self.service = service
        self.port = 8080
        self.api_key = ""
        self.endpoint = "/v1/chat/completions"

        name = service.replace("llm_", "").replace(".service", "").replace("docker:", "")
        self.title(f"Chat — {name}")
        self.configure(fg_color=COLOR_BG_DARK)
        self.update_idletasks()
        w, h = 650, 700
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.minsize(500, 600)

        hdr = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=0)
        hdr.pack(fill="x", padx=0, pady=0)
        ctk.CTkLabel(hdr, text=f"💬  {name}", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COLOR_TEXT).pack(side="left", padx=20, pady=12)
                     
        self.status_lbl = ctk.CTkLabel(hdr, text="Discovering configuration...", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM)
        self.status_lbl.pack(side="right", padx=20)

        # Chat history
        self.history = ctk.CTkTextbox(self, font=ctk.CTkFont(size=13), fg_color="#0D0F18", text_color=COLOR_TEXT, state="disabled")
        self.history.pack(fill="both", expand=True, padx=20, pady=(20, 10))

        # Input area
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(fill="x", padx=20, pady=(0, 20))

        self.msg_entry = ctk.CTkEntry(input_frame, placeholder_text="Type a message...", height=44, font=ctk.CTkFont(size=13))
        self.msg_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.msg_entry.bind("<Return>", lambda e: self._send_msg())

        self.send_btn = ctk.CTkButton(input_frame, text="Send", width=80, height=44, font=ctk.CTkFont(size=13, weight="bold"),
                                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, command=self._send_msg)
        self.send_btn.pack(side="right")
        
        self.msg_entry.focus_set()

        # Start discovery
        threading.Thread(target=self._discover_config, daemon=True).start()

    def _append_chat(self, sender, text, color=COLOR_TEXT):
        self.history.configure(state="normal")
        self.history.insert("end", f"{sender}: ", "bold")
        self.history.insert("end", f"{text}\n\n")
        self.history.see("end")
        self.history.configure(state="disabled")

    def _discover_config(self):
        import re
        if self.service.startswith("docker:"):
            container = self.service.replace("docker:", "")
            _, out = self.ssh.run_command(f"docker port {container} 2>/dev/null")
            # e.g., "8080/tcp -> 0.0.0.0:8080"
            m = re.search(r':(\d+)$', (out or "").strip())
            if m: self.port = int(m.group(1))
            self.endpoint = "/api/generate" if "ollama" in container.lower() else "/v1/chat/completions"
        else:
            _, out = self.ssh.run_command(f"systemctl show {self.service} --property=ExecStart 2>/dev/null", use_sudo=True)
            # Find port
            port_m = re.search(r'--port\s+(\d+)', out or "")
            if not port_m: port_m = re.search(r'-p\s+(\d+)', out or "")
            if port_m: self.port = int(port_m.group(1))
            
            # Find API Key
            key_m = re.search(r'--api[_-]key\s+(\S+)', out or "")
            if key_m: self.api_key = key_m.group(1).strip("'\"")

        status = f"Port: {self.port} | Auth: {'Yes' if self.api_key else 'No'}"
        self.after(0, lambda: self.status_lbl.configure(text=status, text_color=COLOR_SUCCESS))

    def _send_msg(self):
        text = self.msg_entry.get().strip()
        if not text: return
        
        self.msg_entry.delete(0, "end")
        self._append_chat("You", text, COLOR_INFO)
        self.send_btn.configure(state="disabled")
        
        threading.Thread(target=self._do_send, args=(text,), daemon=True).start()

    def _do_send(self, text):
        import json
        safe_text = json.dumps(text) # Automatically escapes quotes correctly
        
        if self.endpoint == "/api/generate":
            payload = f'{{"model": "llama2", "prompt": {safe_text}, "stream": false}}' # basic ollama fallback
        else:
            payload = f'{{"messages": [{{"role": "user", "content": {safe_text}}}], "max_tokens": 512}}'

        safe_payload = payload.replace("'", "'\\''")
        auth_header = f"-H 'Authorization: Bearer {self.api_key}'" if self.api_key else ""
        
        # Add -w to grab HTTP status code on the last line
        cmd = f"curl -s -w '\\n%{{http_code}}' -X POST http://127.0.0.1:{self.port}{self.endpoint} -H 'Content-Type: application/json' {auth_header} -d '{safe_payload}'"
        _, out = self.ssh.run_command(cmd)
        
        self.after(0, lambda: self._handle_reply(out))

    def _handle_reply(self, out):
        self.send_btn.configure(state="normal")
        if not out:
            self._append_chat("System", "Error: No response or connection refused.", COLOR_DANGER)
            return
            
        lines = out.strip().split('\n')
        status_code = lines[-1]
        body = '\n'.join(lines[:-1])

        if status_code == "503":
            self._append_chat("System", "503 Service Unavailable: The model is loading into VRAM. Auto-pinging until ready...", COLOR_WARNING)
            threading.Thread(target=self._wait_for_ready, daemon=True).start()
            return
        elif status_code == "000" or not status_code.isdigit():
            self._append_chat("System", "Error: Connection refused or port not open.", COLOR_DANGER)
            return

        if not body:
            self._append_chat("System", f"HTTP {status_code} Error: Empty response.", COLOR_DANGER)
            return

        import json
        try:
            data = json.loads(body)
            if "choices" in data and len(data["choices"]) > 0:
                reply = data["choices"][0]["message"]["content"]
            elif "response" in data: # Ollama
                reply = data["response"]
            elif "content" in data:
                reply = data["content"]
            elif "error" in data:
                err_msg = data['error'].get('message', str(data['error'])) if isinstance(data['error'], dict) else str(data['error'])
                reply = f"Error: {err_msg}"
            else:
                reply = json.dumps(data, indent=2)
            self._append_chat("Model", reply.strip())
        except Exception:
            self._append_chat("Model (Raw)", body.strip())

    def _wait_for_ready(self):
        if getattr(self, '_is_waiting', False):
            return
        self._is_waiting = True
        
        while self._is_waiting and self.winfo_exists():
            import time
            time.sleep(3)
            auth_header = f"-H 'Authorization: Bearer {self.api_key}'" if self.api_key else ""
            # Simple GET request to the endpoint to check HTTP status
            cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{self.port}{self.endpoint} {auth_header}"
            _, out = self.ssh.run_command(cmd)
            code = (out or "").strip()
            
            # If we get any valid HTTP response other than 503 or 000, the server is fully up
            if code.isdigit() and code not in ["503", "000"]:
                self.after(0, lambda: self._append_chat("System", "✅ The model has finished loading and is ready!", COLOR_SUCCESS))
                self._is_waiting = False
                break


class EditorWindow(ctk.CTkToplevel):
    def __init__(self, parent, ssh_manager, service):
        super().__init__(parent)
        self.title("Configuration Editor")
        self.geometry("700x800")
        self.ssh = ssh_manager
        self.service = service
        self.config = None
        
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(30, 10))
        
        ctk.CTkLabel(header, text="Edit Configuration", font=ctk.CTkFont(size=28, weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text=service, font=ctk.CTkFont(size=14), text_color="gray").pack(side="left", padx=15)
        
        # Card container for form
        self.card = ctk.CTkFrame(self, corner_radius=15, fg_color=("gray85", "gray16"))
        self.card.pack(fill="both", expand=True, padx=30, pady=10)
        
        self.scroll = ctk.CTkScrollableFrame(self.card, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.entries = {}
        self.load_config()
        
    def load_config(self):
        cmd = f"find /etc/systemd/system ~/.config/systemd/user -name '{self.service}' 2>/dev/null | head -n 1"
        success, out = self.ssh.run_command(cmd, use_sudo=True)
        self.file_path = out.strip() if success and out.strip() else f"/etc/systemd/system/{self.service}"
        
        content = self.ssh.read_file(self.file_path)
        if not content:
            ctk.CTkLabel(self.scroll, text="Failed to read service file.", text_color="#E74C3C").pack(pady=20)
            return
            
        self.config = SystemdParser.parse_service_content(content)
        
        # Description
        self._add_field("description", "Service Description", self.config["description"])
        
        ctk.CTkLabel(self.scroll, text="llama-server Arguments", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 10), anchor="w")
        
        # Arguments
        for k, v in self.config["args"].items():
            val = "" if v is True else str(v)
            self._add_field(f"arg_{k}", k, val)
            
        btn_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20, padx=20)
        
        save_btn = ctk.CTkButton(btn_frame, text="Save & Restart Service", command=self.save_config, height=45, font=ctk.CTkFont(weight="bold"), fg_color="#2ECC71", hover_color="#27AE60")
        save_btn.pack(side="right", padx=10)
        
        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), command=self.destroy, height=45)
        cancel_btn.pack(side="right", padx=10)
        
    def _add_field(self, key, label, value):
        lbl = ctk.CTkLabel(self.scroll, text=label, anchor="w", font=ctk.CTkFont(weight="bold"))
        lbl.pack(fill="x", pady=(10, 2))
        ent = ctk.CTkEntry(self.scroll, height=35)
        ent.insert(0, value)
        ent.pack(fill="x", pady=(0, 5))
        self.entries[key] = ent
        
    def save_config(self):
        if not self.config: return
        self.config["description"] = self.entries["description"].get()
        for k in self.config["args"].keys():
            val = self.entries[f"arg_{k}"].get()
            self.config["args"][k] = True if val == "" else val
                
        new_content = SystemdParser.build_service_content(self.config)
        success, msg = self.ssh.write_file(self.file_path, new_content)
        if success:
            self.ssh.run_command("systemctl daemon-reload", use_sudo=True)
            self.ssh.run_command(f"systemctl restart {self.service}", use_sudo=True)
            self.destroy()
        else:
            print(f"Failed to save: {msg}")

class GpuMetricsWindow(ctk.CTkToplevel):
    """Popup showing full GPU metrics via nvidia-smi."""

    QUERY_FIELDS = [
        ("gpu_name",          "GPU Model"),
        ("driver_version",    "Driver Version"),
        ("temperature.gpu",   "Temperature (°C)"),
        ("utilization.gpu",   "GPU Utilization (%)"),
        ("utilization.memory","Memory Utilization (%)"),
        ("memory.used",       "VRAM Used (MiB)"),
        ("memory.free",       "VRAM Free (MiB)"),
        ("memory.total",      "VRAM Total (MiB)"),
        ("power.draw",        "Power Draw (W)"),
        ("power.limit",       "Power Limit (W)"),
        ("clocks.current.sm", "SM Clock (MHz)"),
        ("clocks.current.memory", "Memory Clock (MHz)"),
        ("fan.speed",         "Fan Speed (%)"),
    ]

    def __init__(self, parent, ssh_manager):
        super().__init__(parent)
        self.ssh = ssh_manager
        self.title("GPU Metrics")
        self.configure(fg_color=COLOR_BG_DARK)
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = 680, 820
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.minsize(560, 620)
        self.resizable(True, True)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="🖥  GPU Health Monitor",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color=COLOR_TEXT
                     ).pack(side="left", padx=20, pady=14)
        self.refresh_btn = ctk.CTkButton(
            hdr, text="↻ Refresh", width=100, height=30,
            corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            command=self.fetch
        )
        self.refresh_btn.pack(side="right", padx=14, pady=10)

        # VRAM bar card
        bar_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12,
                                border_width=1, border_color=COLOR_BORDER)
        bar_card.pack(fill="x", padx=20, pady=(16, 8))
        self.bar_title = ctk.CTkLabel(bar_card, text="VRAM Usage",
                                      font=ctk.CTkFont(size=13, weight="bold"),
                                      text_color=COLOR_TEXT)
        self.bar_title.pack(pady=(14, 4), padx=20, anchor="w")
        self.prog_bar = ctk.CTkProgressBar(bar_card, height=16, corner_radius=8,
                                           progress_color=COLOR_SUCCESS)
        self.prog_bar.set(0)
        self.prog_bar.pack(fill="x", padx=20, pady=(0, 6))
        self.bar_label = ctk.CTkLabel(bar_card, text="— / — MiB",
                                      font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM)
        self.bar_label.pack(pady=(0, 12), padx=20, anchor="e")

        # Metrics grid
        metrics_card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=12,
                                    border_width=1, border_color=COLOR_BORDER)
        metrics_card.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self.scroll = ctk.CTkScrollableFrame(metrics_card, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=4, pady=4)
        self.scroll.grid_columnconfigure(0, weight=1)
        self.scroll.grid_columnconfigure(1, weight=1)

        self.metric_values: dict[str, ctk.CTkLabel] = {}
        for row_i, (_, human) in enumerate(self.QUERY_FIELDS):
            bg = COLOR_CARD if row_i % 2 == 0 else "#1E2130"
            ctk.CTkLabel(self.scroll, text=human,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=COLOR_TEXT_DIM, anchor="w"
                         ).grid(row=row_i, column=0, sticky="ew", padx=(12, 4), pady=6)
            val_lbl = ctk.CTkLabel(self.scroll, text="…",
                                   font=ctk.CTkFont(size=12),
                                   text_color=COLOR_TEXT, anchor="e")
            val_lbl.grid(row=row_i, column=1, sticky="ew", padx=(4, 12), pady=6)
            self.metric_values[_] = val_lbl

        self.fetch()

    def fetch(self):
        self.refresh_btn.configure(state="disabled", text="Loading…")
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def _do_fetch(self):
        fields = ",".join(k for k, _ in self.QUERY_FIELDS)
        cmd = f"nvidia-smi --query-gpu={fields} --format=csv,noheader,nounits 2>/dev/null | head -1"
        _, out = self.ssh.run_command(cmd)
        self.after(0, lambda: self._render(out.strip() if out else ""))

    def _render(self, raw: str):
        self.refresh_btn.configure(state="normal", text="↻ Refresh")
        if not raw:
            for lbl in self.metric_values.values():
                lbl.configure(text="N/A", text_color=COLOR_TEXT_DIM)
            return

        parts = [p.strip() for p in raw.split(",")]
        for i, (key, _) in enumerate(self.QUERY_FIELDS):
            val = parts[i] if i < len(parts) else "N/A"
            lbl = self.metric_values[key]

            # Colour-code specific fields
            if key == "temperature.gpu":
                v = float(val) if val.replace(".", "").isdigit() else 0
                color = COLOR_DANGER if v > 80 else COLOR_WARNING if v > 65 else COLOR_SUCCESS
                lbl.configure(text=f"{val} °C", text_color=color)
            elif key == "utilization.gpu":
                v = float(val) if val.replace(".", "").isdigit() else 0
                color = COLOR_DANGER if v > 90 else COLOR_WARNING if v > 70 else COLOR_TEXT
                lbl.configure(text=f"{val} %", text_color=color)
            elif key in ("memory.used", "memory.free", "memory.total"):
                lbl.configure(text=f"{val} MiB", text_color=COLOR_TEXT)
            elif key in ("power.draw", "power.limit"):
                lbl.configure(text=f"{val} W", text_color=COLOR_TEXT)
            elif key in ("clocks.current.sm", "clocks.current.memory"):
                lbl.configure(text=f"{val} MHz", text_color=COLOR_TEXT)
            elif key == "fan.speed":
                lbl.configure(text=f"{val} %", text_color=COLOR_TEXT)
            else:
                lbl.configure(text=val, text_color=COLOR_TEXT)

        # Update progress bar
        try:
            used_txt = self.metric_values["memory.used"].cget("text")
            total_txt = self.metric_values["memory.total"].cget("text")
            if "N/A" in used_txt or "N/A" in total_txt:
                self.prog_bar.set(0)
                self.prog_bar.configure(progress_color=COLOR_BORDER)
                self.bar_label.configure(text="Data Unavailable")
                self.bar_title.configure(text="VRAM Usage", text_color=COLOR_TEXT_DIM)
            else:
                used  = float(used_txt.replace(" MiB",""))
                total = float(total_txt.replace(" MiB",""))
                pct   = used / total if total else 0
                bar_color = COLOR_DANGER if pct > 0.85 else COLOR_WARNING if pct > 0.6 else COLOR_SUCCESS
                self.prog_bar.set(pct)
                self.prog_bar.configure(progress_color=bar_color)
                self.bar_label.configure(text=f"{used:.0f} / {total:.0f} MiB  ({pct*100:.1f}%)")
                self.bar_title.configure(
                    text=f"VRAM Usage",
                    text_color=bar_color
                )
        except Exception:
            pass

class LogsWindow(ctk.CTkToplevel):
    """Live log viewer — pulls journalctl or docker logs over SSH."""

    def __init__(self, parent, ssh_manager, service):
        super().__init__(parent)
        self.ssh = ssh_manager
        self.service = service
        self.is_docker = service.startswith("docker:")
        self._refresh_job = None

        name = service.replace("llm_", "").replace(".service", "").replace("docker:", "")
        self.title(f"Logs — {name}")
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = int(sw * 0.75)
        h = int(sh * 0.75)
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.configure(fg_color=COLOR_BG_DARK)
        self.minsize(800, 500)

        # Header bar
        header = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(header, text=f"📋  Logs: {name}", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=COLOR_TEXT).pack(side="left", padx=20, pady=12)

        # Line count selector
        self.line_var = tk.StringVar(value="100")
        ctk.CTkLabel(header, text="Lines:", font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM).pack(side="left")
        line_menu = ctk.CTkOptionMenu(header, values=["50", "100", "200", "500"],
                                      variable=self.line_var, width=80, height=30,
                                      command=lambda _: self.fetch_logs(),
                                      fg_color=COLOR_INPUT_BG, button_color=COLOR_ACCENT,
                                      button_hover_color=COLOR_ACCENT_HOVER)
        line_menu.pack(side="left", padx=(4, 16), pady=10)

        self.auto_var = tk.BooleanVar(value=False)
        auto_chk = ctk.CTkCheckBox(header, text="Auto-refresh (10s)", variable=self.auto_var,
                                   command=self._toggle_auto, font=ctk.CTkFont(size=12),
                                   text_color=COLOR_TEXT_DIM, fg_color=COLOR_ACCENT,
                                   hover_color=COLOR_ACCENT_HOVER)
        auto_chk.pack(side="left", padx=8)

        refresh_btn = ctk.CTkButton(header, text="↻ Refresh", width=100, height=30,
                                    corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
                                    fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
                                    command=self.fetch_logs)
        refresh_btn.pack(side="right", padx=12, pady=10)

        copy_btn = ctk.CTkButton(header, text="Copy", width=80, height=30,
                                 corner_radius=8, font=ctk.CTkFont(size=12),
                                 fg_color="#2D3045", hover_color="#3D4060",
                                 command=self.copy_to_clipboard)
        copy_btn.pack(side="right", padx=4, pady=10)

        # Log text area
        self.textbox = ctk.CTkTextbox(
            self, font=ctk.CTkFont(family="Monospace", size=12),
            fg_color="#0D0F18", text_color="#C8D0E8",
            corner_radius=0, wrap="none",
            scrollbar_button_color=COLOR_BORDER
        )
        self.textbox.pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.fetch_logs()

    def fetch_logs(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("end", "⏳  Fetching logs...\n")
        self.textbox.configure(state="disabled")
        self.update()
        threading.Thread(target=self._do_fetch, daemon=True).start()

    def _do_fetch(self):
        n = self.line_var.get()
        if self.is_docker:
            container = self.service.split(":")[1]
            _, out = self.ssh.run_command(f"docker logs --tail {n} {container} 2>&1", use_sudo=True)
        else:
            _, out = self.ssh.run_command(
                f"journalctl -u {self.service} -n {n} --no-pager --output=short-iso 2>&1",
                use_sudo=True
            )
        self.after(0, lambda: self._render(out))

    def _render(self, text):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("end", text or "(no log output)")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def copy_to_clipboard(self):
        content = self.textbox.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(content)

    def _toggle_auto(self):
        if self.auto_var.get():
            self._schedule_refresh()
        elif self._refresh_job:
            self.after_cancel(self._refresh_job)
            self._refresh_job = None

    def _schedule_refresh(self):
        self.fetch_logs()
        self._refresh_job = self.after(10000, self._schedule_refresh)

    def _on_close(self):
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        self.destroy()

class AddModelTab(ctk.CTkFrame):
    def __init__(self, master, ssh_manager, app_settings):
        super().__init__(master, fg_color="transparent")
        self.ssh = ssh_manager
        self.app_settings = app_settings

        ctk.CTkLabel(self, text="Download AI Model", font=ctk.CTkFont(size=26, weight="bold"), text_color=COLOR_TEXT).pack(pady=(0, 5), anchor="w")
        ctk.CTkLabel(self, text="Pull a model from HuggingFace and auto-register it as a service.", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(0, 20))

        card = ctk.CTkFrame(self, corner_radius=16, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER)
        card.pack(fill="both", expand=True)

        e = dict(height=44, corner_radius=10, fg_color=COLOR_INPUT_BG, border_color=COLOR_BORDER, border_width=1, text_color=COLOR_TEXT)

        ctk.CTkLabel(card, text="HuggingFace Repository ID", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_DIM).pack(pady=(30, 4), padx=40, anchor="w")
        self.repo_entry = ctk.CTkEntry(card, placeholder_text="e.g. Kbenkhaled/Qwen3.5-35B-A3B-NVFP4", **e)
        self.repo_entry.pack(pady=(0, 16), padx=40, fill="x")

        ctk.CTkLabel(card, text="Local Destination Directory", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_DIM).pack(pady=(0, 4), padx=40, anchor="w")
        self.dir_entry = ctk.CTkEntry(card, **e)
        self.dir_entry.insert(0, self.app_settings.get("default_model_dir", "~/models"))
        self.dir_entry.pack(pady=(0, 24), padx=40, fill="x")

        self.download_btn = ctk.CTkButton(card, text="⬇️  Start Download & Auto-Create Service", command=self.start_download, height=48, corner_radius=12, font=ctk.CTkFont(size=14, weight="bold"), fg_color=COLOR_INFO, hover_color=COLOR_INFO_HOVER)
        self.download_btn.pack(pady=(0, 20), padx=40, fill="x")

        self.status_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_DIM)
        self.status_label.pack(pady=5, padx=40, anchor="w")
        
    def start_download(self):
        repo = self.repo_entry.get().strip()
        local_dir = self.dir_entry.get().strip()
        if not repo or not local_dir:
            self.status_label.configure(text="Please fill both fields.", text_color="#E74C3C")
            return
            
        if not local_dir.endswith(repo.split("/")[-1]):
            local_dir = f"{local_dir}/{repo.split('/')[-1]}"
            self.dir_entry.delete(0, 'end')
            self.dir_entry.insert(0, local_dir)
            
        cmd = f"hf download {repo} --local-dir {local_dir}"
        session_name = "downloads"
        
        self.status_label.configure(text="Initializing download in tmux session 'downloads'...", text_color="white")
        success, msg = self.ssh.run_tmux_command(session_name, cmd)
        
        if success:
            self.create_service_template(repo, local_dir)
        else:
            self.status_label.configure(text=f"Failed to start: {msg}", text_color="#E74C3C")

    def create_service_template(self, repo, local_dir):
        safe_name = repo.split("/")[-1].lower().replace(".", "-")
        service_name = f"llm_{safe_name}.service"
        service_path = f"/etc/systemd/system/{service_name}"
        
        exec_start = self.app_settings.get("default_exec", f"/home/{self.app_settings.get('connected_user', 'user')}/llama.cpp/build/bin/llama-server")
        user = self.app_settings.get("default_user", self.app_settings.get("connected_user", "user"))
        workdir = self.app_settings.get("default_workdir", f"/home/{self.app_settings.get('connected_user', 'user')}")
        
        content = f"""[Unit]
Description={repo} Llama Server
After=network.target

[Service]
ExecStart={exec_start} \\
  -m {local_dir} \\
  -c 32000 \\
  -ngl 99 \\
  --host 0.0.0.0 \\
  --port 30002 \\
  --flash-attn on \\
  --threads 24 \\
  --alias {safe_name}

Restart=always
User={user}
WorkingDirectory={workdir}
Environment=CUDA_VISIBLE_DEVICES=0

[Install]
WantedBy=multi-user.target
"""
        self.ssh.write_file(service_path, content)
        self.ssh.run_command("systemctl daemon-reload", use_sudo=True)
        self.status_label.configure(text=f"Download initiated via tmux! Created service: {service_name}", text_color="#2ECC71")

class CreateServiceTab(ctk.CTkFrame):
    def __init__(self, master, ssh_manager, app_settings):
        super().__init__(master, fg_color="transparent")
        self.ssh = ssh_manager
        self.app_settings = app_settings

        ctk.CTkLabel(self, text="Register Existing Model", font=ctk.CTkFont(size=26, weight="bold"), text_color=COLOR_TEXT).pack(pady=(0, 5), anchor="w")
        ctk.CTkLabel(self, text="Create a systemd service for a model already on the server.", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(0, 20))

        card = ctk.CTkFrame(self, corner_radius=16, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER)
        card.pack(fill="both", expand=True)

        self._add_input(card, "Service Name", "name_entry", "e.g. qwen-fast")
        self._add_input(card, "Absolute Model Path", "path_entry", "e.g. /home/sandeep/models/qwen.gguf")
        self._add_input(card, "Server Port", "port_entry", "e.g. 30005")
        self._add_input(card, "Model Alias", "alias_entry", "e.g. qwen-test")

        self.create_btn = ctk.CTkButton(card, text="➕  Register & Start Service", command=self.create_service, height=48, corner_radius=12, font=ctk.CTkFont(size=14, weight="bold"), fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER, text_color="#0A2A1F")
        self.create_btn.pack(pady=(10, 20), padx=40, fill="x")

        self.status_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=13))
        self.status_label.pack(pady=5, padx=40, anchor="w")

    def _add_input(self, parent, label, attr_name, placeholder):
        ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_DIM).pack(pady=(20, 4), padx=40, anchor="w")
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, height=44, corner_radius=10, fg_color=COLOR_INPUT_BG, border_color=COLOR_BORDER, border_width=1, text_color=COLOR_TEXT)
        entry.pack(pady=(0, 0), padx=40, fill="x")
        setattr(self, attr_name, entry)

    def create_service(self):
        name = self.name_entry.get().strip()
        path = self.path_entry.get().strip()
        port = self.port_entry.get().strip()
        alias = self.alias_entry.get().strip()
        
        if not name or not path or not port or not alias:
            self.status_label.configure(text="Please fill all fields.", text_color="#E74C3C")
            return
            
        prefix = self.app_settings.get("service_prefix", "llm_")
        install_path = self.app_settings.get("service_install_path", "/etc/systemd/system")

        if not name.startswith(prefix):
            name = prefix + name
        if not name.endswith(".service"):
            name += ".service"

        service_path = f"{install_path}/{name}"

        _u = self.app_settings.get("connected_user", "user")
        exec_start = self.app_settings.get("default_exec", f"/home/{_u}/llama.cpp/build/bin/llama-server")
        user     = self.app_settings.get("default_user",    _u)
        workdir  = self.app_settings.get("default_workdir", f"/home/{_u}")
        
        content = f"""[Unit]
Description={alias} Llama Server
After=network.target

[Service]
ExecStart={exec_start} \\
  -m {path} \\
  -c 32000 \\
  -ngl 99 \\
  --host 0.0.0.0 \\
  --port {port} \\
  --flash-attn on \\
  --threads 24 \\
  --alias {alias}

Restart=always
User={user}
WorkingDirectory={workdir}
Environment=CUDA_VISIBLE_DEVICES=0

[Install]
WantedBy=multi-user.target
"""
        success, msg = self.ssh.write_file(service_path, content)
        if success:
            self.ssh.run_command("systemctl daemon-reload", use_sudo=True)
            self.ssh.run_command(f"systemctl start {name}", use_sudo=True)
            self.status_label.configure(text=f"Successfully created and started {name}!", text_color="#2ECC71")
            self.name_entry.delete(0, 'end')
            self.path_entry.delete(0, 'end')
            self.port_entry.delete(0, 'end')
            self.alias_entry.delete(0, 'end')
        else:
            self.status_label.configure(text=f"Failed: {msg}", text_color="#E74C3C")

class SettingsTab(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(self, text="Application Settings", font=ctk.CTkFont(size=26, weight="bold"), text_color=COLOR_TEXT).pack(pady=(0, 4), anchor="w")
        ctk.CTkLabel(self, text="All defaults are derived from your connected username. Save after making changes.",
                     font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(0, 16))

        card = ctk.CTkFrame(self, corner_radius=16, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER)
        card.pack(fill="both", expand=True)

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # Resolve sensible defaults from the connected SSH username
        s = self.app.app_settings
        u = s.get("connected_user") or s.get("user", "user")
        home = f"/home/{u}"

        e = dict(height=44, corner_radius=10, fg_color=COLOR_INPUT_BG,
                 border_color=COLOR_BORDER, border_width=1, text_color=COLOR_TEXT)

        def section(title, subtitle=""):
            ctk.CTkFrame(scroll, height=1, fg_color=COLOR_BORDER).pack(fill="x", padx=30, pady=(24, 0))
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=30, pady=(10, 0))
            ctk.CTkLabel(row, text=title, font=ctk.CTkFont(size=15, weight="bold"), text_color=COLOR_TEXT).pack(anchor="w")
            if subtitle:
                ctk.CTkLabel(row, text=subtitle, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(2, 0))

        def field(label, attr, default):
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=COLOR_TEXT_DIM).pack(pady=(14, 3), padx=40, anchor="w")
            entry = ctk.CTkEntry(scroll, **e)
            entry.insert(0, s.get(attr, default))
            entry.pack(pady=(0, 0), padx=40, fill="x")
            return entry

        # ── Section 1: Server Identity
        section("👤  Server Identity", "User account used in generated systemd unit files.")
        self.user_entry    = field("Remote Username",         "default_user",    u)
        self.workdir_entry = field("Default Working Directory", "default_workdir", home)

        # ── Section 2: Model Storage
        section("📂  Model Storage", "Paths on the remote server where models live.")
        self.modeldir_entry = field("Default Model Download Directory", "default_model_dir", f"{home}/models")
        self.exec_entry     = field("llama-server Binary Path (ExecStart)", "default_exec",
                                    f"{home}/llama.cpp/build/bin/llama-server")

        # ── Section 3: Service Management
        section("⚙️  Service Management", "Controls how systemd service files are named and where they are installed.")
        self.service_prefix_entry = field("Service Name Prefix",    "service_prefix",       "llm_")
        self.service_path_entry   = field("Service Install Directory", "service_install_path", "/etc/systemd/system")

        # ── Section 4: Docker Discovery
        section("🐳  Docker Discovery", "Comma-separated keywords to match against container names/images.")
        self.docker_entry = field("Match Keywords", "docker_keywords", "llm_, llama, vllm, ollama, comfy, wan")

        ctk.CTkFrame(scroll, height=1, fg_color=COLOR_BORDER).pack(fill="x", padx=30, pady=(24, 0))

        self.save_btn = ctk.CTkButton(
            scroll, text="💾  Save Settings",
            command=self.save_global_settings, height=48, corner_radius=12,
            font=ctk.CTkFont(size=14, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER
        )
        self.save_btn.pack(pady=(20, 8), padx=40, fill="x")

        self.status_label = ctk.CTkLabel(scroll, text="", font=ctk.CTkFont(size=13))
        self.status_label.pack(pady=4, padx=40, anchor="w")

    def save_global_settings(self):
        self.app.app_settings["default_user"]        = self.user_entry.get().strip()
        self.app.app_settings["default_workdir"]     = self.workdir_entry.get().strip()
        self.app.app_settings["default_model_dir"]   = self.modeldir_entry.get().strip()
        self.app.app_settings["default_exec"]        = self.exec_entry.get().strip()
        self.app.app_settings["service_prefix"]      = self.service_prefix_entry.get().strip()
        self.app.app_settings["service_install_path"]= self.service_path_entry.get().strip()
        self.app.app_settings["docker_keywords"]     = self.docker_entry.get().strip()

        config_path = os.path.expanduser("~/.model_manager_settings.json")
        try:
            with open(config_path, "w") as f:
                json.dump(self.app.app_settings, f, indent=2)
            self.status_label.configure(text="✓ Settings saved.", text_color=COLOR_SUCCESS)
        except Exception as exc:
            self.status_label.configure(text=f"Failed: {exc}", text_color=COLOR_DANGER)

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Model Manager")
        self.configure(fg_color=COLOR_BG_DARK)
        self.ssh = None
        self.sudo_password = ""      # in-memory only, never saved to disk
        self.app_settings = {}
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.withdraw()
        self.login_dialog = LoginDialog(self, self.on_login_success)

    def is_admin(self):
        return bool(self.sudo_password)

    def on_login_success(self, ssh_manager):
        self.ssh = ssh_manager
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = int(sw * 0.80)
        h = int(sh * 0.80)
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(900, 600)
        self.deiconify()
        self.setup_ui()

    def setup_ui(self):
        import tkinter as tk

        sw = self.winfo_screenwidth()
        sidebar_w = max(180, int(sw * 0.20))

        # Resizable paned layout: sidebar | content
        self.paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL,
            bg=COLOR_BG_DARK, sashwidth=6,
            sashrelief="flat", handlesize=0
        )
        self.paned.pack(fill="both", expand=True)

        # ── Sidebar
        self.sidebar_frame = ctk.CTkFrame(
            self.paned, corner_radius=0, fg_color=COLOR_SIDEBAR
        )
        self.paned.add(self.sidebar_frame, minsize=180, width=sidebar_w)

        # Logo
        ctk.CTkLabel(
            self.sidebar_frame, text="Model Manager",
            font=ctk.CTkFont(size=16, weight="bold"), text_color="#FFFFFF"
        ).pack(pady=(28, 2), padx=20, anchor="w")
        ctk.CTkLabel(
            self.sidebar_frame, text="AI Service Dashboard",
            font=ctk.CTkFont(size=11), text_color="#6C7293"
        ).pack(pady=(0, 14), padx=20, anchor="w")

        # Divider
        ctk.CTkFrame(self.sidebar_frame, height=1, fg_color=COLOR_BORDER).pack(fill="x", padx=14, pady=(0, 14))

        nav_items = [
            ("dashboard", "Dashboard"),
            ("download",  "Download Model"),
            ("create",    "Register Service"),
            ("settings",  "Settings"),
        ]
        self.nav_buttons = {}
        for key, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar_frame, text=label, anchor="w",
                height=44, corner_radius=8,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="transparent", text_color="#BBBBDD",
                hover_color="#252840",
                command=lambda k=key: self.select_frame(k)
            )
            btn.pack(fill="x", padx=10, pady=3)
            self.nav_buttons[key] = btn

        # Spacer
        ctk.CTkFrame(self.sidebar_frame, fg_color="transparent").pack(fill="both", expand=True)

        # Switch to Admin / Admin Mode button
        self.admin_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="🔐  Switch to Admin",
            anchor="w", height=40, corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_WARNING, hover_color=COLOR_WARNING_HOVER,
            text_color="#1A1000",
            command=self.toggle_admin
        )
        self.admin_btn.pack(fill="x", padx=10, pady=(0, 6))
        self._update_admin_btn()

        self.update_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="⬇️  Update Available",
            anchor="w", height=40, corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
            text_color="#0A2A1F",
            command=self.open_releases_page
        )
        
        self.check_for_updates()

        host = self.app_settings.get("host", "")
        ctk.CTkLabel(
            self.sidebar_frame, text=f"●  {host}",
            font=ctk.CTkFont(size=11), text_color=COLOR_SUCCESS,
            wraplength=200, justify="left"
        ).pack(padx=14, pady=(0, 16), anchor="w")

        # ── Main content ────────────────────────────────────────────────
        self.content_frame = ctk.CTkFrame(
            self.paned, corner_radius=0, fg_color=COLOR_BG_DARK
        )
        self.paned.add(self.content_frame, minsize=600)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        self.frames = {}
        self.frames["dashboard"] = DashboardTab(self.content_frame, self.ssh, self)
        self.frames["download"]  = AddModelTab(self.content_frame, self.ssh, self.app_settings)
        self.frames["create"]    = CreateServiceTab(self.content_frame, self.ssh, self.app_settings)
        self.frames["settings"]  = SettingsTab(self.content_frame, self)

        for frame in self.frames.values():
            frame.grid(row=0, column=0, sticky="nsew", padx=30, pady=30)

        self.select_frame("dashboard")

    def check_for_updates(self):
        def _check():
            try:
                req = urllib.request.Request(
                    "https://api.github.com/repos/rapsalands/model-manager/releases/latest",
                    headers={"User-Agent": "ModelManagerApp"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode())
                    latest = data.get("tag_name", "")
                    v_lat = [int(x) for x in latest.lstrip("v").split(".") if x.isdigit()]
                    v_cur = [int(x) for x in APP_VERSION.lstrip("v").split(".") if x.isdigit()]
                    if v_lat > v_cur:
                        self.after(0, lambda: self.update_btn.pack(fill="x", padx=10, pady=(0, 6), before=self.admin_btn))
            except Exception:
                pass
        threading.Thread(target=_check, daemon=True).start()

    def open_releases_page(self):
        import webbrowser
        webbrowser.open("https://github.com/rapsalands/model-manager/releases")

    def select_frame(self, name):
        for key, btn in self.nav_buttons.items():
            if key == name:
                btn.configure(fg_color=COLOR_ACCENT, text_color=COLOR_TEXT)
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT_DIM)
        self.frames[name].tkraise()
        if name == "dashboard":
            self.frames[name].load_services()

    def _update_admin_btn(self):
        if self.is_admin():
            self.admin_btn.configure(
                text="🛡  Admin Mode",
                fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                text_color="#0A2A1F"
            )
        else:
            self.admin_btn.configure(
                text="🔐  Switch to Admin",
                fg_color=COLOR_WARNING, hover_color=COLOR_WARNING_HOVER,
                text_color="#1A1000"
            )

    def toggle_admin(self):
        if self.is_admin():
            # Drop privileges
            self.sudo_password = ""
            self._update_admin_btn()
        else:
            # Ask for password
            SudoAuthDialog(self)


class SudoAuthDialog(ctk.CTkToplevel):
    """Small modal to enter sudo password and verify it via SSH."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Elevate Privileges")
        self.configure(fg_color=COLOR_BG_DARK)
        self.resizable(False, False)
        w, h = 500, 380
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.update_idletasks()
        self.after(100, self.grab_set)   # modal

        card = ctk.CTkFrame(self, corner_radius=16, fg_color=COLOR_CARD,
                            border_width=1, border_color=COLOR_BORDER)
        card.pack(fill="both", expand=True, padx=24, pady=24)

        ctk.CTkLabel(card, text="🔐", font=ctk.CTkFont(size=36)).pack(pady=(28, 4))
        ctk.CTkLabel(card, text="Switch to Admin Mode",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=COLOR_TEXT).pack(pady=(0, 4))
        ctk.CTkLabel(card, text="Enter the sudo password for this session.\nIt will not be saved to disk.",
                     font=ctk.CTkFont(size=12), text_color=COLOR_TEXT_DIM,
                     justify="center").pack(pady=(0, 20))

        self.pwd_entry = ctk.CTkEntry(
            card, placeholder_text="Sudo password", show="•",
            height=44, corner_radius=10,
            fg_color=COLOR_INPUT_BG, border_color=COLOR_BORDER,
            border_width=1, text_color=COLOR_TEXT
        )
        self.pwd_entry.pack(fill="x", padx=28, pady=(0, 8))
        self.pwd_entry.focus_set()

        self.err_label = ctk.CTkLabel(card, text=" ", font=ctk.CTkFont(size=12),
                                      text_color=COLOR_DANGER)
        self.err_label.pack(pady=(0, 8))

        self.auth_btn = ctk.CTkButton(
            card, text="Authenticate  →",
            command=self._authenticate, height=44, corner_radius=10,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER
        )
        self.auth_btn.pack(fill="x", padx=28, pady=(0, 20))

        self.bind("<Return>", lambda e: self._authenticate())

    def _authenticate(self):
        pwd = self.pwd_entry.get()
        if not pwd:
            self.err_label.configure(text="Password cannot be empty.")
            return
        self.auth_btn.configure(state="disabled", text="Verifying...")
        self.err_label.configure(text=" ")
        self.update()
        threading.Thread(target=self._verify, args=(pwd,), daemon=True).start()

    def _verify(self, pwd):
        # Quick sudo check: echo the token back through sudo
        ok, out = self.app.ssh.run_command(
            f"echo '{pwd}' | sudo -S echo sudo_ok 2>/dev/null"
        )
        if "sudo_ok" in (out or ""):
            self.app.sudo_password = pwd
            self.app.ssh.sudo_password = pwd   # keep SSHManager in sync
            self.after(0, self._on_success)
        else:
            self.after(0, lambda: self._on_fail())

    def _on_success(self):
        self.app._update_admin_btn()
        self.destroy()

    def _on_fail(self):
        self.err_label.configure(text="Incorrect password. Try again.")
        self.auth_btn.configure(state="normal", text="Authenticate  →")
        self.pwd_entry.focus_set()
        # Move cursor to end of text
        self.pwd_entry.icursor("end")


if __name__ == "__main__":
    app = App()
    app.mainloop()
