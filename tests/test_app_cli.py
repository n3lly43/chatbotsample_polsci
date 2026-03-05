import pytest

def test_cli_commands_exist():
    from app_cli import handle_command
    assert callable(handle_command)

def test_handle_command_help():
    from app_cli import handle_command
    result = handle_command("/help", cfg={}, state={})
    assert result is not None
    assert "quit" in result.lower() or "help" in result.lower()

def test_handle_command_unknown():
    from app_cli import handle_command
    result = handle_command("What is nonviolent resistance?", cfg={}, state={})
    assert result is None
