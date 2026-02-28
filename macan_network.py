import sys
import psutil
import time
import os
import subprocess
import platform
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QProgressBar, QPushButton, QMenu, QFrame, 
                               QSizeGrip, QDialog, QTableWidget, QTableWidgetItem,
                               QHeaderView, QMessageBox, QFileIconProvider)
from PySide6.QtCore import (Qt, QThread, Signal, QPoint, QSettings, QFileInfo, 
                            QSize, QTimer)
from PySide6.QtGui import (QAction, QFont, QColor, QBrush, QPainter, QPainterPath, 
                           QPen, QLinearGradient, QIcon, QGradient)

# --- IMPORT THEME MANAGER ---
try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

APP_NAME = "Macan Network"
ORG_NAME = "MacanAngkasa"

def get_app_icon():
    filename = "monitoring.ico"
    # 1. Cek apakah running via PyInstaller Bundle
    if hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, filename)
    else:
        # 2. Jika running mode development (script), ambil path absolut file ini
        # Ini mencegah error jika script dijalankan dari direktori lain
        base_path = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_path, filename)
    
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    
    # Debugging print (akan muncul di console jika ada masalah, tidak muncul di windowed exe)
    print(f"Warning: Icon not found at {icon_path}")
    return QIcon()

# --- HELPER: CUSTOM GRAPH WIDGET (cFosSpeed Style) ---
# Mode: 0 = Fill (default), 1 = Line, 2 = Bar
GRAPH_MODES = ["Fill", "Line", "Bar"]

