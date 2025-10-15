# main.py
import json
from app_ui import ThrottlerApp
from throttler_logic import ThrottlerLogic

CONFIG_FILE = "config.json"


def load_config():
    """Загружает настройки из файла. Возвращает словарь с настройками."""
    defaults = {
        "speed": "1",
        "unit": "KB/s",
        "hotkey": "f2",
        "theme": "dark"
    }
    try:
        with open(CONFIG_FILE, 'r') as f:
            # Обновляем значения по умолчанию загруженными, чтобы ничего не сломалось,
            # если в будущем в конфиг добавятся новые ключи.
            config = defaults.copy()
            config.update(json.load(f))
            return config
    except (FileNotFoundError, json.JSONDecodeError):
        # Если файла нет или он поврежден, возвращаем настройки по умолчанию.
        return defaults


if __name__ == "__main__":
    # 1. Загружаем конфиг ПЕРЕД созданием чего-либо
    config = load_config()

    # 2. Создаём экземпляр логики ("мозг")
    logic = ThrottlerLogic()

    # 3. Создаём экземпляр интерфейса ("лицо"), передавая ему логику и конфиг
    app = ThrottlerApp(logic, initial_config=config)

    # 4. Связываем их: даём "мозгу" способ общаться с "лицом"
    logic.status_callback = app.update_status

    # 5. Запускаем приложение
    app.mainloop()