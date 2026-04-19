import customtkinter as ctk
import tkinter as tk
from ssh_manager import SSHManager
from systemd_parser import SystemdParser
import json
import os
import threading

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
        y = (self.winfo_screenheight() // 2) - 310
        self.geometry(f'500x620+{x}+{y}')

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

        self.error_label = ctk.CTkLabel(self.card, text="", text_color=COLOR_DANGER, font=ctk.CTkFont(size=12))
        self.error_label.pack(pady=8)

        self.connect_btn = ctk.CTkButton(self.card, text="Connect Securely  →", command=self.do_login, height=48, corner_radius=12, font=ctk.CTkFont(size=15, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.connect_btn.pack(pady=(5, 30), padx=35, fill="x")

        self.bind('<Return>', lambda event: self.do_login())

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
        key = self.key_entry.get().strip()
        sudo = self.sudo_entry.get()
        
        if not host or not user or not key or not sudo:
            self.error_label.configure(text="All fields including Sudo Password are required.", text_color=COLOR_DANGER)
            return
            
        self.error_label.configure(text="Authenticating...", text_color=COLOR_INFO)
        self.connect_btn.configure(state="disabled", text="Connecting...")
        self.update()
        
        ssh = SSHManager()
        success, msg = ssh.connect(host, user, key, sudo)
        
        if success:
            self.save_settings(host, user, key)
            self.on_login_success(ssh)
            self.destroy()
        else:
            self.error_label.configure(text=f"Error: {msg}", text_color=COLOR_DANGER)
            self.connect_btn.configure(state="normal", text="Connect Securely  →")

class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, ssh_manager, app):
        super().__init__(master, fg_color="transparent")
        self.ssh = ssh_manager
        self.app = app
        
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        
        self.title_label = ctk.CTkLabel(header_frame, text="Active Models", font=ctk.CTkFont(size=28, weight="bold"), text_color=COLOR_TEXT)
        self.title_label.pack(side="left")
        
        self.refresh_btn = ctk.CTkButton(header_frame, text="↻  Refresh", command=self.load_services, width=130, height=40, corner_radius=10, font=ctk.CTkFont(size=13, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.refresh_btn.pack(side="right")
        
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

    def create_service_row(self, service, status):
        is_running = status == "Running"
        is_failed = status == "Failed"

        card = ctk.CTkFrame(self.scroll_frame, fg_color=COLOR_CARD, corner_radius=14, border_width=1, border_color=COLOR_BORDER)
        card.pack(fill="x", pady=8, padx=4, ipadx=5, ipady=12)

        # Left accent bar based on status
        accent_color = COLOR_SUCCESS if is_running else COLOR_DANGER if is_failed else COLOR_TEXT_DIM
        bar = ctk.CTkFrame(card, width=4, corner_radius=4, fg_color=accent_color)
        bar.pack(side="left", fill="y", padx=(10, 0), pady=6)

        # Name and type icon
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", padx=15, fill="y", expand=False)

        raw = service.replace("llm_", "").replace(".service", "")
        is_docker = raw.startswith("docker:")
        icon = "🐳" if is_docker else "⚙️"
        display_name = icon + "  " + (raw.replace("docker:", ""))

        ctk.CTkLabel(info_frame, text=display_name, font=ctk.CTkFont(size=18, weight="bold"), text_color=COLOR_TEXT).pack(anchor="w")

        type_label = "Docker Container" if is_docker else "systemd Service"
        ctk.CTkLabel(info_frame, text=type_label, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_DIM).pack(anchor="w")

        # Status badge
        status_dot = "●" if is_running else "●" if is_failed else "○"
        status_color = COLOR_SUCCESS if is_running else COLOR_DANGER if is_failed else COLOR_TEXT_DIM
        status_text = f"{status_dot}  {status}"
        ctk.CTkLabel(card, text=status_text, text_color=status_color, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=20)

        # Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(side="right", padx=15)

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

    def service_action(self, service, action, btn):
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
        
        exec_start = self.app_settings.get("default_exec", "/home/sandeep/llama.cpp/build/bin/llama-server")
        user = self.app_settings.get("default_user", "sandeep")
        workdir = self.app_settings.get("default_workdir", "/home/sandeep")
        
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
            
        if not name.startswith("llm_"):
            name = "llm_" + name
        if not name.endswith(".service"):
            name += ".service"
            
        service_path = f"/etc/systemd/system/{name}"
        
        exec_start = self.app_settings.get("default_exec", "/home/sandeep/llama.cpp/build/bin/llama-server")
        user = self.app_settings.get("default_user", "sandeep")
        workdir = self.app_settings.get("default_workdir", "/home/sandeep")
        
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

        ctk.CTkLabel(self, text="Application Settings", font=ctk.CTkFont(size=26, weight="bold"), text_color=COLOR_TEXT).pack(pady=(0, 5), anchor="w")
        ctk.CTkLabel(self, text="Configure defaults for service creation and discovery.", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_DIM).pack(anchor="w", pady=(0, 20))

        card = ctk.CTkFrame(self, corner_radius=16, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_BORDER)
        card.pack(fill="both", expand=True)

        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=5, pady=5)

        e = dict(height=44, corner_radius=10, fg_color=COLOR_INPUT_BG, border_color=COLOR_BORDER, border_width=1, text_color=COLOR_TEXT)

        def add_field(label, attr, default):
            ctk.CTkLabel(scroll, text=label, font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_DIM).pack(pady=(20, 4), padx=40, anchor="w")
            entry = ctk.CTkEntry(scroll, **e)
            entry.insert(0, self.app.app_settings.get(attr, default))
            entry.pack(pady=(0, 4), padx=40, fill="x")
            return entry

        self.user_entry     = add_field("Default User (for systemd User=)",      "default_user",     "sandeep")
        self.workdir_entry  = add_field("Default Working Directory",              "default_workdir",  "/home/sandeep")
        self.modeldir_entry = add_field("Default Model Download Directory",       "default_model_dir","~/models")
        self.exec_entry     = add_field("Default ExecStart (llama-server path)",  "default_exec",     "/home/sandeep/llama.cpp/build/bin/llama-server")
        self.docker_entry   = add_field("Docker Match Keywords (comma separated)","docker_keywords",  "llm_, llama, vllm, ollama, comfy, wan")

        self.save_btn = ctk.CTkButton(scroll, text="💾  Save Settings", command=self.save_global_settings, height=48, corner_radius=12, font=ctk.CTkFont(size=14, weight="bold"), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER)
        self.save_btn.pack(pady=(24, 10), padx=40, fill="x")

        self.status_label = ctk.CTkLabel(scroll, text="", font=ctk.CTkFont(size=13))
        self.status_label.pack(pady=5, padx=40, anchor="w")

    def save_global_settings(self):
        self.app.app_settings["default_user"] = self.user_entry.get().strip()
        self.app.app_settings["default_workdir"] = self.workdir_entry.get().strip()
        self.app.app_settings["default_model_dir"] = self.modeldir_entry.get().strip()
        self.app.app_settings["default_exec"] = self.exec_entry.get().strip()
        self.app.app_settings["docker_keywords"] = self.docker_entry.get().strip()
        
        config_path = os.path.expanduser("~/.model_manager_settings.json")
        try:
            with open(config_path, 'w') as f:
                json.dump(self.app.app_settings, f)
            self.status_label.configure(text="Settings saved successfully!", text_color="#2ECC71")
        except Exception as e:
            self.status_label.configure(text=f"Failed to save: {e}", text_color="#E74C3C")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Model Manager")
        self.configure(fg_color=COLOR_BG_DARK)
        self.ssh = None
        self.app_settings = {}
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.withdraw()
        self.login_dialog = LoginDialog(self, self.on_login_success)

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
        sidebar_w = max(200, int(sw * 0.25))

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

        # Spacer + host label
        ctk.CTkFrame(self.sidebar_frame, fg_color="transparent").pack(fill="both", expand=True)
        host = self.app_settings.get("host", "")
        ctk.CTkLabel(
            self.sidebar_frame, text=f"●  {host}",
            font=ctk.CTkFont(size=11), text_color=COLOR_SUCCESS,
            wraplength=200, justify="left"
        ).pack(padx=14, pady=(0, 20), anchor="w")

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

    def select_frame(self, name):
        for key, btn in self.nav_buttons.items():
            if key == name:
                btn.configure(fg_color=COLOR_ACCENT, text_color=COLOR_TEXT)
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT_DIM)
        self.frames[name].tkraise()
        if name == "dashboard":
            self.frames[name].load_services()

if __name__ == "__main__":
    app = App()
    app.mainloop()
