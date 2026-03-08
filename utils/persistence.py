import json
import os
import discord

def _get_timestamp():
    return discord.utils.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def save_json_data(filepath: str, serializable_data: dict, success_msg: str):
    try:
        with open(filepath, 'w') as f:
            json.dump(serializable_data, f, indent=4)
        print(f"[{_get_timestamp()}] {success_msg}")
    except Exception as e:
        print(f"[{_get_timestamp()}] Error saving to {filepath}: {e}")

def load_json_data(filepath: str, empty_msg: str) -> dict:
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                loaded_data = json.load(f)
                return {int(k): v for k, v in loaded_data.items()}
        else:
            print(f"[{_get_timestamp()}] {empty_msg}")
            return {}
    except Exception as e:
        print(f"[{_get_timestamp()}] Error loading from {filepath}: {e}")
        return {}
