import customtkinter as ctk
import tkinter as tk
from ssh_manager import SSHManager
from systemd_parser import SystemdParser
import json
import os

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class LoginDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_login_success):
        super().__init__(parent)
        self.title("Connect to Server")
        self.geometry("450x550")
        self.on_login_success = on_login_success
        self.protocol("WM_DELETE_WINDOW", parent.quit)
        
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

        # Card container
        self.card = ctk.CTkFrame(self, corner_radius=15, fg_color=("gray85", "gray16"))
        self.card.pack(fill="both", expand=True, padx=40, pady=40)

        self.label = ctk.CTkLabel(self.card, text="Model Manager", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=(30, 20))

        self.host_entry = ctk.CTkEntry(self.card, placeholder_text="Host (e.g. 192.168.0.28)", height=40)
        self.host_entry.pack(pady=10, padx=30, fill="x")

        self.user_entry = ctk.CTkEntry(self.card, placeholder_text="Username", height=40)
        self.user_entry.pack(pady=10, padx=30, fill="x")

        self.key_entry = ctk.CTkEntry(self.card, placeholder_text="Path to SSH Key (~/.ssh/id_rsa)", height=40)
        self.key_entry.pack(pady=10, padx=30, fill="x")

        self.sudo_entry = ctk.CTkEntry(self.card, placeholder_text="Sudo Password (Required)", show="*", height=40)
        self.sudo_entry.pack(pady=10, padx=30, fill="x")

        self.load_settings()

        self.error_label = ctk.CTkLabel(self.card, text="", text_color="#E74C3C", font=ctk.CTkFont(size=12))
        self.error_label.pack(pady=5)

        self.connect_btn = ctk.CTkButton(self.card, text="Connect securely", command=self.do_login, height=45, font=ctk.CTkFont(weight="bold"))
        self.connect_btn.pack(pady=(10, 30), padx=30, fill="x")
        
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
            self.error_label.configure(text="Error: All fields (including Sudo Password) are strictly required.", text_color="#E74C3C")
            return
            
        self.error_label.configure(text="Authenticating...", text_color="white")
        self.update()
        
        ssh = SSHManager()
        success, msg = ssh.connect(host, user, key, sudo)
        
        if success:
            self.save_settings(host, user, key)
            self.on_login_success(ssh)
            self.destroy()
        else:
            self.error_label.configure(text=f"Error: {msg}", text_color="#E74C3C")

