# throttler_logic.py
import time
import threading
import psutil
import pydivert
import win32gui
import win32process
import pygetwindow as gw
import winsound


class ThrottlerLogic:
    def __init__(self):
        self.is_running = False
        self.target_pid = None
        self.throttled_pids = set()
        self.network_thread = None
        self.rate_limit_bytes = 1024 * 10
        self.token_buckets = {}
        self.status_callback = None

    def set_target_pid(self, pid):
        self.target_pid = pid
        print(f"Logic: New target set to PID {pid}")

    def get_running_apps(self):
        apps = {}
        windows = gw.getWindowsWithTitle('')
        for window in windows:
            if window.title and window.visible:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(window._hWnd)
                    if pid not in apps.values():
                        proc_name = psutil.Process(pid).name()
                        display_name = f"{proc_name} - {window.title[:30]}... (PID: {pid})"
                        apps[display_name] = pid
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        return apps

    def start_listener(self):
        if self.is_running: return
        self.is_running = True
        self.network_thread = threading.Thread(target=self._packet_loop, daemon=True)
        self.network_thread.start()
        print("Logic: Packet listener started.")

    def stop_listener(self):
        if not self.is_running: return
        self.is_running = False
        self.throttled_pids.clear()
        if self.network_thread: self.network_thread.join(timeout=1.0)
        print("Logic: Packet listener stopped.")

    def toggle_throttle_for_target(self):
        if not self.target_pid:
            msg = "Target PID not set!"
            print(f"Logic: {msg}")
            winsound.PlaySound("SystemHand", winsound.SND_ASYNC)
            if self.status_callback: self.status_callback(msg, "orange")
            return

        foreground_pid = self._get_foreground_pid()
        if not foreground_pid: return

        try:
            parent_process = psutil.Process(foreground_pid)
            pids_to_check = {p.pid for p in parent_process.children(recursive=True)} | {foreground_pid}

            if self.target_pid in pids_to_check:
                target_group = {p.pid for p in psutil.Process(self.target_pid).children(recursive=True)} | {
                    self.target_pid}

                if self.target_pid in self.throttled_pids:
                    # Выключение
                    self.throttled_pids.clear()
                    winsound.PlaySound("SystemExit", winsound.SND_ASYNC)  # <<< ИЗМЕНЕНО: Звук выключения
                    msg = f"Unthrottled {psutil.Process(self.target_pid).name()}"
                    if self.status_callback: self.status_callback(msg, "cyan")
                else:
                    # Включение
                    self.throttled_pids = target_group
                    winsound.PlaySound("SystemExclamation", winsound.SND_ASYNC)  # <<< ИЗМЕНЕНО: Звук включения
                    msg = f"Throttling {psutil.Process(self.target_pid).name()}"
                    if self.status_callback: self.status_callback(msg, "yellow")
                print(f"Logic: {msg}")

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return

    def _get_foreground_pid(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            return win32process.GetWindowThreadProcessId(hwnd)[1] if hwnd != 0 else None
        except:
            return None

    def _map_packet_to_pid(self, packet):
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr and conn.laddr.port == packet.src_port:
                    if not conn.raddr or (conn.raddr.ip == packet.dst_addr and conn.raddr.port == packet.dst_port):
                        return conn.pid
        except:
            pass
        return None

    def _packet_loop(self):
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
            self.is_running = False

    def set_rate_limit(self, bytes_per_sec):
        self.rate_limit_bytes = bytes_per_sec