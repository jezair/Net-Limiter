# app_ui.py
import customtkinter as ctk
import sys
import json
import keyboard
import threading
import winsound
from throttler_logic import ThrottlerLogic

CONFIG_FILE = "config.json"


class ThrottlerApp(ctk.CTk):
    def __init__(self, logic: ThrottlerLogic, initial_config: dict):
        super().__init__()
        self.logic = logic
        self.config = initial_config
        self.app_dict = {}
        # <<< ДОБАВИЛИ ПЕРЕМЕННУЮ ДЛЯ ХРАНЕНИЯ ВЫБРАННОГО ПРИЛОЖЕНИЯ
        self.last_selected_app_name = self.config.get("last_app", "")

        self.PURPLE = "#8A2BE2"
        self.PURPLE_HOVER = "#7A1DD2"
        self.DARK_HOVER = "#333333"
        self.LIGHT_HOVER = "#DCDCDC"

        self.title("Network Throttler")
        self.geometry("550x400")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        ctk.set_appearance_mode(self.config["theme"])

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        self.theme_button = ctk.CTkButton(self.main_frame, text="", font=("Segoe UI Emoji", 20), width=40,
                                          fg_color="transparent", text_color=self.PURPLE, command=self.toggle_theme)
        self.theme_button.grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.update_theme_button_icon()

        self.label_speed = ctk.CTkLabel(self.main_frame, text="Speed Limit:", font=("Arial", 14))
        self.label_speed.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.entry_speed = ctk.CTkEntry(self.main_frame, placeholder_text="10", border_color=self.PURPLE)
        self.entry_speed.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        self.entry_speed.insert(0, self.config["speed"])
        self.unit_menu = ctk.CTkOptionMenu(self.main_frame, values=["KB/s", "MB/s"], fg_color=self.PURPLE,
                                           button_color=self.PURPLE, button_hover_color=self.PURPLE_HOVER,
                                           dropdown_fg_color=self.PURPLE, dropdown_hover_color=self.PURPLE_HOVER,
                                           command=self.update_rate_limit_from_ui)
        self.unit_menu.grid(row=1, column=3, padx=10, pady=5, sticky="e")
        self.unit_menu.set(self.config["unit"])

        self.label_app = ctk.CTkLabel(self.main_frame, text="Target App:", font=("Arial", 14))
        self.label_app.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.app_menu = ctk.CTkOptionMenu(self.main_frame, values=["Loading..."], fg_color=self.PURPLE,
                                          button_color=self.PURPLE, button_hover_color=self.PURPLE_HOVER,
                                          dropdown_fg_color=self.PURPLE, dropdown_hover_color=self.PURPLE_HOVER,
                                          command=self.on_app_selected)
        self.app_menu.grid(row=2, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        self.refresh_button = ctk.CTkButton(self.main_frame, text="🔄 Refresh", width=100, fg_color=self.PURPLE,
                                            hover_color=self.PURPLE_HOVER, command=self.refresh_app_list)
        self.refresh_button.grid(row=2, column=3, padx=10, pady=5, sticky="e")

        self.label_hotkey = ctk.CTkLabel(self.main_frame, text="Hotkey:", font=("Arial", 14))
        self.label_hotkey.grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.entry_hotkey = ctk.CTkEntry(self.main_frame, placeholder_text="f2", border_color=self.PURPLE)
        self.entry_hotkey.grid(row=3, column=1, columnspan=2, padx=10, pady=5, sticky="ew")
        self.entry_hotkey.insert(0, self.config["hotkey"])
        self.entry_hotkey.configure(state="readonly")
        self.record_button = ctk.CTkButton(self.main_frame, text="Set Key", width=100, fg_color=self.PURPLE,
                                           hover_color=self.PURPLE_HOVER, command=self.start_recording_hotkey)
        self.record_button.grid(row=3, column=3, padx=10, pady=5, sticky="e")

        self.toggle_button = ctk.CTkButton(self.main_frame, text="Activate Hotkey", font=("Arial", 16),
                                           fg_color=self.PURPLE, hover_color=self.PURPLE_HOVER,
                                           command=self.toggle_hotkey_listener)
        self.toggle_button.grid(row=4, column=0, columnspan=4, padx=10, pady=20, sticky="ew")

        self.status_label = ctk.CTkLabel(self.main_frame, text="Status: Stopped", text_color="gray")
        self.status_label.grid(row=5, column=0, columnspan=4, padx=10, pady=5, sticky="ew")

        self.main_frame.grid_columnconfigure(1, weight=1)
        self.after(100, self._prime_keyboard_listener)
        self.after(200, self.refresh_app_list)

    def refresh_app_list(self):
        self.update_status("Status: Refreshing list...", "orange")
        self.app_dict = self.logic.get_running_apps()
        app_names = list(self.app_dict.keys())

        if app_names:
            self.app_menu.configure(values=app_names)
            # <<< ИЗМЕНЕНО: Пытаемся выбрать последнее сохраненное приложение
            if self.last_selected_app_name and self.last_selected_app_name in app_names:
                self.app_menu.set(self.last_selected_app_name)
                self.on_app_selected(self.last_selected_app_name)
            else:
                # Если не нашли, выбираем первое в списке
                self.app_menu.set(app_names[0])
                self.on_app_selected(app_names[0])
        else:
            self.app_menu.configure(values=["No apps with windows found"])
            self.app_menu.set("No apps with windows found")
            self.logic.set_target_pid(None)
            self.update_status("Status: No apps found. Run an app and refresh.", "gray")
        print("UI: App list refreshed.")

    def on_app_selected(self, selected_app_name: str):
        target_pid = self.app_dict.get(selected_app_name)
        self.logic.set_target_pid(target_pid)
        # <<< ИЗМЕНЕНО: Запоминаем выбор пользователя
        self.last_selected_app_name = selected_app_name
        self.update_status(f"Target selected: {selected_app_name}", "gray")

    def _save_config(self):
        # <<< ИЗМЕНЕНО: Добавляем last_app в сохранение
        current_config = {
            "speed": self.entry_speed.get(),
            "unit": self.unit_menu.get(),
            "hotkey": self.entry_hotkey.get(),
            "theme": ctk.get_appearance_mode().lower(),
            "last_app": self.last_selected_app_name
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(current_config, f, indent=4)
        print("Config saved.")

    # ... (остальной код файла остается без изменений) ...

    def toggle_hotkey_listener(self):
        if self.logic.is_running:
            winsound.PlaySound("SystemExit", winsound.SND_ASYNC)
            self.logic.stop_listener()
            keyboard.unhook_all_hotkeys()
            self.toggle_button.configure(text="Activate Hotkey")
            self.update_status("Status: Stopped", "gray")
            self.app_menu.configure(state="normal")
            self.refresh_button.configure(state="normal")
            self.record_button.configure(state="normal")
        else:
            if not self.logic.target_pid:
                winsound.PlaySound("SystemHand", winsound.SND_ASYNC)
                self.update_status("Error: Please refresh and select a target app!", "red")
                return
            hotkey = self.entry_hotkey.get().lower()
            if not hotkey:
                winsound.PlaySound("SystemHand", winsound.SND_ASYNC)
                self.update_status("Error: Hotkey cannot be empty!", "red")
                return
            try:
                keyboard.unhook_all_hotkeys()
                keyboard.add_hotkey(hotkey, self.logic.toggle_throttle_for_target)
            except Exception as e:
                winsound.PlaySound("SystemHand", winsound.SND_ASYNC)
                self.update_status(f"Error: Invalid hotkey! ({e})", "red")
                return

            winsound.PlaySound("SystemStart", winsound.SND_ASYNC)
            self.update_rate_limit_from_ui()
            self.logic.start_listener()
            self.toggle_button.configure(text="Deactivate Hotkey")
            self.update_status(f"Listener active! Press '{hotkey.upper()}' in target window.", "green")
            self.app_menu.configure(state="disabled")
            self.refresh_button.configure(state="disabled")
            self.record_button.configure(state="disabled")

    def _prime_keyboard_listener(self):
        try:
            dummy_hotkey = "ctrl+alt+shift+f24"
            keyboard.add_hotkey(dummy_hotkey, lambda: None)
            keyboard.remove_hotkey(dummy_hotkey)
        except:
            pass

    def update_rate_limit_from_ui(self, _=None):
        try:
            speed = float(self.entry_speed.get())
            unit = self.unit_menu.get()
            bytes_per_sec = speed * (1024 if unit == "KB/s" else 1024 * 1024)
            self.logic.set_rate_limit(bytes_per_sec)
            self._save_config()
            return True
        except ValueError:
            return False

    def on_closing(self):
        self._save_config()
        self.logic.stop_listener()
        self.destroy()
        sys.exit()

    def update_status(self, message, color):
        self.status_label.configure(text=message, text_color=color)

    def toggle_theme(self):
        new_mode = "light" if ctk.get_appearance_mode().lower() == "dark" else "dark"
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
        self.after(0, self.on_hotkey_recorded, keyboard.read_hotkey(suppress=False))

    def on_hotkey_recorded(self, hotkey_name):
        self.entry_hotkey.configure(state="normal")
        self.entry_hotkey.delete(0, "end")
        self.entry_hotkey.insert(0, hotkey_name)
        self.entry_hotkey.configure(state="readonly")
        self.record_button.configure(text="Set Key", state="normal")
        self.main_frame.focus_set()
        self._save_config()