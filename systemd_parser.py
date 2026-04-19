import shlex

class SystemdParser:
    @staticmethod
    def parse_service_content(content):
        """Parses a systemd service file and extracts llama-server arguments."""
        lines = content.split('\n')
        config = {
            "description": "",
            "exec_start_path": "",
            "args": {},
            "raw_other_lines": [] # To rebuild the file
        }
        
        in_service = False
        exec_start_line = ""
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Description="):
                config["description"] = stripped.split("=", 1)[1]
            
            if stripped.startswith("ExecStart="):
                exec_start_line = stripped.split("=", 1)[1]
                # Keep accumulating if it ends with backslash
                if exec_start_line.endswith("\\"):
                    exec_start_line = exec_start_line[:-1]
                continue
                
            if exec_start_line and not config["exec_start_path"]:
                # If we are accumulating ExecStart
                if stripped.endswith("\\"):
                    exec_start_line += " " + stripped[:-1]
                else:
                    exec_start_line += " " + stripped
                    
                    # Parse the command line
                    parts = shlex.split(exec_start_line)
                    if parts:
                        config["exec_start_path"] = parts[0]
                        
                        # Very simple flag parsing
                        i = 1
                        while i < len(parts):
                            arg = parts[i]
                            if arg.startswith("-"):
                                if i + 1 < len(parts) and not parts[i+1].startswith("-"):
                                    config["args"][arg] = parts[i+1]
                                    i += 2
                                else:
                                    config["args"][arg] = True
                                    i += 1
                            else:
                                i += 1
                    
            elif not stripped.startswith("ExecStart="):
                config["raw_other_lines"].append(line)
                
        return config

    @staticmethod
    def build_service_content(config):
        """Rebuilds the service file content from the config."""
        lines = []
        exec_start_written = False
        
        for line in config["raw_other_lines"]:
            stripped = line.strip()
            if stripped.startswith("Description="):
                lines.append(f"Description={config['description']}")
            elif stripped == "[Service]" and not exec_start_written:
                lines.append(line)
                
                # Build ExecStart
                exec_lines = [f"ExecStart={config['exec_start_path']} \\"]
                arg_keys = list(config["args"].keys())
                for i, k in enumerate(arg_keys):
                    v = config["args"][k]
                    is_last = (i == len(arg_keys) - 1)
                    suffix = "" if is_last else " \\"
                    
                    if v is True:
                        exec_lines.append(f"  {k}{suffix}")
                    else:
                        exec_lines.append(f"  {k} {v}{suffix}")
                
                lines.extend(exec_lines)
                exec_start_written = True
            else:
                lines.append(line)
                
        return "\n".join(lines)
