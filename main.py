# main.py
import json
from app_ui import ThrottlerApp
from throttler_logic import ThrottlerLogic

CONFIG_FILE = "config.json"


def load_config():
    """Загружает настройки и проверяет их на корректность."""
    defaults = {
        "speed": "10",
        "unit": "KB/s",
        "hotkey": "f2",
        "theme": "dark",
        "last_app": ""  # <<< ДОБАВИЛИ НОВУЮ НАСТРОЙКУ
    }
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = defaults.copy()
            config.update(json.load(f))

            hotkey_value = config.get("hotkey")
            if hotkey_value and isinstance(hotkey_value, str):
                config["hotkey"] = hotkey_value.strip()
            else:
                config["hotkey"] = defaults["hotkey"]

            if not config["hotkey"]:
                print("Warning: Hotkey in config was empty after cleaning. Using default 'f2'.")
                config["hotkey"] = defaults["hotkey"]

            return config

    except (FileNotFoundError, json.JSONDecodeError):
        return defaults


if __name__ == "__main__":
    config = load_config()
    logic = ThrottlerLogic()
    app = ThrottlerApp(logic, initial_config=config)
    logic.status_callback = app.update_status
    app.mainloop()