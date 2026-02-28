import sys
import psutil
import time
import platform
import os
import socket
import urllib.request
import ctypes
from PySide6.QtGui import QDrag, QPixmap, QPainter
from PySide6.QtCore import QMimeData

from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QProgressBar, QPushButton, QMenu, QFrame, 
                               QSizeGrip, QMessageBox, QFileIconProvider, 
                               QGraphicsDropShadowEffect)
from PySide6.QtCore import (Qt, QThread, Signal, QPoint, QSettings, QSize, QUrl, 
                            QFileInfo, QEasingCurve, QVariantAnimation)
from PySide6.QtGui import (QAction, QFont, QDesktopServices, QDragEnterEvent, 
                           QDropEvent, QColor)

# --- IMPORT THEME MANAGER ---
try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False
    print("Warning: macan_theme.py not found. Using default dark theme.")

# --- IMPORT MODULES MODULAR (OPTIONAL) ---
try:
    from macan_clock import MacanClock
    from macan_dock import MacanDock
    from macan_analog import MacanAnalog
    from macan_memo import MacanMemo
    from macan_task import MacanTask
    from macan_network import MacanNetwork
    from macan_disk import MacanDisk
    from macan_url import MacanURL
    import macan_about_update
    
except ImportError as e:
    MacanClock = None
    MacanDock = None
    MacanAnalog = None
    MacanMemo = None
    MacanTask = None
    MacanNetwork = None
    MacanDisk = None
    MacanURL = None
    macan_about_update = None

APP_NAME = "Macan Monitoring"
ORG_NAME = "MacanAngkasa"
EXE_FILENAME = "macan-monitoring.exe"
APP_VERSION = "7.5.0"

# ==========================================

# ==========================================
# BAGIAN: SIDEBAR (INTEGRATED) - WITH DRAG REORDER
# ==========================================

