import pytest
import sys
import os

# Add parent directory to path so we can import systemd_parser
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from systemd_parser import SystemdParser

SAMPLE_SERVICE = """[Unit]
Description=Qwen3.0 80B Llama Server
After=network.target

[Service]
ExecStart=/home/sandeep/llama.cpp/build/bin/llama-server \\
  -m /home/sandeep/models/qwen.gguf \\
  -c 124000 \\
  --host 0.0.0.0 \\
  --port 30001 \\
  --flash-attn on \\
  --threads 24 \\
  --jinja \\
  --alias qwen80b

Restart=always
User=sandeep

[Install]
WantedBy=multi-user.target
"""

def test_parse_service_content():
    config = SystemdParser.parse_service_content(SAMPLE_SERVICE)
    
    assert config["description"] == "Qwen3.0 80B Llama Server"
    assert config["exec_start_path"] == "/home/sandeep/llama.cpp/build/bin/llama-server"
    
    args = config["args"]
    assert args["-m"] == "/home/sandeep/models/qwen.gguf"
    assert args["-c"] == "124000"
    assert args["--port"] == "30001"
    assert args["--jinja"] is True  # Boolean flag
    assert args["--flash-attn"] == "on"
    
def test_build_service_content():
    config = SystemdParser.parse_service_content(SAMPLE_SERVICE)
    
    # Modify some arguments
    config["args"]["--port"] = "8080"
    config["description"] = "Updated Model"
    
    new_content = SystemdParser.build_service_content(config)
    
    assert "Description=Updated Model" in new_content
    assert "--port 8080" in new_content
    assert "--jinja" in new_content
    assert "[Install]" in new_content
