# app_ui.py
import customtkinter as ctk
import keyboard
import sys
import threading
import json
from throttler_logic import ThrottlerLogic

CONFIG_FILE = "config.json"


class ThrottlerApp(ctk.CTk):
    def __init__(self, logic: ThrottlerLogic, initial_config: dict):
        super().__init__()
        self.logic = logic
        self.config = initial_config

        # --- Настройка кастомной темы ---
        self.PURPLE = "#8A2BE2"
        self.PURPLE_HOVER = "#7A1DD2"
        self.DARK_HOVER = "#333333"
        self.LIGHT_HOVER = "#DCDCDC"

        self.title("Network Throttler")
        self.geometry("450x350")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        ctk.set_appearance_mode(self.config["theme"])

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        # --- ВИДЖЕТЫ (без изменений) ---
        self.theme_button = ctk.CTkButton(self.main_frame, text="", font=("Segoe UI Emoji", 20), width=40,
                                          fg_color="transparent", text_color=self.PURPLE, command=self.toggle_theme)
        self.theme_button.grid(row=0, column=3, padx=5, pady=10, sticky="e")
        self.update_theme_button_icon()

        self.label_speed = ctk.CTkLabel(self.main_frame, text="Speed Limit:", font=("Arial", 14))
        self.label_speed.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.entry_speed = ctk.CTkEntry(self.main_frame, placeholder_text="10", border_color=self.PURPLE)
        self.entry_speed.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.entry_speed.insert(0, self.config["speed"])

        self.unit_menu = ctk.CTkOptionMenu(self.main_frame, values=["KB/s", "MB/s"], fg_color=self.PURPLE,
                                           button_color=self.PURPLE, button_hover_color=self.PURPLE_HOVER,
                                           dropdown_fg_color=self.PURPLE, dropdown_hover_color=self.PURPLE_HOVER,
                                           command=self.update_rate_limit_from_ui)
        self.unit_menu.grid(row=1, column=2, columnspan=2, padx=10, pady=10, sticky="e")
        self.unit_menu.set(self.config["unit"])

        self.label_hotkey = ctk.CTkLabel(self.main_frame, text="Hotkey:", font=("Arial", 14))
        self.label_hotkey.grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.entry_hotkey = ctk.CTkEntry(self.main_frame, placeholder_text="f2", border_color=self.PURPLE)
        self.entry_hotkey.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        self.entry_hotkey.insert(0, self.config["hotkey"])
        self.entry_hotkey.configure(state="readonly")

        self.record_button = ctk.CTkButton(self.main_frame, text="Set Key", width=80, fg_color=self.PURPLE,
                                           hover_color=self.PURPLE_HOVER, command=self.start_recording_hotkey)
        self.record_button.grid(row=2, column=2, columnspan=2, padx=(0, 10), pady=10, sticky="e")

        self.toggle_button = ctk.CTkButton(self.main_frame, text="Start Throttling", font=("Arial", 16),
                                           fg_color=self.PURPLE, hover_color=self.PURPLE_HOVER,
                                           command=self.toggle_throttling)
        self.toggle_button.grid(row=3, column=0, columnspan=4, padx=10, pady=20, sticky="ew")

        self.status_label = ctk.CTkLabel(self.main_frame, text="Status: Stopped", text_color="gray")
        self.status_label.grid(row=4, column=0, columnspan=4, padx=10, pady=10, sticky="ew")

        self.main_frame.grid_columnconfigure(1, weight=1)

        # --- <<< ВОТ ГЛАВНОЕ ИСПРАВЛЕНИЕ ---
        # "Пробуждаем" библиотеку keyboard через 100 миллисекунд после запуска окна
        self.after(100, self._prime_keyboard_listener)

    def _prime_keyboard_listener(self):
        """
        Принудительно инициализирует прослушиватель клавиатуры,
        чтобы избежать ошибок при первой регистрации горячей клавиши.
        """
        try:
            print("Priming keyboard listener...")
            # Регистрируем и тут же удаляем сложную, неиспользуемую клавишу.
            # Это действие "пробуждает" библиотеку.
            dummy_hotkey = "ctrl+alt+shift+f24"
            keyboard.add_hotkey(dummy_hotkey, lambda: None)
            keyboard.remove_hotkey(dummy_hotkey)
            print("Keyboard listener primed successfully.")
        except Exception as e:
            # Если не получилось, ничего страшного, но выводим информацию.
            print(f"Could not prime keyboard listener: {e}")

    def _save_config(self):
        current_config = {"speed": self.entry_speed.get(), "unit": self.unit_menu.get(),
                          "hotkey": self.entry_hotkey.get(), "theme": ctk.get_appearance_mode().lower()}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(current_config, f, indent=4)
        print("Config saved.")

    def toggle_theme(self):
        current_mode = ctk.get_appearance_mode()
        new_mode = "light" if current_mode.lower() == "dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        self.update_theme_button_icon()
        self._save_config()

    def update_theme_button_icon(self):
        if ctk.get_appearance_mode().lower() == "dark":
            self.theme_button.configure(text="☀️", hover_color=self.DARK_HOVER)
        else:
            self.theme_button.configure(text="🌙", hover_color=self.LIGHT_HOVER)

    def start_recording_hotkey(self):
        self.record_button.configure(text="Press...", state="disabled")
        threading.Thread(target=self.read_hotkey_thread, daemon=True).start()

    def read_hotkey_thread(self):
        hotkey_str = keyboard.read_hotkey(suppress=False)
        self.after(0, self.on_hotkey_recorded, hotkey_str)

    def on_hotkey_recorded(self, hotkey_name):
        self.entry_hotkey.configure(state="normal")
        self.entry_hotkey.delete(0, "end")
        self.entry_hotkey.insert(0, hotkey_name)
        self.entry_hotkey.configure(state="readonly")
        self.record_button.configure(text="Set Key", state="normal")
        self.main_frame.focus_set()
        self._save_config()

    def update_status(self, message, color):
        self.status_label.configure(text=message, text_color=color)

    def toggle_throttling(self):
        if self.logic.is_running:
            self.logic.stop()
            keyboard.unhook_all_hotkeys()
            self.toggle_button.configure(text="Start Throttling")
            self.update_status("Status: Stopped", "gray")
        else:
            if not self.update_rate_limit_from_ui(): return
            hotkey = self.entry_hotkey.get().lower()
            if not hotkey:
                self.update_status("Error: Hotkey cannot be empty!", "red")
                return
            try:
                # Полная очистка перед регистрацией для надежности
                keyboard.unhook_all_hotkeys()
                keyboard.add_hotkey(hotkey, self.logic.toggle_pids)
            except Exception as e:
                self.update_status(f"Error: Invalid hotkey! ({e})", "red")
                return
            self.logic.start()
            self.toggle_button.configure(text="Stop Throttling")
            self.update_status(f"Status: Running. Press '{hotkey.upper()}' to toggle.", "green")

    def update_rate_limit_from_ui(self, _=None):
        try:
            speed = float(self.entry_speed.get())
            unit = self.unit_menu.get()
            bytes_per_sec = speed * (1024 if unit == "KB/s" else 1024 * 1024)
            self.logic.set_rate_limit(bytes_per_sec)
            self.update_status("Status: Ready", "gray")
            self._save_config()
            return True
        except ValueError:
            self.update_status("Error: Invalid speed value!", "red")
            return False

    def on_closing(self):
        self._save_config()
        self.logic.stop()
        self.destroy()
        sys.exit()