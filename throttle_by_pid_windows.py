"""
throttle_by_pid_windows.py (Single-Loop Version)

Требования: запустить от администратора.
pip install pydivert psutil keyboard pywin32
"""

import time
import threading
import psutil
import pydivert
import keyboard
import win32gui
import win32process

# Параметры
RATE_BYTES_PER_SEC = 1024  # 1 KB/s
WINDIVERT_FILTER = "outbound and ip"

# Структуры (теперь намного проще)
throttled_pids = set()      # PIDs, для которых включено ограничение
token_buckets = {}          # pid -> {'tokens': float, 'last': float}

# --- Вспомогательные функции (остаются без изменений) ---
def get_foreground_pid():
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return pid
    except Exception:
        return None

def map_packet_to_pid(packet):
    try:
        lport = packet.src_port
        raddr = packet.dst_addr
        rport = packet.dst_port
    except Exception:
        return None

    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.laddr and conn.laddr.port == lport:
                if not conn.raddr or (conn.raddr.ip == raddr and conn.raddr.port == rport):
                    return conn.pid
        return None
    except Exception:
        return None

# --- Функция переключения (теперь она просто меняет set) ---
def on_f2():
    parent_pid = get_foreground_pid()
    if not parent_pid:
        print("Не удалось определить PID foreground-приложения.")
        return

    try:
        parent_process = psutil.Process(parent_pid)
        child_processes = parent_process.children(recursive=True)
        pids_to_toggle = [p.pid for p in child_processes] + [parent_pid]
    except psutil.NoSuchProcess:
        pids_to_toggle = [parent_pid]

    if parent_pid in throttled_pids:
        # ВЫКЛЮЧАЕМ: просто удаляем все PID из множества
        for pid in pids_to_toggle:
            throttled_pids.discard(pid) # .discard не вызовет ошибку, если pid нет
        print(f"Отключил ограничение для группы процессов (PID {parent_pid} и дочерние).")
    else:
        # ВКЛЮЧАЕМ: просто добавляем все PID в множество
        for pid in pids_to_toggle:
            throttled_pids.add(pid)
        print(f"Включил ограничение (1 KB/s) для группы процессов (PID {parent_pid} и дочерние).")

# --- Основной цикл (ВСЯ ЛОГИКА ТЕПЕРЬ ЗДЕСЬ) ---
def packet_loop():
    print("Нажмите F2, чтобы переключить ограничение для foreground-приложения.")
    keyboard.add_hotkey('f2', on_f2)

    try:
        with pydivert.WinDivert(WINDIVERT_FILTER) as w:
            print("WinDivert открыт, перехват пакетов...")
            for pkt in w:
                pid = map_packet_to_pid(pkt)

                # Проверяем, нужно ли ограничивать этот PID
                if pid is not None and pid in throttled_pids:
                    # Да, нужно. Вся логика ограничения прямо здесь.

                    # 1. Убедимся, что для PID есть "ведро токенов"
                    if pid not in token_buckets:
                        token_buckets[pid] = {'tokens': RATE_BYTES_PER_SEC, 'last': time.time()}

                    bucket = token_buckets[pid]
                    packet_len = len(pkt.raw)

                    # 2. Пополняем токены с момента последнего пополнения
                    now = time.time()
                    elapsed = now - bucket['last']
                    if elapsed > 0:
                        bucket['tokens'] += elapsed * RATE_BYTES_PER_SEC
                        # Не даём токенам копиться бесконечно
                        if bucket['tokens'] > RATE_BYTES_PER_SEC:
                            bucket['tokens'] = RATE_BYTES_PER_SEC
                        bucket['last'] = now

                    # 3. Проверяем, хватает ли токенов
                    if bucket['tokens'] < packet_len:
                        # Не хватает. Считаем, сколько нужно подождать.
                        wait_time = (packet_len - bucket['tokens']) / RATE_BYTES_PER_SEC
                        time.sleep(wait_time)
                        # "Доплачиваем" токены за время ожидания
                        bucket['tokens'] += wait_time * RATE_BYTES_PER_SEC

                    # 4. Тратим токены и отправляем пакет
                    bucket['tokens'] -= packet_len
                    w.send(pkt)
                else:
                    # Нет, не нужно. Просто отправляем пакет немедленно.
                    w.send(pkt)

    except Exception as e:
        print(f"Критическая ошибка WinDivert/pydivert: {e}")
        print("Убедитесь, что скрипт запущен от администратора.")

# --- Запуск ---
if __name__ == "__main__":
    # Запускаем всё в одном главном потоке
    packet_loop()
    print("Выход.")