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
        "theme": "dark"
    }
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = defaults.copy()
            config.update(json.load(f))

            # --- УЛУЧШЕННАЯ ПРОВЕРКА ---
            # 1. Получаем значение hotkey из конфига.
            hotkey_value = config.get("hotkey")

            # 2. Проверяем, существует ли оно и является ли строкой.
            #    Если да, убираем пробелы по краям.
            if hotkey_value and isinstance(hotkey_value, str):
                config["hotkey"] = hotkey_value.strip()
            else:
                # Если значение не строка или отсутствует, ставим по умолчанию.
                config["hotkey"] = defaults["hotkey"]

            # 3. Финальная проверка: если после очистки строка пустая,
            #    ставим значение по умолчанию.
            if not config["hotkey"]:
                print("Warning: Hotkey in config was empty after cleaning. Using default 'f2'.")
                config["hotkey"] = defaults["hotkey"]

            return config

    except (FileNotFoundError, json.JSONDecodeError):
        # Если файла нет или он поврежден, возвращаем стандартные настройки.
        return defaults


if __name__ == "__main__":
    # 1. Загружаем проверенный и очищенный конфиг
    config = load_config()

    # 2. Создаём экземпляр логики ("мозг")
    logic = ThrottlerLogic()

    # 3. Создаём экземпляр интерфейса ("лицо"), передавая ему логику и конфиг
    app = ThrottlerApp(logic, initial_config=config)

    # 4. Связываем их: даём "мозгу" способ общаться с "лицом"
    logic.status_callback = app.update_status

    # 5. Запускаем приложение
    app.mainloop()