class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, ssh_manager):
        super().__init__(master, fg_color="transparent")
        self.ssh = ssh_manager
        
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 20))
        
        self.title_label = ctk.CTkLabel(header_frame, text="Active Models", font=ctk.CTkFont(size=32, weight="bold"))
        self.title_label.pack(side="left")
        
        self.refresh_btn = ctk.CTkButton(header_frame, text="↻ Refresh", command=self.load_services, width=120, height=40, font=ctk.CTkFont(weight="bold"))
        self.refresh_btn.pack(side="right")
        
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True)
        
    def load_services(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
            
        loading = ctk.CTkLabel(self.scroll_frame, text="Scanning for services...", font=ctk.CTkFont(size=16))
        loading.pack(pady=40)
        self.update()
        
        raw_keywords = self.master.app_settings.get("docker_keywords", "llm_, llama, vllm, ollama, comfy, wan")
        keywords = "|".join([k.strip() for k in raw_keywords.split(",") if k.strip()])
        if not keywords: keywords = "llm_|llama"
        
        services_status = self.ssh.get_services_with_status(docker_keywords=keywords)
        loading.destroy()
        
        if not services_status:
            ctk.CTkLabel(self.scroll_frame, text="No model services found.", font=ctk.CTkFont(size=16), text_color="gray").pack(pady=40)
            return
            
        for service, status in services_status.items():
            self.create_service_row(service, status)

    def create_service_row(self, service, status):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=("gray85", "gray16"), corner_radius=15)
        card.pack(fill="x", pady=10, padx=5, ipadx=10, ipady=15)
        
        status_color = "#2ECC71" if status == "Running" else "#E74C3C" if status == "Failed" else "#95A5A6"
        status_icon = "● Running" if status == "Running" else "● Failed" if status == "Failed" else "○ Stopped"
        
        display_name = service.replace("llm_", "").replace(".service", "")
        if display_name.startswith("docker:"):
            display_name = "🐳 " + display_name.replace("docker:", "")
        else:
            display_name = "⚙️ " + display_name
            
        name_label = ctk.CTkLabel(card, text=display_name, font=ctk.CTkFont(size=20, weight="bold"))
        name_label.pack(side="left", padx=20)
        
        status_badge = ctk.CTkLabel(card, text=status_icon, text_color=status_color, font=ctk.CTkFont(size=14, weight="bold"))
        status_badge.pack(side="left", padx=10)
        
        # Buttons with beautiful colors
        btn_font = ctk.CTkFont(weight="bold")
        restart_btn = ctk.CTkButton(card, text="Restart", width=90, height=35, command=lambda: self.service_action(service, "restart"), font=btn_font, fg_color="#3498DB", hover_color="#2980B9")
        restart_btn.pack(side="right", padx=10)
        
        stop_btn = ctk.CTkButton(card, text="Stop", width=90, height=35, command=lambda: self.service_action(service, "stop"), font=btn_font, fg_color="#E74C3C", hover_color="#C0392B")
        stop_btn.pack(side="right", padx=10)
        
        start_btn = ctk.CTkButton(card, text="Start", width=90, height=35, command=lambda: self.service_action(service, "start"), font=btn_font, fg_color="#2ECC71", hover_color="#27AE60")
        start_btn.pack(side="right", padx=10)
        
        if service.startswith("docker:"):
            edit_btn = ctk.CTkButton(card, text="Edit Config", width=110, height=35, state="disabled", font=btn_font, fg_color="gray", hover_color="gray")
        else:
            edit_btn = ctk.CTkButton(card, text="Edit Config", width=110, height=35, command=lambda: self.open_editor(service), font=btn_font, fg_color="#F39C12", hover_color="#D35400")
        edit_btn.pack(side="right", padx=10)

    def service_action(self, service, action):
        if action in ["start", "stop", "restart"]:
            if service.startswith("docker:"):
                container = service.split(":")[1]
                self.ssh.run_command(f"docker {action} {container}", use_sudo=True)
            else:
                self.ssh.run_command(f"systemctl {action} {service}", use_sudo=True)
            self.load_services()

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
        
        self.title_label = ctk.CTkLabel(self, text="Download AI Model", font=ctk.CTkFont(size=32, weight="bold"))
        self.title_label.pack(pady=(0, 20), anchor="w")
        
        card = ctk.CTkFrame(self, corner_radius=15, fg_color=("gray85", "gray16"))
        card.pack(fill="both", expand=True)
        
        ctk.CTkLabel(card, text="HuggingFace Repository ID", font=ctk.CTkFont(weight="bold")).pack(pady=(30, 5), padx=40, anchor="w")
        self.repo_entry = ctk.CTkEntry(card, placeholder_text="e.g. Kbenkhaled/Qwen3.5-35B-A3B-NVFP4", height=40)
        self.repo_entry.pack(pady=(0, 20), padx=40, fill="x")
        
        ctk.CTkLabel(card, text="Local Destination Directory", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 5), padx=40, anchor="w")
        default_dir = self.app_settings.get("default_model_dir", "~/models")
        self.dir_entry = ctk.CTkEntry(card, height=40)
        self.dir_entry.insert(0, default_dir)
        self.dir_entry.pack(pady=(0, 20), padx=40, fill="x")
        
        self.download_btn = ctk.CTkButton(card, text="Start Download & Auto-Create Service", command=self.start_download, height=45, font=ctk.CTkFont(weight="bold"), fg_color="#3498DB", hover_color="#2980B9")
        self.download_btn.pack(pady=30, padx=40, fill="x")
        
        self.status_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=10, padx=40, anchor="w")
        
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
        
        self.title_label = ctk.CTkLabel(self, text="Register Existing Model", font=ctk.CTkFont(size=32, weight="bold"))
        self.title_label.pack(pady=(0, 20), anchor="w")
        
        card = ctk.CTkFrame(self, corner_radius=15, fg_color=("gray85", "gray16"))
        card.pack(fill="both", expand=True)
        
        self._add_input(card, "Service Name", "name_entry", "e.g. qwen-fast")
        self._add_input(card, "Absolute Model Path", "path_entry", "e.g. /home/sandeep/models/qwen.gguf")
        self._add_input(card, "Server Port", "port_entry", "e.g. 30005")
        self._add_input(card, "Model Alias", "alias_entry", "e.g. qwen-test")
        
        self.create_btn = ctk.CTkButton(card, text="Register & Start Service", command=self.create_service, height=45, font=ctk.CTkFont(weight="bold"), fg_color="#3498DB", hover_color="#2980B9")
        self.create_btn.pack(pady=30, padx=40, fill="x")
        
        self.status_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=10, padx=40, anchor="w")

    def _add_input(self, parent, label, attr_name, placeholder):
        ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(weight="bold")).pack(pady=(20, 5), padx=40, anchor="w")
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, height=40)
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
        
        self.title_label = ctk.CTkLabel(self, text="Application Settings", font=ctk.CTkFont(size=32, weight="bold"))
        self.title_label.pack(pady=(0, 20), anchor="w")
        
        card = ctk.CTkFrame(self, corner_radius=15, fg_color=("gray85", "gray16"))
        card.pack(fill="both", expand=True)
        
        ctk.CTkLabel(card, text="Default User (for systemd User=)", font=ctk.CTkFont(weight="bold")).pack(pady=(30, 5), padx=40, anchor="w")
        self.user_entry = ctk.CTkEntry(card, height=40)
        self.user_entry.insert(0, self.app.app_settings.get("default_user", "sandeep"))
        self.user_entry.pack(pady=(0, 20), padx=40, fill="x")
        
        ctk.CTkLabel(card, text="Default Working Directory", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 5), padx=40, anchor="w")
        self.workdir_entry = ctk.CTkEntry(card, height=40)
        self.workdir_entry.insert(0, self.app.app_settings.get("default_workdir", "/home/sandeep"))
        self.workdir_entry.pack(pady=(0, 20), padx=40, fill="x")
        
        ctk.CTkLabel(card, text="Default Model Download Directory", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 5), padx=40, anchor="w")
        self.modeldir_entry = ctk.CTkEntry(card, height=40)
        self.modeldir_entry.insert(0, self.app.app_settings.get("default_model_dir", "~/models"))
        self.modeldir_entry.pack(pady=(0, 20), padx=40, fill="x")
        
        ctk.CTkLabel(card, text="Default ExecStart (llama-server path)", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 5), padx=40, anchor="w")
        self.exec_entry = ctk.CTkEntry(card, height=40)
        self.exec_entry.insert(0, self.app.app_settings.get("default_exec", "/home/sandeep/llama.cpp/build/bin/llama-server"))
        self.exec_entry.pack(pady=(0, 20), padx=40, fill="x")
        
        ctk.CTkLabel(card, text="Docker Match Keywords (comma separated)", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 5), padx=40, anchor="w")
        self.docker_entry = ctk.CTkEntry(card, height=40)
        self.docker_entry.insert(0, self.app.app_settings.get("docker_keywords", "llm_, llama, vllm, ollama, comfy, wan"))
        self.docker_entry.pack(pady=(0, 20), padx=40, fill="x")
        
        self.save_btn = ctk.CTkButton(card, text="Save Settings", command=self.save_global_settings, height=45, font=ctk.CTkFont(weight="bold"), fg_color="#3498DB", hover_color="#2980B9")
        self.save_btn.pack(pady=30, padx=40, fill="x")
        
        self.status_label = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=10, padx=40, anchor="w")

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
        self.ssh = None
        self.app_settings = {}
        
        # Configure layout (1 row, 2 columns)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.withdraw()
        self.login_dialog = LoginDialog(self, self.on_login_success)

    def on_login_success(self, ssh_manager):
        self.ssh = ssh_manager
        self.geometry("1100x750")
        self.deiconify()
        self.setup_ui()

    def setup_ui(self):
        # Create Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1) # spacer
        
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Model Manager", font=ctk.CTkFont(size=22, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 30))
        
        btn_font = ctk.CTkFont(size=14, weight="bold")
        
        self.nav_btn_1 = ctk.CTkButton(self.sidebar_frame, text="Dashboard", font=btn_font, command=lambda: self.select_frame("dashboard"), fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w", height=45)
        self.nav_btn_1.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        
        self.nav_btn_2 = ctk.CTkButton(self.sidebar_frame, text="Download Model", font=btn_font, command=lambda: self.select_frame("download"), fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w", height=45)
        self.nav_btn_2.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        self.nav_btn_3 = ctk.CTkButton(self.sidebar_frame, text="Register Service", font=btn_font, command=lambda: self.select_frame("create"), fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w", height=45)
        self.nav_btn_3.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        
        self.nav_btn_4 = ctk.CTkButton(self.sidebar_frame, text="Settings", font=btn_font, command=lambda: self.select_frame("settings"), fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"), anchor="w", height=45)
        self.nav_btn_4.grid(row=4, column=0, padx=20, pady=5, sticky="ew")
        
        # Frames
        self.frames = {}
        self.frames["dashboard"] = DashboardTab(self, self.ssh)
        self.frames["download"] = AddModelTab(self, self.ssh, self.app_settings)
        self.frames["create"] = CreateServiceTab(self, self.ssh, self.app_settings)
        self.frames["settings"] = SettingsTab(self, self)
        
        # Grid all frames in column 1
        for frame in self.frames.values():
            frame.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
            
        self.select_frame("dashboard")

    def select_frame(self, name):
        buttons = {"dashboard": self.nav_btn_1, "download": self.nav_btn_2, "create": self.nav_btn_3, "settings": self.nav_btn_4}
        for key, btn in buttons.items():
            if key == name:
                btn.configure(fg_color=("gray75", "#2C3E50")) # Highlighted color
            else:
                btn.configure(fg_color="transparent")
                
        # Raise selected frame
        self.frames[name].tkraise()
        # Refresh dashboard auto if selected
        if name == "dashboard":
            self.frames[name].load_services()

if __name__ == "__main__":
    app = App()
    app.mainloop()
