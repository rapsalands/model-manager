import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ssh_manager import SSHManager

class TestSSHManager:
    @pytest.fixture
    def mock_ssh_client(self):
        with patch('ssh_manager.paramiko.SSHClient') as mock_client:
            client_instance = mock_client.return_value
            yield client_instance

    def test_run_command_formatting(self, mock_ssh_client):
        """Test that commands are correctly wrapped when use_sudo is true."""
        manager = SSHManager()
        manager.client = mock_ssh_client
        manager.connected = True
        manager.sudo_password = "mypassword"
        
        # Mock the exec_command return values
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_stdout.read.return_value = b"success"
        mock_stderr.read.return_value = b""
        
        mock_ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        # Run command with sudo
        success, out = manager.run_command("systemctl restart myservice", use_sudo=True)
        
        # Verify the command was constructed correctly with the password piped in
        mock_ssh_client.exec_command.assert_called_once_with("echo 'mypassword' | sudo -S systemctl restart myservice")
        assert success is True
        assert out == "success"

    def test_get_services_with_status_formatting(self, mock_ssh_client):
        """Test that the complex bash string used for fetching statuses has no syntax issues."""
        manager = SSHManager()
        manager.client = mock_ssh_client
        manager.connected = True
        
        # Mock execution
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdout.channel.recv_exit_status.return_value = 0
        
        # Mock the output of our complex command
        mock_stdout.read.return_value = b"llm_qwen80b.service|active\nllm_test.service|stopped"
        mock_stderr.read.return_value = b""
        
        mock_ssh_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        
        results = manager.get_services_with_status()
        
        # Grab the actual command sent to SSH
        actual_command_sent = mock_ssh_client.exec_command.call_args[0][0]
        
        # Assert the command uses double quotes or avoids single quotes properly
        assert "sh -c '" in actual_command_sent
        assert "echo stopped" in actual_command_sent # Should not have single quotes around stopped
        
        # Assert the parsing works
        assert "llm_qwen80b.service" in results
        assert results["llm_qwen80b.service"] == "Running"
        assert results["llm_test.service"] == "Stopped"
