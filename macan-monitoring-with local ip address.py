import sys
import psutil
import time
import platform
import os
import socket  # Import socket untuk cek IP
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QProgressBar, QPushButton, QMenu, QFrame)
from PySide6.QtCore import Qt, QThread, Signal, QPoint
from PySide6.QtGui import QAction, QFont

# --- KONFIGURASI NAMA APLIKASI ---
APP_NAME = "Macan Monitoring"

# --- WORKER THREAD UNTUK MONITORING ---
class SystemMonitor(QThread):
    stats_signal = Signal(float, float, float, str, str) # CPU, RAM, Swap, DL, UL

    def run(self):
        last_net = psutil.net_io_counters()
        while True:
            try:
                # CPU, RAM, SWAP
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                swap = psutil.swap_memory().percent

                # NETWORK SPEED CALCULATION
                current_net = psutil.net_io_counters()
                bytes_sent = current_net.bytes_sent - last_net.bytes_sent
                bytes_recv = current_net.bytes_recv - last_net.bytes_recv
                
                last_net = current_net

                upload_speed = self.format_speed(bytes_sent)
                download_speed = self.format_speed(bytes_recv)

                self.stats_signal.emit(cpu, ram, swap, download_speed, upload_speed)
                
                time.sleep(1)
            except Exception as e:
                print(f"Error in monitor thread: {e}")
                break

    def format_speed(self, bytes_sec):
        if bytes_sec < 1024:
            return f"{bytes_sec} B/s"
        elif bytes_sec < 1024 * 1024:
            return f"{bytes_sec / 1024:.1f} KB/s"
        else:
            return f"{bytes_sec / (1024 * 1024):.1f} MB/s"