class TrafficGraph(QWidget):
    mode_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.dl_history = [0.0] * 60
        self.ul_history = [0.0] * 60
        self.max_speed = 1024 * 10

        self.color_dl = QColor("#00bcd4")
        self.color_ul = QColor("#ff9800")
        self.bg_color = QColor("#222")
        self.graph_mode = 0  # 0=Fill, 1=Line, 2=Bar

        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to change traffic mode")

    def set_mode(self, mode):
        self.graph_mode = mode % len(GRAPH_MODES)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.graph_mode = (self.graph_mode + 1) % len(GRAPH_MODES)
            self.setToolTip(f"Mode: {GRAPH_MODES[self.graph_mode]} — Click to change")
            self.mode_changed.emit(self.graph_mode)
            self.update()
        super().mousePressEvent(event)

    def update_data(self, dl, ul):
        self.dl_history.pop(0)
        self.dl_history.append(dl)
        self.ul_history.pop(0)
        self.ul_history.append(ul)

        current_max = max(max(self.dl_history), max(self.ul_history))
        if current_max > 0:
            self.max_speed = current_max * 1.2
        else:
            self.max_speed = 1024 * 10

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, self.bg_color)

        painter.setPen(QPen(QColor(60, 60, 60), 1, Qt.DotLine))
        painter.drawLine(0, h//2, w, h//2)

        # Label mode di pojok kiri atas
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.setFont(QFont("Segoe UI", 7))
        painter.drawText(3, 10, GRAPH_MODES[self.graph_mode])

        if self.max_speed == 0:
            return

        if self.graph_mode == 0:
            self._draw_fill(painter, w, h)
        elif self.graph_mode == 1:
            self._draw_line(painter, w, h)
        elif self.graph_mode == 2:
            self._draw_bar(painter, w, h)

    def _draw_fill(self, painter, w, h):
        step_x = w / (len(self.dl_history) - 1)

        path_dl = QPainterPath()
        path_dl.moveTo(0, h)
        for i, val in enumerate(self.dl_history):
            path_dl.lineTo(i * step_x, h - (val / self.max_speed * h))
        path_dl.lineTo(w, h)
        path_dl.closeSubpath()

        grad_dl = QLinearGradient(0, 0, 0, h)
        c_dl = QColor(self.color_dl)
        c_dl.setAlpha(100)
        grad_dl.setColorAt(0, c_dl)
        grad_dl.setColorAt(1, Qt.transparent)
        painter.fillPath(path_dl, grad_dl)
        painter.setPen(QPen(self.color_dl, 1.5))
        painter.drawPath(path_dl)

        path_ul = QPainterPath()
        path_ul.moveTo(0, h - (self.ul_history[0] / self.max_speed * h))
        for i, val in enumerate(self.ul_history):
            path_ul.lineTo(i * step_x, h - (val / self.max_speed * h))
        painter.setPen(QPen(self.color_ul, 1.5))
        painter.drawPath(path_ul)

    def _draw_line(self, painter, w, h):
        step_x = w / (len(self.dl_history) - 1)

        path_dl = QPainterPath()
        path_dl.moveTo(0, h - (self.dl_history[0] / self.max_speed * h))
        for i, val in enumerate(self.dl_history):
            path_dl.lineTo(i * step_x, h - (val / self.max_speed * h))
        painter.setPen(QPen(self.color_dl, 2))
        painter.drawPath(path_dl)

        path_ul = QPainterPath()
        path_ul.moveTo(0, h - (self.ul_history[0] / self.max_speed * h))
        for i, val in enumerate(self.ul_history):
            path_ul.lineTo(i * step_x, h - (val / self.max_speed * h))
        painter.setPen(QPen(self.color_ul, 2))
        painter.drawPath(path_ul)

    def _draw_bar(self, painter, w, h):
        n = len(self.dl_history)
        bar_w = max(1, w / n - 1)
        step_x = w / n

        for i in range(n):
            x = i * step_x

            dl_h = (self.dl_history[i] / self.max_speed) * h
            c_dl = QColor(self.color_dl)
            c_dl.setAlpha(180)
            painter.fillRect(int(x), int(h - dl_h), max(1, int(bar_w)), max(1, int(dl_h)), c_dl)

            ul_h = (self.ul_history[i] / self.max_speed) * (h * 0.6)
            c_ul = QColor(self.color_ul)
            c_ul.setAlpha(160)
            painter.fillRect(int(x), int(h - ul_h), max(1, int(bar_w)), max(1, int(ul_h)), c_ul)



# --- WORKER: NETWORK MONITOR (SPEED) ---
class NetworkWorker(QThread):
    stats_signal = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def run(self):
        last_net = psutil.net_io_counters()
        while self._running:
            try:
                for _ in range(10):
                    if not self._running:
                        return
                    time.sleep(0.1)

                if not self._running:
                    return

                current_net = psutil.net_io_counters()
                bytes_sent = current_net.bytes_sent - last_net.bytes_sent
                bytes_recv = current_net.bytes_recv - last_net.bytes_recv
                last_net = current_net

                if self._running:
                    self.stats_signal.emit(float(bytes_recv), float(bytes_sent))
            except Exception as e:
                print(f"Net Monitor error: {e}")
                break

    def stop(self):
        self._running = False
        self.wait(3000)

# --- WORKER: NETWORK APPS SCANNER ---
class NetworkAppsWorker(QThread):
    apps_signal = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def run(self):
        while self._running:
            try:
                connections = psutil.net_connections(kind='inet')
                data = []
                icon_provider = QFileIconProvider()
                seen_pids = set()

                for conn in connections:
                    if not self._running:
                        return
                    if conn.status != psutil.CONN_ESTABLISHED:
                        continue
                    if conn.pid in seen_pids:
                        continue
                    try:
                        proc = psutil.Process(conn.pid)
                        proc_name = proc.name()
                        exe_path = proc.exe()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue

                    raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "Unknown"
                    seen_pids.add(conn.pid)
                    data.append({
                        'pid': conn.pid,
                        'name': proc_name,
                        'path': exe_path,
                        'raddr': raddr,
                        'status': conn.status
                    })

                if self._running:
                    self.apps_signal.emit(data)

                for _ in range(30):
                    if not self._running:
                        return
                    time.sleep(0.1)

            except Exception as e:
                print(f"Apps Worker Error: {e}")
                for _ in range(30):
                    if not self._running:
                        return
                    time.sleep(0.1)

    def stop(self):
        self._running = False
        self.wait(3000)

# --- UI COMPONENT: NET STAT BAR ---
class NetStat(QWidget):
    def __init__(self, label_text, icon_char, color_code, theme_manager=None):
        super().__init__()
        self.theme = theme_manager
        self.color_code = color_code
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(1)
        
        header_layout = QHBoxLayout()
        self.lbl_icon = QLabel(icon_char)
        self.lbl_name = QLabel(label_text)
        self.lbl_value = QLabel("0 B/s")
        self.lbl_value.setAlignment(Qt.AlignRight)

        self.apply_theme()

        header_layout.addWidget(self.lbl_icon)
        header_layout.addWidget(self.lbl_name)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_value)

        self.pbar = QProgressBar()
        self.pbar.setTextVisible(False)
        self.pbar.setFixedHeight(3)
        self.pbar.setRange(0, 100)
        self.update_progressbar_style()

        layout.addLayout(header_layout)
        layout.addWidget(self.pbar)
        self.setLayout(layout)

    def apply_theme(self):
        """Apply theme to labels"""
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
        c_bg = "#404040"
        if self.theme:
            c_bg = self.theme.get_colors()['progress_bg']
        
        self.pbar.setStyleSheet(f"""
            QProgressBar {{ border: none; background-color: {c_bg}; border-radius: 1px; }}
            QProgressBar::chunk {{ background-color: {self.color_code}; border-radius: 1px; }}
        """)

    def update_speed(self, bytes_sec):
        text = self.format_speed(bytes_sec)
        self.lbl_value.setText(text)
        # Visual scaling: Max bar penuh di 5 MB/s
        max_visual = 5 * 1024 * 1024
        percentage = (bytes_sec / max_visual) * 100
        if percentage > 100: percentage = 100
        self.pbar.setValue(int(percentage))

    def format_speed(self, bytes_sec):
        if bytes_sec < 1024: return f"{bytes_sec:.0f} B/s"
        elif bytes_sec < 1024 * 1024: return f"{bytes_sec / 1024:.1f} KB/s"
        else: return f"{bytes_sec / (1024 * 1024):.1f} MB/s"