class SidebarIcon(QPushButton):
    def __init__(self, app_path, theme_manager=None, parent=None):
        super().__init__(parent)
        self.app_path = app_path
        self.theme = theme_manager
        
        self.default_size = 45
        self.hover_size = 75
        self.click_size = 40
        
        self.setFixedSize(self.default_size, self.default_size)
        self.setIconSize(QSize(32, 32))
        self.setCursor(Qt.PointingHandCursor)
        
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setOffset(2, 0)
        self.setGraphicsEffect(self.shadow)

        self.apply_theme_style()

        file_info = QFileInfo(app_path)
        icon_provider = QFileIconProvider()
        self.base_icon = icon_provider.icon(file_info)
        self.setIcon(self.base_icon)
        self.setToolTip(file_info.fileName())
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(200) 
        self.anim.setEasingCurve(QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self.update_geometry_anim)
        
        # === DRAG SUPPORT ===
        self.drag_start_pos = None
        self.is_dragging = False

    def apply_theme_style(self):
        hover_bg = "rgba(255, 255, 255, 30)"
        if self.theme and self.theme.get_theme() == "light":
            hover_bg = "rgba(0, 0, 0, 20)"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
        """)

    def update_geometry_anim(self, value):
        size = int(value)
        self.setFixedSize(size, size)
        icon_new_size = size - 12
        if icon_new_size > 0:
            self.setIconSize(QSize(icon_new_size, icon_new_size))

    def enterEvent(self, event):
        if not self.is_dragging:
            self.anim.stop()
            self.anim.setStartValue(self.width())
            self.anim.setEndValue(self.hover_size)
            self.anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.is_dragging:
            self.anim.stop()
            self.anim.setStartValue(self.width())
            self.anim.setEndValue(self.default_size)
            self.anim.start()
        super().leaveEvent(event)

    # === DRAG EVENTS ===
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # FIX: Gunakan position().toPoint()
            self.drag_start_pos = event.position().toPoint() 
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if self.drag_start_pos is None:
            return
        
        # FIX: Gunakan position().toPoint()
        current_pos = event.position().toPoint()
        if (current_pos - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
            
        self.is_dragging = True
        event.accept()
        self.perform_drag()

    def mouseReleaseEvent(self, event):
        was_dragging = self.is_dragging
        self.drag_start_pos = None
        self.is_dragging = False
        
        if not was_dragging:
            super().mouseReleaseEvent(event)
        else:
            event.accept()

    def perform_drag(self):
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(f"REORDER:{self.app_path}")
        drag.setMimeData(mime_data)
        
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.render(painter, QPoint(0, 0))
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(self.rect().center())
        
        self.anim.stop()
        self.setFixedSize(self.default_size, self.default_size)
        
        drag.exec(Qt.MoveAction)

class MacanSidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MacanAngkasa", "MacanSidebar")
        self.app_list = [] 
        self.theme = get_theme_manager() if THEME_AVAILABLE else None

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_AlwaysShowToolTips, True)
        self.setAcceptDrops(True) 

        self.old_pos = None
        self.drag_over_index = -1
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        self.container = QFrame(self)
        self.container.setObjectName("SidebarContainer")
        
        self.layout_icons = QVBoxLayout(self.container)
        self.layout_icons.setContentsMargins(3, 12, 3, 12) 
        self.layout_icons.setSpacing(8)
        self.layout_icons.setAlignment(Qt.AlignLeft) 

        self.apply_theme()
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) 
        main_layout.addWidget(self.container)
        main_layout.setAlignment(Qt.AlignLeft)

        self.refresh_sidebar_icons()

    def apply_theme(self):
        if self.theme:
            self.container.setStyleSheet(self.theme.get_container_style())
            
            if hasattr(self, 'layout_icons') and self.layout_icons is not None:
                for i in range(self.layout_icons.count()):
                    item = self.layout_icons.itemAt(i)
                    if item and item.widget():
                        w = item.widget()
                        if isinstance(w, SidebarIcon):
                            w.apply_theme_style()
        else:
            self.container.setStyleSheet("""
                QFrame#SidebarContainer {
                    background-color: rgba(20, 20, 20, 200);
                    border: 1px solid rgba(255, 255, 255, 20);
                    border-radius: 20px;
                }
            """)

    def refresh_sidebar_icons(self):
        while self.layout_icons.count():
            item = self.layout_icons.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()

        if not self.app_list:
            lbl = QPushButton("Drop\nApps")
            txt_col = "#555" if self.theme and self.theme.get_theme() == "light" else "#888"
            lbl.setStyleSheet(f"color: {txt_col}; border: none; font-style: italic; margin: 5px;")
            lbl.setEnabled(False)
            lbl.setFixedSize(45, 60)
            self.layout_icons.addWidget(lbl)
        
        for app_path in self.app_list:
            btn = SidebarIcon(app_path, theme_manager=self.theme)
            btn.clicked.connect(lambda _, x=app_path: self.launch_app(x))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, b=btn, x=app_path: self.show_context_menu(pos, b, x))
            self.layout_icons.addWidget(btn)
        
        self.container.adjustSize()
        self.adjustSize()

    def launch_app(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def show_context_menu(self, pos, target_btn, app_path):
        menu = QMenu(self)
        if self.theme:
            menu.setStyleSheet(self.theme.get_menu_style())
        else:
            menu.setStyleSheet("QMenu { background: #333; color: #fff; border: 1px solid #555; }")
        
        action_remove = QAction("Remove", self)
        action_remove.triggered.connect(lambda: self.remove_app(app_path))
        menu.addAction(action_remove)
        
        menu.exec(target_btn.mapToGlobal(pos))

    def remove_app(self, path):
        if path in self.app_list:
            self.app_list.remove(path)
            self.save_settings()
            self.refresh_sidebar_icons()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        elif event.mimeData().hasText() and event.mimeData().text().startswith("REORDER:"):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        elif event.mimeData().hasText() and event.mimeData().text().startswith("REORDER:"):
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        mime_data = event.mimeData()
        
        if mime_data.hasText() and mime_data.text().startswith("REORDER:"):
            app_path = mime_data.text().replace("REORDER:", "")
            self.reorder_app(app_path, event.position().toPoint())
            event.accept()
            return
        
        if mime_data.hasUrls():
            files = [u.toLocalFile() for u in mime_data.urls()]
            for f in files:
                if os.path.exists(f) and f not in self.app_list:
                    self.app_list.append(f)
            self.save_settings()
            self.refresh_sidebar_icons()
            event.accept()

    def reorder_app(self, app_path, drop_pos):
        if app_path not in self.app_list:
            return
        
        old_index = self.app_list.index(app_path)
        self.app_list.pop(old_index)
        
        new_index = self.get_drop_index(drop_pos)
        
        self.app_list.insert(new_index, app_path)
        
        self.save_settings()
        self.refresh_sidebar_icons()

    def get_drop_index(self, pos):
        for i in range(len(self.app_list)):
            widget = self.layout_icons.itemAt(i).widget()
            if widget and isinstance(widget, SidebarIcon):
                widget_center = widget.geometry().center()
                if pos.y() < widget_center.y():
                    return i
        
        return len(self.app_list)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # FIX: Gunakan position().toPoint()
            click_pos = event.position().toPoint()
            if self.childAt(click_pos) == self.container or self.childAt(click_pos) == self:
                self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        self.save_settings()

    def load_settings(self):
        pos = self.settings.value("pos", QPoint(10, 200))
        self.move(pos)
        self.app_list = self.settings.value("apps", [])
        if not isinstance(self.app_list, list): self.app_list = []
        self.refresh_sidebar_icons()

    def save_settings(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("apps", self.app_list)

# ==========================================
# BAGIAN: SYSTEM MONITORING UTAMA
# ==========================================

class SystemMonitor(QThread):
    stats_signal = Signal(float, float, float, float, float, int, bool, bool) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True  # Flag untuk mengontrol loop

    def run(self):
        last_net = psutil.net_io_counters()
        # FIX: Ubah while True menjadi while self.running
        while self.running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                swap = psutil.swap_memory().percent

                current_net = psutil.net_io_counters()
                bytes_sent = current_net.bytes_sent - last_net.bytes_sent
                bytes_recv = current_net.bytes_recv - last_net.bytes_recv
                last_net = current_net
                
                batt = psutil.sensors_battery()
                batt_percent = 0
                batt_plugged = False
                show_widget = True 
                
                if batt:
                    batt_percent = int(batt.percent)
                    batt_plugged = batt.power_plugged
                else:
                    batt_percent = -1 
                    batt_plugged = True 

                self.stats_signal.emit(cpu, ram, swap, float(bytes_recv), float(bytes_sent),
                                       batt_percent, batt_plugged, show_widget)
                
                # FIX: Gunakan sleep yang bisa diinterupsi atau cek running setelah sleep
                for _ in range(10): # Sleep 1 detik (10 x 0.1s) agar responsif saat stop
                    if not self.running: break
                    time.sleep(0.1)

            except Exception as e:
                print(f"Monitor error: {e}")
                break
    
    def stop(self):
        """Method untuk menghentikan thread secara aman"""
        self.running = False
        self.wait(3000)

class NetworkInfoWorker(QThread):
    info_signal = Signal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def run(self):
        public_ip = "Offline"
        local_ip = "127.0.0.1"
        conn_type = "Unknown"

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(3)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            conn_type = self.get_connection_type(local_ip)
        except Exception:
            local_ip = "127.0.0.1"
            conn_type = "No Network"

        # Guard: cek sebelum HTTP request yg bisa block lama
        if not self._running:
            return

        try:
            url = "https://api.ipify.org"
            with urllib.request.urlopen(url, timeout=4) as response:
                public_ip = response.read().decode('utf-8')
        except Exception:
            public_ip = "N/A"

        # Guard: jangan emit jika widget sudah di-destroy
        if self._running:
            self.info_signal.emit(public_ip, local_ip, conn_type)

    def stop(self):
        self._running = False
        self.wait(5000)

    def get_connection_type(self, target_ip):
        try:
            for interface_name, snics in psutil.net_if_addrs().items():
                for snic in snics:
                    if snic.family == socket.AF_INET and snic.address == target_ip:
                        name_lower = interface_name.lower()
                        if "wi-fi" in name_lower or "wireless" in name_lower or "wlan" in name_lower:
                            return "Wi-Fi"
                        elif "ethernet" in name_lower or "eth" in name_lower or "lan" in name_lower:
                            return "Ethernet"
                        else:
                            return interface_name 
        except Exception:
            pass
        return "Unknown"

class StatBar(QWidget):
    def __init__(self, label_text, color_code, theme=None):
        super().__init__()
        self.theme = theme
        self.color_code = color_code
        self.last_value = 0
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)

        header_layout = QHBoxLayout()
        self.lbl_name = QLabel(label_text)
        self.lbl_value = QLabel("0%")
        self.lbl_value.setAlignment(Qt.AlignRight)
        
        self.pbar = QProgressBar()
        self.pbar.setTextVisible(False)
        self.pbar.setFixedHeight(6)

        self.apply_theme()
        self.update_progressbar_style()

        header_layout.addWidget(self.lbl_name)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_value)

        layout.addLayout(header_layout)
        layout.addWidget(self.pbar)
        self.setLayout(layout)

    def apply_theme(self):
        if self.theme:
            c = self.theme.get_colors()
            self.lbl_name.setStyleSheet(f"color: {c['text_secondary']}; font-weight: bold; font-size: 11px;")
            self.lbl_value.setStyleSheet(f"color: {c['text_primary']}; font-size: 11px;")
        else:
            self.lbl_name.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 11px;")
            self.lbl_value.setStyleSheet("color: #ffffff; font-size: 11px;")

    def update_progressbar_style(self):
        if self.theme:
            c = self.theme.get_colors()
            self.pbar.setStyleSheet(f"""
                QProgressBar {{ border: none; background-color: {c['progress_bg']}; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {self.color_code}; border-radius: 3px; }}
            """)
        else:
            self.pbar.setStyleSheet(f"""
                QProgressBar {{ border: none; background-color: #404040; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {self.color_code}; border-radius: 3px; }}
            """)

    def update_value(self, value):
        self.last_value = value
        self.pbar.setValue(int(value))
        self.lbl_value.setText(f"{value:.1f}%")

class NetStat(QWidget):
    def __init__(self, label_text, icon_char, color_code, theme=None):
        super().__init__()
        self.theme = theme
        self.color_code = color_code
        self.last_speed = 0
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(2)
        
        header_layout = QHBoxLayout()
        self.lbl_icon = QLabel(icon_char) 
        self.lbl_name = QLabel(label_text)
        self.lbl_value = QLabel("0 B/s")
        self.lbl_value.setAlignment(Qt.AlignRight)
        
        self.pbar = QProgressBar()
        self.pbar.setTextVisible(False)
        self.pbar.setFixedHeight(4)
        self.pbar.setRange(0, 100)
        
        self.apply_theme()
        self.update_progressbar_style()

        header_layout.addWidget(self.lbl_icon)
        header_layout.addWidget(self.lbl_name)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_value)

        layout.addLayout(header_layout)
        layout.addWidget(self.pbar)
        self.setLayout(layout)

    def apply_theme(self):
        if self.theme:
            c = self.theme.get_colors()
            self.lbl_icon.setStyleSheet(f"color: {self.color_code}; font-size: 14px; font-weight: bold;")
            self.lbl_name.setStyleSheet(f"color: {c['text_secondary']}; font-size: 11px;")
            self.lbl_value.setStyleSheet(f"color: {c['text_primary']}; font-weight: bold; font-size: 11px;")
        else:
            self.lbl_icon.setStyleSheet(f"color: {self.color_code}; font-size: 14px; font-weight: bold;")
            self.lbl_name.setStyleSheet("color: #e0e0e0; font-size: 11px;")
            self.lbl_value.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 11px;")

    def update_progressbar_style(self):
        if self.theme:
            c = self.theme.get_colors()
            self.pbar.setStyleSheet(f"""
                QProgressBar {{ border: none; background-color: {c['progress_bg']}; border-radius: 2px; }}
                QProgressBar::chunk {{ background-color: {self.color_code}; border-radius: 2px; }}
            """)
        else:
            self.pbar.setStyleSheet(f"""
                QProgressBar {{ border: none; background-color: #404040; border-radius: 2px; }}
                QProgressBar::chunk {{ background-color: {self.color_code}; border-radius: 2px; }}
            """)

    def update_speed(self, bytes_sec):
        self.last_speed = bytes_sec
        text = self.format_speed(bytes_sec)
        self.lbl_value.setText(text)
        max_visual = 10 * 1024 * 1024
        percentage = (bytes_sec / max_visual) * 100
        if percentage > 100: percentage = 100
        self.pbar.setValue(int(percentage))

    def format_speed(self, bytes_sec):
        if bytes_sec < 1024: return f"{bytes_sec:.0f} B/s"
        elif bytes_sec < 1024 * 1024: return f"{bytes_sec / 1024:.1f} KB/s"
        else: return f"{bytes_sec / (1024 * 1024):.1f} MB/s"

class WidgetMonitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground) 


        # Initialize Theme Manager
        self.theme = get_theme_manager() if THEME_AVAILABLE else None
        
        # Modules State placeholders
        self.task_window = None

        # Load Modules
        self.clock_widget = MacanClock() if MacanClock else None
        self.dock_widget = MacanDock() if MacanDock else None
        self.analog_widget = MacanAnalog() if MacanAnalog else None
        self.memo_widget = MacanMemo() if MacanMemo else None
        self.network_widget = MacanNetwork() if MacanNetwork else None
        self.disk_widget = MacanDisk() if MacanDisk else None
        self.url_widget = MacanURL() if MacanURL else None
        self.sidebar_widget = MacanSidebar()
        
        self.old_pos = None
        self.settings = QSettings(ORG_NAME, APP_NAME)

        self.setup_ui()
        self.load_settings()
        self.load_module_states() 
        
        self._is_closing = False

        self.monitor_thread = SystemMonitor(self)
        self.monitor_thread.stats_signal.connect(self.update_stats)
        self.monitor_thread.start()

        self.net_info_thread = NetworkInfoWorker(self)
        self.net_info_thread.info_signal.connect(self.update_network_info)
        self.refresh_network_info()

    def setup_ui(self):
        self.container = QFrame()
        self.container.setObjectName("MainFrame")
        self.apply_theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

        content_layout = QVBoxLayout(self.container)
        content_layout.setContentsMargins(15, 10, 15, 15)
        content_layout.setSpacing(5)

        # Title Bar
        title_bar = QHBoxLayout()
        self.lbl_title = QLabel(APP_NAME)
        
        if self.theme:
            c = self.theme.get_colors()
            self.lbl_title.setStyleSheet(f"color: {c['accent_orange']}; font-weight: bold; font-size: 13px;")
        else:
            self.lbl_title.setStyleSheet("color: #ff9800; font-weight: bold; font-size: 13px;")
        
        # Theme Toggle Button
        self.btn_theme = QPushButton("🌓")
        self.btn_theme.setFixedSize(25, 25)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setToolTip("Toggle Light/Dark Theme")
        self.btn_theme.clicked.connect(self.toggle_theme)
        
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedSize(25, 25)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self.show_settings_menu)

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(25, 25)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.exit_app)

        self.apply_button_styles()

        title_bar.addWidget(self.lbl_title)
        title_bar.addStretch()
        title_bar.addWidget(self.btn_theme)
        title_bar.addWidget(self.btn_settings)
        title_bar.addWidget(self.btn_close)
        content_layout.addLayout(title_bar)
        
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.apply_separator_style(self.line)
        content_layout.addWidget(self.line)

        # Stats Rows
        if self.theme:
            c = self.theme.get_colors()
            self.row_cpu = StatBar("CPU", c['cpu_color'], self.theme) 
            self.row_ram = StatBar("RAM", c['ram_color'], self.theme) 
            self.row_swap = StatBar("Swap", c['swap_color'], self.theme) 
            self.row_dl = NetStat("Download", "↓", c['download_color'], self.theme) 
            self.row_ul = NetStat("Upload", "↑", c['upload_color'], self.theme) 
        else:
            self.row_cpu = StatBar("CPU", "#00bcd4") 
            self.row_ram = StatBar("RAM", "#8bc34a") 
            self.row_swap = StatBar("Swap", "#ffc107")
            self.row_dl = NetStat("Download", "↓", "#2196f3") 
            self.row_ul = NetStat("Upload", "↑", "#ff9800")
            
        content_layout.addWidget(self.row_cpu)
        content_layout.addWidget(self.row_ram)
        content_layout.addWidget(self.row_swap)
        content_layout.addSpacing(5)
        content_layout.addWidget(self.row_dl)
        content_layout.addWidget(self.row_ul)

        # Connection & Battery
        content_layout.addSpacing(8)
        self.line_ip = QFrame()
        self.line_ip.setFrameShape(QFrame.HLine)
        self.apply_separator_style(self.line_ip)
        content_layout.addWidget(self.line_ip)

        info_row_layout = QHBoxLayout()
        
        self.lbl_conn_icon = QLabel("🔌") 
        self.lbl_conn_icon.setStyleSheet("font-size: 14px;")
        self.lbl_conn_text = QLabel("Checking...")
        
        self.lbl_batt_icon = QLabel("🔋")
        self.lbl_batt_icon.setStyleSheet("font-size: 14px; margin-left: 10px;")
        self.lbl_batt_text = QLabel("--%")
        
        self.apply_info_text_styles()
        
        info_row_layout.addWidget(self.lbl_conn_icon)
        info_row_layout.addWidget(self.lbl_conn_text)
        info_row_layout.addStretch()
        info_row_layout.addWidget(self.lbl_batt_icon)
        info_row_layout.addWidget(self.lbl_batt_text)
        
        content_layout.addLayout(info_row_layout)

        # IP Address
        self.lbl_local_ip = QLabel("Local IP: ...")
        self.lbl_public_ip = QLabel("...")
        
        self.apply_ip_text_styles()

        content_layout.addWidget(self.lbl_local_ip)

        ip_layout = QHBoxLayout()
        self.lbl_pub_title = QLabel("Public IP:")
        self.apply_ip_title_style(self.lbl_pub_title)
        self.lbl_public_ip.setAlignment(Qt.AlignRight)

        ip_layout.addWidget(self.lbl_pub_title)
        ip_layout.addStretch()
        ip_layout.addWidget(self.lbl_public_ip)
        content_layout.addLayout(ip_layout)

        content_layout.addStretch()

        # Grip
        grip_layout = QHBoxLayout()
        grip_layout.addStretch()
        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setStyleSheet("background: transparent; width: 15px; height: 15px;")
        grip_layout.addWidget(self.sizegrip, 0, Qt.AlignBottom | Qt.AlignRight)
        self.sizegrip.setParent(self.container)

    def apply_theme(self):
        """Apply current theme to main window"""
        if self.theme:
            self.container.setStyleSheet(self.theme.get_main_window_style())
        else:
            self.container.setStyleSheet("""
                QFrame#MainFrame {
                    background-color: rgba(20, 20, 20, 220); 
                    border: 1px solid #555;
                    border-radius: 12px;
                }
            """)

    def apply_button_styles(self):
        """Apply theme to buttons"""
        if self.theme:
            c = self.theme.get_colors()
            base_style = f"QPushButton {{ color: {c['text_muted']}; background: transparent; border: none; font-size: 16px; }} QPushButton:hover {{ color: {c['text_primary']}; }}"
            self.btn_theme.setStyleSheet(base_style)
            self.btn_settings.setStyleSheet(base_style)
            self.btn_close.setStyleSheet(f"QPushButton {{ color: {c['text_muted']}; background: transparent; border: none; font-size: 14px; }} QPushButton:hover {{ color: {c['accent_red']}; }}")
        else:
            self.btn_theme.setStyleSheet("QPushButton { color: #aaa; background: transparent; border: none; font-size: 16px; } QPushButton:hover { color: #fff; }")
            self.btn_settings.setStyleSheet("QPushButton { color: #aaa; background: transparent; border: none; font-size: 16px; } QPushButton:hover { color: #fff; }")
            self.btn_close.setStyleSheet("QPushButton { color: #aaa; background: transparent; border: none; font-size: 14px; } QPushButton:hover { color: #ff5555; }")

    def apply_separator_style(self, line):
        if self.theme:
            c = self.theme.get_colors()
            line.setStyleSheet(f"color: {c['separator_color']}; background-color: {c['separator_color']}; border: none; height: 1px;")
        else:
            line.setStyleSheet("color: #444; background-color: #444; border: none; height: 1px;")

    def apply_info_text_styles(self):
        if self.theme:
            c = self.theme.get_colors()
            self.lbl_conn_text.setStyleSheet(f"color: {c['text_dark']}; font-weight: bold; font-size: 11px;")
            self.lbl_batt_text.setStyleSheet(f"color: {c['text_dark']}; font-size: 11px;")
        else:
            self.lbl_conn_text.setStyleSheet("color: #ddd; font-weight: bold; font-size: 11px;")
            self.lbl_batt_text.setStyleSheet("color: #ddd; font-size: 11px;")

    def apply_ip_text_styles(self):
        if self.theme:
            c = self.theme.get_colors()
            self.lbl_local_ip.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
            self.lbl_public_ip.setStyleSheet(f"color: {c['accent_cyan']}; font-weight: bold; font-size: 11px;")
        else:
            self.lbl_local_ip.setStyleSheet("color: #aaa; font-size: 11px;")
            self.lbl_public_ip.setStyleSheet("color: #00ffcc; font-weight: bold; font-size: 11px;")

    def apply_ip_title_style(self, label):
        if self.theme:
            c = self.theme.get_colors()
            label.setStyleSheet(f"color: {c['text_muted']}; font-size: 11px;")
        else:
            label.setStyleSheet("color: #aaa; font-size: 11px;")

    # --- THEME DYNAMIC SWITCHING (UPDATED LOGIC) ---
    def toggle_theme(self):
        """Switch between dark and light themes and propagate to all modules"""
        if self.theme:
            self.theme.toggle_theme()
            self.refresh_ui_theme() 
            self.propagate_theme_update()

    def refresh_ui_theme(self):
        """Re-apply styles to main window components immediately"""
        self.apply_theme()
        
        if self.theme:
            c = self.theme.get_colors()
            self.lbl_title.setStyleSheet(f"color: {c['accent_orange']}; font-weight: bold; font-size: 13px;")
            self.apply_button_styles()
            self.apply_separator_style(self.line)
            self.apply_separator_style(self.line_ip)
            self.apply_info_text_styles()
            self.apply_ip_text_styles()
            self.apply_ip_title_style(self.lbl_pub_title)

            # Update Internal Stats Widgets
            for w in [self.row_cpu, self.row_ram, self.row_swap, self.row_dl, self.row_ul]:
                w.apply_theme()
                w.update_progressbar_style()

    def propagate_theme_update(self):
        """Force update all external modules to apply new theme"""
        modules = [
            self.clock_widget, 
            self.dock_widget, 
            self.sidebar_widget,
            self.memo_widget,
            self.network_widget,
            self.disk_widget,
            self.url_widget,
            self.task_window
        ]

        for mod in modules:
            if mod is not None:
                # 1. Standard Apply Theme
                if hasattr(mod, 'apply_theme'):
                    mod.apply_theme()
                
                # 2. Specific Module Refresh Logic
                if mod == self.dock_widget:
                    if hasattr(mod, 'refresh_dock_icons'):
                        mod.refresh_dock_icons() # Recreates icons with new hover style
                
                elif mod == self.sidebar_widget:
                    if hasattr(mod, 'refresh_sidebar_icons'):
                        mod.refresh_sidebar_icons() # Recreates icons with new hover style

                elif mod == self.disk_widget:
                    # Update internal disk bars if they exist in dictionary
                    if hasattr(mod, 'disk_widgets'):
                        for key, disk_bar in mod.disk_widgets.items():
                            if hasattr(disk_bar, 'apply_theme'): disk_bar.apply_theme()
                            if hasattr(disk_bar, 'update_progressbar_style'): disk_bar.update_progressbar_style(disk_bar.pbar.value())
                    # Update header
                    if hasattr(mod, 'apply_header_styles'): mod.apply_header_styles()

                elif mod == self.network_widget:
                    if hasattr(mod, 'apply_header_styles'): mod.apply_header_styles()
                    if hasattr(mod, 'row_dl'): 
                        mod.row_dl.apply_theme()
                        mod.row_dl.update_progressbar_style()
                    if hasattr(mod, 'row_ul'): 
                        mod.row_ul.apply_theme()
                        mod.row_ul.update_progressbar_style()

                elif mod == self.task_window:
                    # Force repaint of table
                    if hasattr(mod, 'table'):
                        mod.table.viewport().update()

        # 3. Handle Analog Clock (PaintEvent based)
        if self.analog_widget is not None:
            self.analog_widget.update() # Triggers paintEvent

    # --- SLOTS & UPDATES ---
    def update_stats(self, cpu, ram, swap, dl, ul, batt_pct, batt_plugged, show_widget):
        self.row_cpu.update_value(cpu)
        self.row_ram.update_value(ram)
        self.row_swap.update_value(swap)
        self.row_dl.update_speed(dl)
        self.row_ul.update_speed(ul)
        
        if show_widget:
            c = self.theme.get_colors() if self.theme else {
                'accent_green': '#00ff00', 'accent_orange': '#ff9800', 'accent_red': '#ff5555', 'accent_cyan': '#00ffcc'
            }
            
            # Use theme keys if available, else fallback
            col_chg = c.get('accent_green', '#00ff00')
            col_norm = c.get('accent_orange', '#ff9800')
            col_low = c.get('accent_red', '#ff5555')
            col_ac = c.get('accent_cyan', '#00ffcc')

            color = col_chg if batt_plugged else col_norm
            
            if batt_pct == -1:
                self.lbl_batt_text.setText("AC Power")
                icon = "⚡"
                color = col_ac
            else:
                status_str = "Chg" if batt_plugged else "Bat"
                if not batt_plugged and batt_pct < 20: 
                    color = col_low
                
                self.lbl_batt_text.setText(f"{batt_pct}% ({status_str})")
                
                if batt_plugged: icon = "⚡"
                elif batt_pct > 80: icon = "🔋"
                elif batt_pct > 30: icon = "🪫"
                else: icon = "⚠️"

            self.lbl_batt_icon.setText(icon)
            self.lbl_batt_icon.setStyleSheet(f"font-size: 14px; margin-left: 10px; color: {color};")
        else:
            self.lbl_batt_text.setText("")
            self.lbl_batt_icon.setText("")

    def refresh_network_info(self):
        self.lbl_public_ip.setText("...")
        self.lbl_local_ip.setText("Local IP: ...")
        self.lbl_conn_text.setText("Checking...")
        if not self.net_info_thread.isRunning():
            self.net_info_thread.start()

    def update_network_info(self, public_ip, local_ip, conn_type):
        self.lbl_public_ip.setText(public_ip)
        self.lbl_local_ip.setText(f"Local IP: {local_ip}")
        self.lbl_conn_text.setText(conn_type)
        if "Wi-Fi" in conn_type:
            self.lbl_conn_icon.setText("📶")
        elif "Ethernet" in conn_type:
            self.lbl_conn_icon.setText("🔌")
        else:
            self.lbl_conn_icon.setText("❓")

    # --- MENU & ACTIONS ---
    def show_settings_menu(self):
        menu = QMenu(self)
        if self.theme:
            menu.setStyleSheet(self.theme.get_menu_style())
        else:
            menu.setStyleSheet("""
                QMenu { background-color: #333; color: white; border: 1px solid #555; }
                QMenu::item { padding: 5px 25px 5px 20px; }
                QMenu::item:selected { background-color: #555; }
            """)

        action_ontop = QAction("Always on Top", self)
        action_ontop.setCheckable(True)
        action_ontop.setChecked(bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        action_ontop.triggered.connect(self.toggle_always_on_top)
        menu.addAction(action_ontop)

        menu.addSeparator()
        
        for name, widget, method in [
            ("Digital Clock", self.clock_widget, self.toggle_clock),
            ("Analog Clock", self.analog_widget, self.toggle_analog),
            ("App Dock", self.dock_widget, self.toggle_dock),
            ("Sidebar Launcher", self.sidebar_widget, self.toggle_sidebar),
            ("Memo / Sticky", self.memo_widget, self.toggle_memo),
            ("Ext Network", self.network_widget, self.toggle_network),
            ("Disk Info", self.disk_widget, self.toggle_disk),
            ("URL / Search Bar", self.url_widget, self.toggle_url)
        ]:
            if widget:
                act = QAction(f"Show {name}", self)
                act.setCheckable(True)
                act.setChecked(widget.isVisible())
                act.triggered.connect(method)
                menu.addAction(act)

        menu.addSeparator()

        action_task = QAction("Open Macan Task Manager", self)
        action_task.triggered.connect(self.open_task_manager)
        menu.addAction(action_task)

        action_rb = QAction("Open Recycle Bin", self)
        action_rb.triggered.connect(self.open_recycle_bin)
        menu.addAction(action_rb)

        action_conq = QAction("Open Macan Conquer", self)
        action_conq.triggered.connect(self.open_macan_conquer)
        menu.addAction(action_conq)

        action_refresh = QAction("Refresh Network Info", self)
        action_refresh.triggered.connect(self.refresh_network_info)
        menu.addAction(action_refresh)

        # ==========================================
        # BAGIAN BARU: UPDATE & ABOUT
        # ==========================================
        if macan_about_update:
            # 1. Check for Updates
            action_update = QAction("Check for Updates...", self)
            action_update.triggered.connect(self.trigger_check_update)
            menu.addAction(action_update)

            # 2. About
            action_about = QAction("About Macan Monitoring", self)
            action_about.triggered.connect(self.trigger_about)
            menu.addAction(action_about)
            
            menu.addSeparator()
        # ==========================================
        
        menu.addSeparator()
        power_menu = menu.addMenu("Power Options")
        if self.theme:
            power_menu.setStyleSheet(self.theme.get_menu_style())
        
        act_restart = QAction("Restart System", self)
        act_restart.triggered.connect(lambda: self.system_action("restart"))
        power_menu.addAction(act_restart)

        act_shutdown = QAction("Shutdown System", self)
        act_shutdown.triggered.connect(lambda: self.system_action("shutdown"))
        power_menu.addAction(act_shutdown)

        menu.addSeparator()

        if platform.system() == "Windows":
            action_startup = QAction("Run on Startup (EXE)", self)
            action_startup.setCheckable(True)
            action_startup.setChecked(self.check_startup_status())
            action_startup.triggered.connect(self.toggle_startup_with_elevation)
            menu.addAction(action_startup)

        menu.exec(self.btn_settings.mapToGlobal(QPoint(0, self.btn_settings.height())))

    def trigger_check_update(self):
        if macan_about_update:
            # Panggil fungsi helper dari modul, passing versi saat ini dan parent (self)
            macan_about_update.check_update_manual(APP_VERSION, self)
        else:
            QMessageBox.warning(self, "Error", "Module macan_about_update not found.")

    def trigger_about(self):
        if macan_about_update:
            macan_about_update.show_about(APP_VERSION, self)
        else:
            QMessageBox.warning(self, "Error", "Module macan_about_update not found.")

    def toggle_always_on_top(self, checked):
        if checked: self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else: self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()
        self.save_settings()

    def toggle_clock(self, checked):
        if self.clock_widget: self.clock_widget.setVisible(checked); self.save_module_states()

    def toggle_dock(self, checked):
        if self.dock_widget: self.dock_widget.setVisible(checked); self.save_module_states()
    
    def toggle_sidebar(self, checked):
        if self.sidebar_widget: self.sidebar_widget.setVisible(checked); self.save_module_states()

    def toggle_analog(self, checked):
        if self.analog_widget: self.analog_widget.setVisible(checked); self.save_module_states()

    def toggle_memo(self, checked):
        if self.memo_widget: self.memo_widget.setVisible(checked); self.save_module_states()

    def toggle_network(self, checked):
        if self.network_widget: self.network_widget.setVisible(checked); self.save_module_states()

    def toggle_disk(self, checked):
        if self.disk_widget: self.disk_widget.setVisible(checked); self.save_module_states()

    def toggle_url(self, checked):
        if self.url_widget: self.url_widget.setVisible(checked); self.save_module_states()

    def open_task_manager(self):
        if MacanTask:
            if not self.task_window:
                self.task_window = MacanTask(self)
            self.task_window.show()
            self.task_window.raise_()
        else:
            QMessageBox.warning(self, "Error", "Module macan_task.py not found.")

    def open_recycle_bin(self):
        try:
            os.system('start shell:RecycleBinFolder')
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Recycle Bin: {e}")

    def open_macan_conquer(self):
        candidate_paths = [
            r"C:\Program Files\Macan Angkasa\Macan Conquer\Macan Conquer.exe",
            r"C:\Program Files\Macan Angkasa\Fusion Suite\Macan Conquer.exe",
            r"D:\MacanStack\Macan Conquer\Macan Conquer.exe",            
        ]
        found_path = None
        for path in candidate_paths:
            if os.path.exists(path):
                found_path = path
                break
        if found_path:
            try:
                ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", found_path, None, None, 1)
                if ret <= 32: raise Exception(f"ShellExecute failed with code {ret}")
            except Exception as e:
                QMessageBox.critical(self, "Access Error", f"Failed to launch with Admin rights.\nError: {e}")
        else:
            QMessageBox.warning(self, "Not Found", "Macan Conquer application not found.")

    def system_action(self, action):
        cmd = "shutdown /s /f /t 0" if action == "shutdown" else "shutdown /r /t 0"
        if platform.system() != "Windows":
             cmd = "shutdown now" if action == "shutdown" else "reboot"
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f"Are you sure you want to {action}?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if msg.exec() == QMessageBox.Yes:
            os.system(cmd)

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def check_startup_status(self):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            key.Close()
            return True
        except WindowsError:
            return False

    def toggle_startup_with_elevation(self, checked):
        success = self.set_startup_registry(checked)
        if not success:
            print("Requesting Admin Access...")
            if not self.is_admin():
                key_path = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
                if getattr(sys, 'frozen', False): exe_path = sys.executable
                else: exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), EXE_FILENAME)
                
                if checked:
                    app_cmd = f'"{exe_path}"'
                    params = f'ADD "{key_path}" /v "{APP_NAME}" /t REG_SZ /d {app_cmd} /f'
                else:
                    params = f'DELETE "{key_path}" /v "{APP_NAME}" /f'
                
                try:
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", "reg.exe", params, None, 0)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Admin Prompt Failed: {e}")

    def set_startup_registry(self, checked):
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if checked:
                if getattr(sys, 'frozen', False): exe_path = sys.executable
                else: exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), EXE_FILENAME)
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
            else:
                try: winreg.DeleteValue(key, APP_NAME)
                except WindowsError: pass
            key.Close()
            return True
        except Exception:
            return False

    def load_module_states(self):
        if self.clock_widget and self.settings.value("show_clock", False, type=bool): self.clock_widget.show()
        if self.dock_widget and self.settings.value("show_dock", False, type=bool): self.dock_widget.show()
        if self.sidebar_widget and self.settings.value("show_sidebar", False, type=bool): self.sidebar_widget.show()
        if self.analog_widget and self.settings.value("show_analog", False, type=bool): self.analog_widget.show()
        if self.memo_widget and self.settings.value("show_memo", False, type=bool): self.memo_widget.show()
        if self.network_widget and self.settings.value("show_network", False, type=bool): self.network_widget.show()
        if self.disk_widget and self.settings.value("show_disk", False, type=bool): self.disk_widget.show()
        if self.url_widget and self.settings.value("show_url", False, type=bool): self.url_widget.show()

    def save_module_states(self):
        if self.clock_widget: self.settings.setValue("show_clock", self.clock_widget.isVisible())
        if self.dock_widget: self.settings.setValue("show_dock", self.dock_widget.isVisible())
        if self.sidebar_widget: self.settings.setValue("show_sidebar", self.sidebar_widget.isVisible())
        if self.analog_widget: self.settings.setValue("show_analog", self.analog_widget.isVisible())
        if self.memo_widget: self.settings.setValue("show_memo", self.memo_widget.isVisible())
        if self.network_widget: self.settings.setValue("show_network", self.network_widget.isVisible())
        if self.disk_widget: self.settings.setValue("show_disk", self.disk_widget.isVisible())
        if self.url_widget: self.settings.setValue("show_url", self.url_widget.isVisible())

    def load_settings(self):
        pos = self.settings.value("pos", QPoint(100, 100))
        size = self.settings.value("size", QSize(280, 320)) 
        self.move(pos)
        self.resize(size)
        if self.settings.value("always_on_top", True, type=bool):
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        
    def save_settings(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("size", self.size())
        self.settings.setValue("always_on_top", bool(self.windowFlags() & Qt.WindowStaysOnTopHint))

    def _shutdown(self):
        """Shutdown bersih satu titik. Guard double-call via _is_closing."""
        if self._is_closing:
            return
        self._is_closing = True

        self.save_settings()
        self.save_module_states()

        # Stop threads — thread sudah ber-parent self, tapi kita stop manual
        # agar tidak ada emit ke widget yang sedang di-destroy
        if hasattr(self, 'monitor_thread') and self.monitor_thread.isRunning():
            self.monitor_thread.stop()

        if hasattr(self, 'net_info_thread') and self.net_info_thread.isRunning():
            self.net_info_thread.stop()

        # Tutup semua module widget
        for w in [self.clock_widget, self.dock_widget, self.sidebar_widget,
                  self.analog_widget, self.memo_widget, self.network_widget,
                  self.disk_widget, self.url_widget, self.task_window]:
            if w is not None:
                try:
                    w.close()
                except Exception:
                    pass

    def closeEvent(self, event):
        self._shutdown()
        event.accept()

    def exit_app(self):
        self._shutdown()
        QApplication.quit()
    
    def resizeEvent(self, event):
        if hasattr(self, 'sizegrip'):
            rect = self.geometry()
            self.sizegrip.move(rect.width() - 20, rect.height() - 20)
        super().resizeEvent(event)

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
        self.save_settings()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    window = WidgetMonitor()
    window.show()
    sys.exit(app.exec())
