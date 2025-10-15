"""
throttle_by_pid_windows.py

Требования: запустить от администратора.
pip install pydivert psutil keyboard pywin32
"""

import time
import threading
import queue
import psutil
import pydivert
import keyboard
import win32gui
import win32process
import socket

# Параметры
RATE_BYTES_PER_SEC = 1024  # 1 KB/s
WINDIVERT_FILTER = "outbound and ip" #"outbound and (ip or ip6)"  # перехватываем исходящие IP пакеты (IPv4 | IPv6 можно убрать/добавить)

# Структуры
throttled_pids = set()  # PIDs, для которых включено ограничение
buffers = {}            # pid -> Queue() (очередь пакетов (bytes, meta))
token_buckets = {}      # pid -> (tokens, last_time)
buffers_lock = threading.Lock()

# Вспомогательные функции
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
    """
    Пытаемся сопоставить IP-пакет к PID через psutil.net_connections.
    Возвращаем PID или None.
    """
    try:
        # Получим локальный и удалённый адреса/порты
        # pydivert.Packet имеет поля: src_addr, src_port, dst_addr, dst_port, protocol
        # Некоторые варианты: у pydivert-пакета атрибуты могут отличаться, но обычно эти есть.
        laddr = packet.src_addr
        raddr = packet.dst_addr
        lport = packet.src_port
        rport = packet.dst_port
        proto = packet.protocol  # 'TCP' или 'UDP' (строка или int) — проверим в runtime
    except Exception:
        return None

    # Небольшая оптимизация: собираем словарь порт->pid для совпадающих локальных портов
    # psutil.net_connections() даёт список всех сокетов и их pid
    try:
        for conn in psutil.net_connections(kind='inet'):
            # conn.laddr/conn.raddr — кортежи (ip, port) либо пустые
            if not conn.laddr:
                continue
            try:
                conn_lip, conn_lport = conn.laddr
            except Exception:
                continue
            conn_r = getattr(conn, 'raddr', None)
            conn_rip, conn_rport = (None, None)
            if conn_r:
                try:
                    conn_rip, conn_rport = conn_r
                except Exception:
                    pass

            # Сравниваем по локальному порту и удалённому адресу/порту (если есть)
            if conn_lport == lport:
                #Если удалённый порт/адрес совпадают — считаем что это тот
                #Если нет — всё равно иногда сопоставляем по локальному порту
                if (conn_rip is None) or (conn_rip == raddr and conn_rport == rport):
                    return conn.pid
        return None
    except Exception:
        return None

def throttle_worker(pid):
    """
    Поток, выталкивающий пакеты из буфера pid с ограничением скорости.
    """
    bucket = {'tokens': RATE_BYTES_PER_SEC, 'last': time.time()}
    token_buckets[pid] = bucket
    q = buffers[pid]
    while True:
        if pid not in throttled_pids:
            # выключили ограничение — вытащим и отправим всё (в порядке FIFO)
            try:
                while True:
                    raw, meta = q.get_nowait()
                    meta['handle'].send(raw)  # немедленно посылаем
                    q.task_done()
            except queue.Empty:
                pass
            break

        # refill tokens
        now = time.time()
        elapsed = now - bucket['last']
        if elapsed > 0:
            bucket['tokens'] = min(RATE_BYTES_PER_SEC, bucket['tokens'] + elapsed * RATE_BYTES_PER_SEC)
            bucket['last'] = now

        try:
            raw, meta = q.get(timeout=0.1)  # подождём чуть-чуть
        except queue.Empty:
            continue

        length = len(raw)
        if bucket['tokens'] >= length:
            # отправляем
            try:
                meta['handle'].send(raw)
            except Exception:
                pass
            bucket['tokens'] -= length
            q.task_done()
        else:
            # не хватает токенов — вернём пакет обратно и подождём
            q.put((raw, meta))
            time.sleep(max(0.01, (length - bucket['tokens']) / RATE_BYTES_PER_SEC))

    # завершение: удаляем структуры
    with buffers_lock:
        if pid in buffers:
            del buffers[pid]
        if pid in token_buckets:
            del token_buckets[pid]

def ensure_pid_worker(pid):
    with buffers_lock:
        if pid not in buffers:
            buffers[pid] = queue.Queue()
            t = threading.Thread(target=throttle_worker, args=(pid,), daemon=True)
            t.start()

# Клавиша F1 переключает PID ограничение (берём foreground PID)
def on_f1():
    pid = get_foreground_pid()
    if not pid:
        print("Не удалось определить PID foreground-приложения.")
        return
    if pid in throttled_pids:
        throttled_pids.remove(pid)
        print(f"Отключил ограничение для PID {pid}")
    else:
        throttled_pids.add(pid)
        print(f"Включил ограничение (1 KB/s) для PID {pid}")
        ensure_pid_worker(pid)

# При старте — назначаем слушатель клавиши
keyboard.add_hotkey('f1', on_f1)
print("Нажмите F1, чтобы переключить ограничение для foreground-приложения.")

# Основной ловец пакетов
def packet_loop():
    # Используем pydivert. Убедитесь, что установлены pydivert и WinDivert (pydivert включает драйвер).
    # Фильтр можно уточнить: 'outbound and tcp' и т.д.
    try:
        with pydivert.WinDivert(WINDIVERT_FILTER) as w:
            print("WinDivert открыт, перехват пакетов...")
            for pkt in w:
                try:
                    # Преобразуем packet в сырые байты для последующей отправки
                    raw = pkt.raw  # байтовая строка (pydivert.Packet.raw)
                except Exception:
                    # если нет raw — просто отправляем обратно
                    w.send(pkt)
                    continue

                # Попытка быстро получить pid: сначала try meta (если у pydivert есть поле pid)
                pid = None
                try:
                    if hasattr(pkt, 'pid') and pkt.pid:
                        pid = pkt.pid
                except Exception:
                    pid = None

                # Если pid не найден, маппим через psutil
                if pid is None:
                    pid = map_packet_to_pid(pkt)

                if pid is not None and pid in throttled_pids:
                    # Кладём в буфер (сохраняя handle/инфу для отправки)
                    with buffers_lock:
                        ensure_pid_worker(pid)
                        # Сохраним мета: handle — специальный объект для отправки (pydivert handle)
                        meta = {'handle': w}
                        buffers[pid].put((raw, meta))
                    # не отправляем тут
                    continue
                else:
                    # Не ограничиваем — отправим обратно немедленно
                    try:
                        w.send(raw)
                    except Exception:
                        # в некоторых версиях pydivert .send() ожидает packet, но .send(raw) часто работает.
                        try:
                            w.send(pkt)
                        except Exception:
                            pass
            # конец for
    except Exception as e:
        print("Ошибка WinDivert/pydivert:", e)
        print("Убедитесь, что скрипт запущен от администратора и pydivert установлен.")
        raise

# Запускаем loop в основном потоке (или новом)
if __name__ == "__main__":
    loop_thread = threading.Thread(target=packet_loop, daemon=True)
    loop_thread.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Выход.")