# --- WINDOW: NETWORK APPS MANAGER ---
class NetworkAppsWindow(QDialog):
    def __init__(self, parent=None, theme_manager=None):
        super().__init__(parent)
        self.theme = theme_manager
        self.setWindowTitle("Live App Connections")
        self.resize(550, 450)
        self.setWindowIcon(get_app_icon())
        
        layout = QVBoxLayout(self)

        # --- BARU: Area Toolbar untuk Tombol Refresh ---
        toolbar_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton("Refresh Connection")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        # Style sedikit agar terlihat bagus
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                padding: 6px 15px;
                font-weight: bold;
                border-radius: 4px;
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #555;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border: 1px solid #777;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #555;
            }
        """)
        self.btn_refresh.clicked.connect(self.handle_refresh)

        toolbar_layout.addWidget(self.btn_refresh)
        toolbar_layout.addStretch() # Mendorong tombol ke kiri (spasi kosong di kanan)
        
        layout.addLayout(toolbar_layout)
        # -----------------------------------------------
        
        # Info
        info_layout = QHBoxLayout()
        lbl_info = QLabel("<b>Active Connections</b>")
        lbl_hint = QLabel("Requires Admin for full process names")
        lbl_hint.setStyleSheet("color: #777; font-size: 10px;")
        info_layout.addWidget(lbl_info)
        info_layout.addStretch()
        info_layout.addWidget(lbl_hint)
        layout.addLayout(info_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["App", "PID", "Remote Address", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setShowGrid(False)
        self.table.setIconSize(QSize(24, 24)) # Ukuran Icon
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch) # Name Stretch
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        
        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_kill = QPushButton("End Task")
        self.btn_kill.setIcon(QIcon.fromTheme("process-stop")) # Try standard icon
        self.btn_kill.clicked.connect(self.kill_process)
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_kill)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.apply_theme()
        
        self.icon_provider = QFileIconProvider()

        # Worker
        self.worker = NetworkAppsWorker()
        self.worker.apps_signal.connect(self.update_table)
        self.worker.start()

    def apply_theme(self):
        if self.theme:
            c = self.theme.get_colors()
            self.setStyleSheet(f"background-color: {c['bg_main']}; color: {c['text_primary']};")
            self.table.setStyleSheet(f"""
                QTableWidget {{ background-color: {c['bg_secondary']}; border: 1px solid #444; }}
                QHeaderView::section {{ background-color: {c['bg_header']}; border: none; padding: 4px; }}
                QTableWidget::item {{ padding: 5px; }}
                QTableWidget::item:selected {{ background-color: {c['accent_red']}; }}
            """)
            self.btn_kill.setStyleSheet(f"background-color: {c['accent_red']}; color: white; border-radius: 4px; padding: 6px 12px;")
            self.btn_close.setStyleSheet(f"background-color: #555; color: white; border-radius: 4px; padding: 6px 12px;")
        else:
            self.setStyleSheet("background-color: #2b2b2b; color: #eee;")
            self.table.setStyleSheet("QTableWidget { background-color: #333; border: 1px solid #444; }")
            self.btn_kill.setStyleSheet("background-color: #d32f2f; color: white; padding: 6px;")
            self.btn_close.setStyleSheet("background-color: #555; color: white; padding: 6px;")

    def update_table(self, data):
        current_row = self.table.currentRow()
        sel_pid = None
        if current_row >= 0:
            item = self.table.item(current_row, 1)
            if item: sel_pid = item.text()

        self.table.setRowCount(len(data))
        self.table.setSortingEnabled(False)
        
        for i, row in enumerate(data):
            # Column 0: Icon + Name
            name_item = QTableWidgetItem(row['name'])
            
            # --- GET ICON FROM PATH ---
            if row['path'] and os.path.exists(row['path']):
                file_info = QFileInfo(row['path'])
                icon = self.icon_provider.icon(file_info)
                name_item.setIcon(icon)
            
            self.table.setItem(i, 0, name_item)
            
            # Column 1: PID
            self.table.setItem(i, 1, QTableWidgetItem(str(row['pid'])))
            
            # Column 2: Remote
            self.table.setItem(i, 2, QTableWidgetItem(str(row['raddr'])))
            
            # Column 3: Status
            stat_item = QTableWidgetItem("ACTIVE")
            stat_item.setForeground(QBrush(QColor("#4caf50"))) # Green
            stat_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 3, stat_item)

            # Restore selection
            if str(row['pid']) == sel_pid:
                self.table.selectRow(i)
                
        self.table.setSortingEnabled(True)
        # --- BARU: Kembalikan status tombol ---
        if hasattr(self, 'btn_refresh'):
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("Refresh Connection")

    def kill_process(self):
        row = self.table.currentRow()
        if row < 0: return

        pid_text = self.table.item(row, 1).text()
        name_text = self.table.item(row, 0).text()
        
        msg = QMessageBox(self)
        msg.setWindowTitle("End Task")
        msg.setText(f"Stop process {name_text}?")
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        
        # Style message box
        if self.theme:
            c = self.theme.get_colors()
            msg.setStyleSheet(f"background-color: {c['bg_main']}; color: {c['text_primary']};")
        
        if msg.exec() == QMessageBox.Yes:
            try:
                psutil.Process(int(pid_text)).terminate()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    # --- BARU: Fungsi Handler Tombol ---
    def handle_refresh(self):
        # Ubah status tombol jadi disable agar tidak di-spam
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Refreshing...")
        
        # Bersihkan tabel untuk memberi efek visual "reset"
        self.table.setRowCount(0)
        
        # Kita tidak perlu memanggil thread secara manual karena 
        # AppsNetworkThread berjalan otomatis setiap 2 detik.
        # Data akan muncul lagi saat thread mengirim sinyal update_table berikutnya.

    def show_table_context_menu(self, pos):
        """Tampilkan context menu saat klik kanan pada tabel"""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        self.table.selectRow(row)

        menu = QMenu(self)
        if self.theme:
            menu.setStyleSheet(self.theme.get_menu_style() if hasattr(self.theme, 'get_menu_style') else "")
        else:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2d2d2d;
                    color: #eee;
                    border: 1px solid #555;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 6px 20px;
                    border-radius: 3px;
                }
                QMenu::item:selected {
                    background-color: #444;
                }
                QMenu::separator {
                    height: 1px;
                    background: #555;
                    margin: 3px 8px;
                }
            """)

        act_open_location = QAction("📂  Open File Location", self)
        act_open_location.triggered.connect(lambda: self.open_file_location(row))
        menu.addAction(act_open_location)

        menu.addSeparator()

        act_kill = QAction("🛑  End Task", self)
        act_kill.triggered.connect(self.kill_process)
        menu.addAction(act_kill)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def open_file_location(self, row):
        """Buka folder lokasi file executable dari proses yang dipilih"""
        if row < 0:
            return

        # Ambil PID dari kolom 1
        pid_item = self.table.item(row, 1)
        if not pid_item:
            return

        try:
            pid = int(pid_item.text())
            proc = psutil.Process(pid)
            exe_path = proc.exe()
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError) as e:
            QMessageBox.warning(self, "Open File Location", f"Cannot get process path:\n{e}")
            return

        if not exe_path or not os.path.exists(exe_path):
            QMessageBox.warning(self, "Open File Location", f"File not found:\n{exe_path}")
            return

        folder_path = os.path.dirname(exe_path)
        system = platform.system()

        try:
            if system == "Windows":
                # Buka Explorer dan highlight file-nya
                subprocess.Popen(["explorer", "/select,", exe_path])
            elif system == "Darwin":
                subprocess.Popen(["open", "-R", exe_path])
            else:
                # Linux: buka folder saja (highlight file tidak didukung di semua file manager)
                subprocess.Popen(["xdg-open", folder_path])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open location:\n{e}")

    def closeEvent(self, event):
        if self.worker.isRunning():
            self.worker.stop()
        super().closeEvent(event)

