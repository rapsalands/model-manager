import paramiko
import select
import time

class SSHManager:
    def __init__(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.host = ""
        self.username = ""
        self.key_path = ""
        self.sudo_password = ""
        self.connected = False

    def connect(self, host, username, key_path, sudo_password=""):
        self.host = host
        self.username = username
        self.key_path = key_path
        self.sudo_password = sudo_password
        
        try:
            self.client.connect(hostname=host, username=username, key_filename=key_path, timeout=5)
            self.connected = True
            
            # Verify the sudo password actually works
            success, out = self.run_command("echo sudo_ok", use_sudo=True)
            if not success or "sudo_ok" not in out:
                self.disconnect()
                return False, "SSH Connected, but Sudo password is incorrect or user lacks sudo privileges."
                
            return True, "Connected successfully."
        except Exception as e:
            self.connected = False
            return False, str(e)

    def disconnect(self):
        if self.connected:
            self.client.close()
            self.connected = False

    def run_command(self, command, use_sudo=False):
        if not self.connected:
            return False, "Not connected"

        final_command = command
        if use_sudo and self.sudo_password:
            # We use sudo -S to read password from stdin
            final_command = f"echo '{self.sudo_password}' | sudo -S {command}"
        elif use_sudo:
             final_command = f"sudo {command}"

        try:
            stdin, stdout, stderr = self.client.exec_command(final_command)
            exit_status = stdout.channel.recv_exit_status()
            out = stdout.read().decode('utf-8').strip()
            err = stderr.read().decode('utf-8').strip()
            
            if exit_status == 0:
                return True, out
            else:
                return False, err if err else out
        except Exception as e:
            return False, str(e)

    def run_tmux_command(self, session_name, command):
        """Runs a command inside a new detached tmux session."""
        # Ensure tmux is installed
        self.run_command("sudo apt-get install -y tmux", use_sudo=True)
        # Kill if exists
        self.run_command(f"tmux kill-session -t {session_name}")
        # Create detached session running the command
        tmux_cmd = f"tmux new-session -d -s {session_name} '{command}; read'"
        return self.run_command(tmux_cmd)

    def list_services(self, pattern="*.service"):
        # Deprecated: use get_services_with_status instead for speed
        return list(self.get_services_with_status().keys())

    def get_services_with_status(self, docker_keywords="llm_|llama|vllm|ollama|comfy|wan"):
        # We find services and their statuses in a single bash command to save SSH overhead
        # This makes the Dashboard Refresh button extremely fast
        cmd = 'for f in /etc/systemd/system/llm_*.service ~/.config/systemd/user/llm_*.service; do if [ -f "$f" ]; then name=$(basename "$f"); status=$(systemctl is-active "$name" 2>/dev/null || echo stopped); echo "$name|$status"; fi; done; if command -v docker >/dev/null 2>&1; then docker ps -a --format "{{.Names}}|{{.State}}|{{.Image}}" 2>/dev/null | grep -iE "%s" | while IFS="|" read -r name state image; do if [ "$state" = "running" ]; then status="active"; elif [ "$state" = "exited" ] || [ "$state" = "created" ]; then status="stopped"; else status="failed"; fi; echo "docker:$name|$status"; done; fi; exit 0' % docker_keywords
        success, out = self.run_command(f"sh -c '{cmd}'", use_sudo=True)
        
        results = {}
        if out:
            for line in out.strip().split('\n'):
                if '|' in line:
                    name, state = line.split('|', 1)
                    if state == 'active': 
                        status = 'Running'
                    elif state == 'failed': 
                        status = 'Failed'
                    else: 
                        status = 'Stopped'
                    results[name] = status
        return results

    def get_service_status(self, service_name):
        success, out = self.run_command(f"systemctl status {service_name}", use_sudo=True)
        if "Active: active (running)" in out:
            return "Running"
        elif "Active: failed" in out:
            return "Failed"
        else:
            return "Stopped"

    def read_file(self, path):
        success, out = self.run_command(f"cat {path}", use_sudo=True)
        return out if success else ""

    def write_file(self, path, content):
        # We need to write content safely using sudo tee
        import base64
        encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        cmd = f"echo '{encoded}' | base64 --decode | sudo tee {path} > /dev/null"
        return self.run_command(cmd, use_sudo=True)
