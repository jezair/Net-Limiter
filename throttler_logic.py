import time
import threading
import psutil
import pydivert
import win32gui
import win32process

class ThrottlerLogic:
    def __init__(self):
        # --- Состояние ---
        self.is_running = False
        self.network_thread = None
        self.rate_limit_bytes = 1024 * 10  # 10 KB/s по умолчанию
        self.throttled_pids = set()
        self.token_buckets = {}
        self.status_callback = None # Функция для отправки сообщений в UI

    def set_rate_limit(self, bytes_per_sec):
        """Метод для UI, чтобы установить новую скорость."""
        self.rate_limit_bytes = bytes_per_sec
        print(f"Logic: Rate limit set to {bytes_per_sec} B/s")

    def start(self):
        """Запускает основной цикл перехвата пакетов в отдельном потоке."""
        if self.is_running:
            return
        self.is_running = True
        self.network_thread = threading.Thread(target=self._packet_loop, daemon=True)
        self.network_thread.start()
        print("Logic: Started packet loop.")

    def stop(self):
        """Останавливает цикл перехвата пакетов."""
        if not self.is_running:
            return
        self.is_running = False
        if self.network_thread:
            self.network_thread.join(timeout=1.0)
        print("Logic: Stopped packet loop.")

    def _get_foreground_pid(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            return win32process.GetWindowThreadProcessId(hwnd)[1] if hwnd != 0 else None
        except: return None

    def _map_packet_to_pid(self, packet):
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr and conn.laddr.port == packet.src_port:
                    if not conn.raddr or (conn.raddr.ip == packet.dst_addr and conn.raddr.port == packet.dst_port):
                        return conn.pid
        except: pass
        return None
    
    def toggle_pids(self):
        """Основная функция для горячей клавиши. Переключает ограничение для активного окна."""
        parent_pid = self._get_foreground_pid()
        if not parent_pid: return

        try:
            pids_to_toggle = [p.pid for p in psutil.Process(parent_pid).children(recursive=True)] + [parent_pid]
        except psutil.NoSuchProcess:
            pids_to_toggle = [parent_pid]

        if parent_pid in self.throttled_pids:
            for pid in pids_to_toggle: self.throttled_pids.discard(pid)
            message = f"Unthrottled PID {parent_pid}"
            if self.status_callback: self.status_callback(message, "cyan")
        else:
            for pid in pids_to_toggle: self.throttled_pids.add(pid)
            message = f"Throttling PID {parent_pid}"
            if self.status_callback: self.status_callback(message, "yellow")
        
        print(f"Logic: {message}")

    def _packet_loop(self):
        """Основной цикл, который работает в фоновом потоке."""
        try:
            with pydivert.WinDivert("outbound and ip") as w:
                for pkt in w:
                    if not self.is_running: break

                    pid = self._map_packet_to_pid(pkt)
                    if pid and pid in self.throttled_pids:
                        if pid not in self.token_buckets:
                            self.token_buckets[pid] = {'tokens': self.rate_limit_bytes, 'last': time.time()}
                        
                        bucket = self.token_buckets[pid]
                        packet_len = len(pkt.raw)
                        
                        now = time.time()
                        bucket['tokens'] += (now - bucket['last']) * self.rate_limit_bytes
                        bucket['tokens'] = min(self.rate_limit_bytes, bucket['tokens'])
                        bucket['last'] = now

                        if bucket['tokens'] < packet_len:
                            wait_time = (packet_len - bucket['tokens']) / self.rate_limit_bytes
                            time.sleep(wait_time)
                            bucket['tokens'] += wait_time * self.rate_limit_bytes
                        
                        bucket['tokens'] -= packet_len
                    w.send(pkt)
        except Exception as e:
            error_message = f"WinDivert Error: {e}"
            print(error_message)
            if self.status_callback:
                self.status_callback(error_message, "red")
            self.is_running = False # Авто-остановка при ошибке