# --- KOMPONEN UI CUSTOM ---
class StatBar(QWidget):
    def __init__(self, label_text, color_code):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(2)

        self.lbl_name = QLabel(label_text)
        self.lbl_name.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 11px;")
        
        self.lbl_value = QLabel("0%")
        self.lbl_value.setAlignment(Qt.AlignRight)
        self.lbl_value.setStyleSheet("color: #ffffff; font-size: 11px;")

        header_layout = QHBoxLayout()
        header_layout.addWidget(self.lbl_name)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_value)

        self.pbar = QProgressBar()
        self.pbar.setTextVisible(False)
        self.pbar.setFixedHeight(6)
        self.pbar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background-color: #404040;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {color_code};
                border-radius: 3px;
            }}
        """)

        layout.addLayout(header_layout)
        layout.addWidget(self.pbar)
        self.setLayout(layout)

    def update_value(self, value):
        self.pbar.setValue(int(value))
        self.lbl_value.setText(f"{value:.1f}%")

class NetStat(QWidget):
    def __init__(self, label_text, icon_char, color_code):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 5, 0, 5)
        
        self.lbl_icon = QLabel(icon_char) 
        self.lbl_icon.setStyleSheet(f"color: {color_code}; font-size: 14px; font-weight: bold;")
        
        self.lbl_name = QLabel(label_text)
        self.lbl_name.setStyleSheet("color: #e0e0e0; font-size: 11px;")

        self.lbl_value = QLabel("0 KB/s")
        self.lbl_value.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11px;")
        self.lbl_value.setAlignment(Qt.AlignRight)

        layout.addWidget(self.lbl_icon)
        layout.addWidget(self.lbl_name)
        layout.addStretch()
        layout.addWidget(self.lbl_value)
        self.setLayout(layout)

    def update_text(self, text):
        self.lbl_value.setText(text)

# --- MAIN WINDOW ---
class WidgetMonitor(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground) 
        
        self.old_pos = None

        self.setup_ui()
        
        # 4. Start Monitoring Thread
        self.monitor_thread = SystemMonitor()
        self.monitor_thread.stats_signal.connect(self.update_stats)
        
        # [FIX 1] Set daemon True agar thread mati saat aplikasi ditutup
        self.monitor_thread.daemon = True 
        self.monitor_thread.start()

    def setup_ui(self):
        self.container = QFrame()
        self.container.setObjectName("MainFrame")
        self.container.setStyleSheet("""
            QFrame#MainFrame {
                background-color: rgba(20, 20, 20, 180); 
                border: 1px solid #444;
                border-radius: 15px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

        content_layout = QVBoxLayout(self.container)
        content_layout.setContentsMargins(15, 10, 15, 15)
        content_layout.setSpacing(5)

        # --- TITLE BAR ---
        title_bar = QHBoxLayout()
        
        self.lbl_title = QLabel(APP_NAME)
        self.lbl_title.setStyleSheet("color: #ff9800; font-weight: bold; font-family: sans-serif; font-size: 13px;")
        
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedSize(25, 25)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setStyleSheet("""
            QPushButton { color: #aaa; background: transparent; border: none; font-size: 16px; }
            QPushButton:hover { color: #fff; }
        """)
        self.btn_settings.clicked.connect(self.show_settings_menu)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(25, 25)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton { color: #aaa; background: transparent; border: none; font-size: 14px; }
            QPushButton:hover { color: #ff5555; }
        """)
        # [FIX 1] Panggil self.exit_app untuk close bersih
        self.btn_close.clicked.connect(self.exit_app)

        title_bar.addWidget(self.lbl_title)
        title_bar.addStretch()
        title_bar.addWidget(self.btn_settings)
        title_bar.addWidget(self.btn_close)
        
        content_layout.addLayout(title_bar)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #444;")
        content_layout.addWidget(line)

        # --- STATS ---
        self.row_cpu = StatBar("CPU Usage", "#00bcd4") 
        content_layout.addWidget(self.row_cpu)

        self.row_ram = StatBar("RAM Usage", "#8bc34a") 
        content_layout.addWidget(self.row_ram)

        self.row_swap = StatBar("Swap Usage", "#ffc107") 
        content_layout.addWidget(self.row_swap)

        content_layout.addSpacing(10)

        self.row_dl = NetStat("Download", "↓", "#2196f3") 
        content_layout.addWidget(self.row_dl)

        self.row_ul = NetStat("Upload", "↑", "#f44336") 
        content_layout.addWidget(self.row_ul)

        # --- [FITUR BARU] IP ADDRESS SECTION ---
        content_layout.addSpacing(5)
        
        # Garis tipis pemisah untuk IP
        line_ip = QFrame()
        line_ip.setFrameShape(QFrame.HLine)
        line_ip.setStyleSheet("color: #444;")
        content_layout.addWidget(line_ip)

        ip_layout = QHBoxLayout()
        
        lbl_ip_title = QLabel("IP Address")
        lbl_ip_title.setStyleSheet("color: #aaa; font-size: 11px;")
        
        self.lbl_ip_val = QLabel(self.get_local_ip())
        self.lbl_ip_val.setStyleSheet("color: #00ffcc; font-weight: bold; font-size: 11px;")
        self.lbl_ip_val.setAlignment(Qt.AlignRight)

        ip_layout.addWidget(lbl_ip_title)
        ip_layout.addStretch()
        ip_layout.addWidget(self.lbl_ip_val)
        
        content_layout.addLayout(ip_layout)

        content_layout.addStretch()
        # Sedikit tambah tinggi window untuk muat IP
        self.resize(280, 350)

    # --- LOGIC IP ADDRESS ---
    def get_local_ip(self):
        try:
            # Cara paling reliable dapat IP lokal (bukan 127.0.0.1)
            # Kita coba connect dummy ke DNS Google (tidak kirim data beneran)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def update_stats(self, cpu, ram, swap, dl_speed, ul_speed):
        self.row_cpu.update_value(cpu)
        self.row_ram.update_value(ram)
        self.row_swap.update_value(swap)
        self.row_dl.update_text(dl_speed)
        self.row_ul.update_text(ul_speed)

    def exit_app(self):
        # Memastikan aplikasi benar-benar berhenti
        QApplication.quit()

    # --- DRAGGABLE WINDOW LOGIC ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    # --- SETTINGS MENU ---
    def show_settings_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #333; color: white; border: 1px solid #555; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #555; }
        """)

        action_ontop = QAction("Always on Top", self)
        action_ontop.setCheckable(True)
        is_ontop = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        action_ontop.setChecked(is_ontop)
        action_ontop.triggered.connect(self.toggle_always_on_top)
        menu.addAction(action_ontop)

        if platform.system() == "Windows":
            action_startup = QAction("Run on Startup", self)
            action_startup.setCheckable(True)
            action_startup.setChecked(self.check_startup_status())
            action_startup.triggered.connect(self.toggle_startup)
            menu.addAction(action_startup)

        menu.exec(self.btn_settings.mapToGlobal(QPoint(0, self.btn_settings.height())))

    def toggle_always_on_top(self, checked):
        if checked:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()

    def check_startup_status(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                 r"Software\Microsoft\Windows\CurrentVersion\Run", 
                                 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            key.Close()
            return True
        except WindowsError:
            return False

    def toggle_startup(self, checked):
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if checked:
                exe_path = sys.executable 
                if not getattr(sys, 'frozen', False):
                    script_path = os.path.abspath(__file__)
                    exe_path = exe_path.replace("python.exe", "pythonw.exe")
                    cmd = f'"{exe_path}" "{script_path}"'
                else:
                    cmd = f'"{sys.executable}"'
                
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except WindowsError:
                    pass
            key.Close()
        except Exception as e:
            print(f"Error registry: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    window = WidgetMonitor()
    window.show()
    sys.exit(app.exec())