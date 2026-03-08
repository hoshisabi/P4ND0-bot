import os
import json
import pytest
from utils.persistence import save_json_data, load_json_data

def test_save_and_load_json_data(tmp_path):
    filepath = tmp_path / "test_data.json"
    filepath_str = str(filepath)
    
    # Data with string keys that should be converted to integers on load
    test_data = {"123": "value1", "456": {"nested": "value2"}}
    success_msg = "Saved successfully!"
    
    # Test saving
    save_json_data(filepath_str, test_data, success_msg)
    
    assert os.path.exists(filepath_str)
    
    # Verify file content
    with open(filepath_str, 'r') as f:
        saved_data = json.load(f)
    assert saved_data == test_data

    # Test loading
    empty_msg = "Starting empty"
    loaded_data = load_json_data(filepath_str, empty_msg)
    
    # load_json_data converts top-level keys to integers
    expected_data = {123: "value1", 456: {"nested": "value2"}}
    assert loaded_data == expected_data

def test_load_nonexistent_file(tmp_path, capsys):
    filepath = tmp_path / "nonexistent.json"
    empty_msg = "File not found message"
    
    loaded_data = load_json_data(str(filepath), empty_msg)
    
    assert loaded_data == {}
    captured = capsys.readouterr()
    assert empty_msg in captured.out

def test_load_invalid_json(tmp_path, capsys):
    filepath = tmp_path / "invalid.json"
    filepath.write_text("not json")
    
    loaded_data = load_json_data(str(filepath), "Empty message")
    
    assert loaded_data == {}
    captured = capsys.readouterr()
    assert "Error loading from" in captured.out