# --- MAIN CLASS ---
class MacanNetwork(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = get_theme_manager() if THEME_AVAILABLE else None
        
        flags = Qt.FramelessWindowHint | Qt.Tool
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.old_pos = None
        self.apps_window = None

        self.setup_ui()
        self.load_settings()

        self.worker = NetworkWorker(self)
        self.worker.stats_signal.connect(self.on_stats_update)
        self.worker.start()

    def setup_ui(self):
        self.container = QFrame()
        self.container.setObjectName("MainFrame")
        self.apply_theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

        content_layout = QVBoxLayout(self.container)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(4)

        # 1. Header (Title + Buttons)
        header = QHBoxLayout()
        self.title = QLabel("Network Traffic")
        
        self.btn_apps = QPushButton("📊") # Tombol Grafik/Apps
        self.btn_apps.setFixedSize(22, 22)
        self.btn_apps.setCursor(Qt.PointingHandCursor)
        self.btn_apps.setToolTip("Show Active Apps")
        self.btn_apps.clicked.connect(self.show_network_apps)

        self.btn_menu = QPushButton("⚙")
        self.btn_menu.setFixedSize(22, 22)
        self.btn_menu.setCursor(Qt.PointingHandCursor)
        self.btn_menu.clicked.connect(self.show_context_menu)

        self.btn_hide = QPushButton("✕")
        self.btn_hide.setFixedSize(22, 22)
        self.btn_hide.setCursor(Qt.PointingHandCursor)
        self.btn_hide.clicked.connect(self.close_or_hide)

        self.apply_header_styles()

        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.btn_apps)
        header.addWidget(self.btn_menu)
        header.addWidget(self.btn_hide)
        content_layout.addLayout(header)

        # 2. Grafik Realtime (cFos Style)
        self.graph = TrafficGraph()
        self.graph.mode_changed.connect(self.on_graph_mode_changed)
        content_layout.addWidget(self.graph)

        # 3. Stats Bar (Text & Simple Bar)
        if self.theme:
            c = self.theme.get_colors()
            self.row_dl = NetStat("DL", "↓", c['download_color'], self.theme)
            self.row_ul = NetStat("UL", "↑", c['upload_color'], self.theme)
        else:
            self.row_dl = NetStat("DL", "↓", "#00bcd4")
            self.row_ul = NetStat("UL", "↑", "#ff9800")
            
        content_layout.addWidget(self.row_dl)
        content_layout.addWidget(self.row_ul)

        # 4. Resizer
        grip_layout = QHBoxLayout()
        grip_layout.addStretch()
        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setStyleSheet("background: transparent; width: 12px; height: 12px;")
        grip_layout.addWidget(self.sizegrip, 0, Qt.AlignBottom | Qt.AlignRight)
        
        # Trik agar grip ada di pojok kanan bawah container
        self.sizegrip.setParent(self.container)

    def on_stats_update(self, dl, ul):
        self.row_dl.update_speed(dl)
        self.row_ul.update_speed(ul)
        self.graph.update_data(dl, ul)

    def on_graph_mode_changed(self, mode):
        self.save_settings()

    def load_settings(self):
        pos = self.settings.value("pos", QPoint(100, 100))
        ontop = self.settings.value("always_on_top", False, type=bool)
        graph_mode = self.settings.value("graph_mode", 0, type=int)
        self.move(pos)
        if ontop:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.graph.set_mode(graph_mode)

    def save_settings(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("always_on_top", bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        self.settings.setValue("graph_mode", self.graph.graph_mode)

    def close_or_hide(self):
        self.save_settings()
        if self.apps_window:
            self.apps_window.close()
        self.hide()

    def closeEvent(self, event):
        self.save_settings()
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
        if self.apps_window:
            self.apps_window.close()
        event.accept()

    def apply_theme(self):
        if self.theme:
            self.container.setStyleSheet(self.theme.get_main_window_style())
        else:
            self.container.setStyleSheet("""
                QFrame#MainFrame {
                    background-color: rgba(20, 20, 20, 230); 
                    border: 1px solid #444;
                    border-radius: 8px;
                }
            """)

    def apply_header_styles(self):
        if self.theme:
            c = self.theme.get_colors()
            self.title.setStyleSheet(f"color: {c['text_primary']}; font-weight: bold; font-size: 12px;")
            btn_css = f"""
                QPushButton {{ color: {c['text_muted']}; background: transparent; border: none; border-radius: 3px; }} 
                QPushButton:hover {{ background-color: {c['bg_header']}; color: {c['text_primary']}; }}
            """
            self.btn_menu.setStyleSheet(btn_css)
            self.btn_apps.setStyleSheet(btn_css)
            self.btn_hide.setStyleSheet(f"QPushButton {{ color: {c['text_muted']}; background: transparent; border: none; }} QPushButton:hover {{ color: {c['accent_red']}; }}")
        else:
            self.title.setStyleSheet("color: #fff; font-weight: bold; font-size: 12px;")
            self.btn_menu.setStyleSheet("color: #aaa; background: transparent; border: none;")
            self.btn_apps.setStyleSheet("color: #aaa; background: transparent; border: none;")
            self.btn_hide.setStyleSheet("color: #aaa; background: transparent; border: none;")

    def show_network_apps(self):
        """Membuka jendela detail aplikasi di tengah layar"""
        if not self.apps_window:
            self.apps_window = NetworkAppsWindow(self, self.theme)
        
        # --- LOGIKA POSISI TENGAH LAYAR ---
        # 1. Ambil geometri (ukuran) layar yang sedang digunakan
        screen_geo = self.screen().availableGeometry()
        
        # 2. Ambil geometri jendela aplikasi network
        window_geo = self.apps_window.frameGeometry()
        
        # 3. Hitung titik tengah
        center_point = screen_geo.center()
        
        # 4. Pindahkan 'bayangan' geometri jendela ke tengah
        window_geo.moveCenter(center_point)
        
        # 5. Terapkan posisi tersebut ke jendela asli
        self.apps_window.move(window_geo.topLeft())
        # ----------------------------------

        self.apps_window.show()
        self.apps_window.raise_()
        self.apps_window.activateWindow() # Pastikan window fokus ke depan

    def show_context_menu(self):
        menu = QMenu(self)
        if self.theme:
            menu.setStyleSheet(self.theme.get_menu_style())
        else:
            menu.setStyleSheet("QMenu { background: #333; color: white; }")
        
        act_ontop = QAction("Always on Top", self)
        act_ontop.setCheckable(True)
        act_ontop.setChecked(bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        act_ontop.triggered.connect(self.toggle_ontop)
        menu.addAction(act_ontop)

        menu.exec(self.cursor().pos())

    def toggle_ontop(self, checked):
        if checked:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()
        self.save_settings()

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
    w = MacanNetwork()
    w.show()
    sys.exit(app.exec())