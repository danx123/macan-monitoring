import sys
import psutil
import time
import os
import shutil
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLabel, QProgressBar, QPushButton, QMenu, QFrame, 
                               QSizeGrip, QScrollArea, QMessageBox)
from PySide6.QtCore import Qt, QThread, Signal, QPoint, QSettings, QSize
from PySide6.QtGui import QAction, QFont

# --- IMPORT THEME MANAGER ---
try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

APP_NAME = "Macan Disk Info"
ORG_NAME = "MacanAngkasa"

# --- WORKER: DISK MONITOR ---
class DiskWorker(QThread):
    stats_signal = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def run(self):
        while self._running:
            disk_data = []
            try:
                partitions = psutil.disk_partitions(all=False)
                for p in partitions:
                    if not self._running:
                        return
                    try:
                        if 'cdrom' in p.opts or p.fstype == '':
                            continue
                        usage = psutil.disk_usage(p.mountpoint)
                        name = p.mountpoint
                        if name.endswith('\\'): name = name[:-1]
                        disk_data.append({
                            'name': name,
                            'device': p.device,
                            'total': usage.total,
                            'free': usage.free,
                            'used': usage.used,
                            'percent': usage.percent
                        })
                    except PermissionError:
                        continue

                if self._running:
                    self.stats_signal.emit(disk_data)

                # Sleep interruptible 5 detik
                for _ in range(50):
                    if not self._running:
                        return
                    time.sleep(0.1)

            except Exception as e:
                print(f"Disk monitor error: {e}")
                break

    def stop(self):
        self._running = False
        self.wait(3000)

# --- UI COMPONENT: DISK BAR ---
class DiskBar(QWidget):
    def __init__(self, drive_name, theme_manager=None):
        super().__init__()
        self.theme = theme_manager
        self.drive_name = drive_name
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(2)
        
        # Header
        header_layout = QHBoxLayout()
        self.lbl_name = QLabel(f"💿 {drive_name}")
        self.lbl_value = QLabel("Loading...")
        self.lbl_value.setAlignment(Qt.AlignRight)

        self.apply_theme()

        header_layout.addWidget(self.lbl_name)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_value)

        # Progress Bar
        self.pbar = QProgressBar()
        self.pbar.setTextVisible(False)
        self.pbar.setFixedHeight(6)
        self.pbar.setRange(0, 100)
        self.update_progressbar_style()

        layout.addLayout(header_layout)
        layout.addWidget(self.pbar)
        self.setLayout(layout)

    def apply_theme(self):
        """Apply theme to labels"""
        if self.theme:
            c = self.theme.get_colors()
            self.lbl_name.setStyleSheet(f"color: {c['text_secondary']}; font-weight: bold; font-size: 11px;")
            self.lbl_value.setStyleSheet(f"color: {c['text_muted']}; font-size: 10px;")
        else:
            self.lbl_name.setStyleSheet("color: #e0e0e0; font-weight: bold; font-size: 11px;")
            self.lbl_value.setStyleSheet("color: #aaa; font-size: 10px;")

    def update_progressbar_style(self, percent=0):
        """Update progressbar with color based on usage"""
        if self.theme:
            c = self.theme.get_colors()
            if percent < 75:
                color = c['accent_green']
            elif percent < 90:
                color = c['accent_orange']
            else:
                color = c['accent_red']
            
            self.pbar.setStyleSheet(f"""
                QProgressBar {{ border: none; background-color: {c['progress_bg']}; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}
            """)
        else:
            if percent < 75:
                color = "#8bc34a"
            elif percent < 90:
                color = "#ff9800"
            else:
                color = "#ff5555"
                
            self.pbar.setStyleSheet(f"""
                QProgressBar {{ border: none; background-color: #404040; border-radius: 3px; }}
                QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}
            """)

    def update_data(self, total, free, percent):
        total_str = self.format_bytes(total)
        free_str = self.format_bytes(free)
        
        self.lbl_value.setText(f"Free: {free_str} / {total_str}")
        self.pbar.setValue(int(percent))
        self.update_progressbar_style(percent)

    def format_bytes(self, size):
        power = 2**30
        n = size / power
        if n > 1000:
            return f"{n/1024:.1f} TB"
        else:
            return f"{n:.1f} GB"

# --- MAIN WINDOW ---
class MacanDisk(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = get_theme_manager() if THEME_AVAILABLE else None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.old_pos = None
        self.disk_widgets = {}

        self.setup_ui()
        self.load_settings()

        self.worker = DiskWorker(self)
        self.worker.stats_signal.connect(self.update_ui)
        self.worker.start()

    def setup_ui(self):
        self.container = QFrame()
        self.container.setObjectName("MainFrame")
        self.apply_theme()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

        content_layout = QVBoxLayout(self.container)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(5)

        # Header
        header = QHBoxLayout()
        self.title = QLabel("Disk Info")

        self.btn_clear_temp = QPushButton("🧹 Clear Temp")
        self.btn_clear_temp.setFixedHeight(20)
        self.btn_clear_temp.setCursor(Qt.PointingHandCursor)
        self.btn_clear_temp.setToolTip("Clear Windows Temporary Files")
        self.btn_clear_temp.clicked.connect(self.clear_temp_files)

        self.btn_menu = QPushButton("⚙")
        self.btn_menu.setFixedSize(20, 20)
        self.btn_menu.setCursor(Qt.PointingHandCursor)
        self.btn_menu.clicked.connect(self.show_context_menu)

        self.btn_hide = QPushButton("✕")
        self.btn_hide.setFixedSize(20, 20)
        self.btn_hide.setCursor(Qt.PointingHandCursor)
        self.btn_hide.clicked.connect(self.close_or_hide)

        self.apply_header_styles()

        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.btn_clear_temp)
        header.addWidget(self.btn_menu)
        header.addWidget(self.btn_hide)
        content_layout.addLayout(header)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.disks_container = QWidget()
        self.disks_container.setStyleSheet("background: transparent;")
        self.disks_layout = QVBoxLayout(self.disks_container)
        self.disks_layout.setContentsMargins(0, 0, 0, 0)
        self.disks_layout.setSpacing(0)
        self.disks_layout.addStretch()

        self.scroll_area.setWidget(self.disks_container)
        content_layout.addWidget(self.scroll_area)

        # Size Grip
        grip_layout = QHBoxLayout()
        grip_layout.addStretch()
        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setStyleSheet("background: transparent; width: 10px; height: 10px;")
        grip_layout.addWidget(self.sizegrip, 0, Qt.AlignBottom | Qt.AlignRight)
        self.sizegrip.setParent(self.container)

    def apply_theme(self):
        """Apply theme to main container"""
        if self.theme:
            self.container.setStyleSheet(self.theme.get_main_window_style())
        else:
            self.container.setStyleSheet("""
                QFrame#MainFrame {
                    background-color: rgba(20, 20, 20, 220); 
                    border: 1px solid #555;
                    border-radius: 10px;
                }
            """)

    def apply_header_styles(self):
        """Apply theme to header elements"""
        if self.theme:
            c = self.theme.get_colors()
            self.title.setStyleSheet(f"color: {c['accent_pink']}; font-weight: bold; font-size: 12px;")
            btn_style = f"QPushButton {{ color: {c['text_muted']}; background: transparent; border: none; }} QPushButton:hover {{ color: {c['text_primary']}; }}"
            self.btn_menu.setStyleSheet(btn_style)
            self.btn_hide.setStyleSheet(f"QPushButton {{ color: {c['text_muted']}; background: transparent; border: none; }} QPushButton:hover {{ color: {c['accent_red']}; }}")
            self.btn_clear_temp.setStyleSheet(f"""
                QPushButton {{
                    color: {c['accent_green']}; background: rgba(139,195,74,15);
                    border: 1px solid rgba(139,195,74,60); border-radius: 4px;
                    font-size: 10px; padding: 0 6px;
                }}
                QPushButton:hover {{ background: rgba(139,195,74,35); }}
                QPushButton:disabled {{ color: {c['text_muted']}; background: transparent; border-color: transparent; }}
            """)
        else:
            self.title.setStyleSheet("color: #E91E63; font-weight: bold; font-size: 12px;")
            self.btn_menu.setStyleSheet("color: #aaa; background: transparent; border: none;")
            self.btn_hide.setStyleSheet("color: #aaa; background: transparent; border: none;")
            self.btn_clear_temp.setStyleSheet("""
                QPushButton {
                    color: #8bc34a; background: rgba(139,195,74,15);
                    border: 1px solid rgba(139,195,74,60); border-radius: 4px;
                    font-size: 10px; padding: 0 6px;
                }
                QPushButton:hover { background: rgba(139,195,74,35); }
                QPushButton:disabled { color: #555; background: transparent; border-color: transparent; }
            """)

    def update_ui(self, disk_data_list):
        present_drives = []
        
        for data in disk_data_list:
            drive_name = data['name']
            present_drives.append(drive_name)
            
            if drive_name not in self.disk_widgets:
                # Pass self.theme
                new_widget = DiskBar(drive_name, self.theme)
                count = self.disks_layout.count()
                self.disks_layout.insertWidget(count - 1, new_widget)
                self.disk_widgets[drive_name] = new_widget
            
            self.disk_widgets[drive_name].update_data(data['total'], data['free'], data['percent'])

        current_keys = list(self.disk_widgets.keys())
        for key in current_keys:
            if key not in present_drives:
                widget = self.disk_widgets.pop(key)
                widget.deleteLater()

    def clear_temp_files(self):
        """Clear Windows temporary files"""
        self.btn_clear_temp.setEnabled(False)
        self.btn_clear_temp.setText("Clearing...")

        temp_dirs = []
        win_temp = os.environ.get("TEMP", "")
        if win_temp and os.path.isdir(win_temp):
            temp_dirs.append(win_temp)
        user_temp = os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Temp")
        if user_temp and os.path.isdir(user_temp) and user_temp not in temp_dirs:
            temp_dirs.append(user_temp)

        deleted_count = 0
        failed_count = 0
        for temp_dir in temp_dirs:
            try:
                for item in os.listdir(temp_dir):
                    item_path = os.path.join(temp_dir, item)
                    try:
                        if os.path.isfile(item_path) or os.path.islink(item_path):
                            os.unlink(item_path)
                            deleted_count += 1
                        elif os.path.isdir(item_path):
                            shutil.rmtree(item_path, ignore_errors=True)
                            deleted_count += 1
                    except Exception:
                        failed_count += 1
            except Exception as e:
                print(f"Error clearing temp: {e}")

        msg = QMessageBox(self)
        msg.setWindowTitle("Clear Temp")
        msg.setText(f"✅ Done!\n\nDeleted: {deleted_count} items\nSkipped (in use): {failed_count} items")
        msg.setIcon(QMessageBox.Information)
        if self.theme:
            c = self.theme.get_colors()
            msg.setStyleSheet(f"background-color: {c['bg_main']}; color: {c['text_primary']};")
        msg.exec()

        self.btn_clear_temp.setEnabled(True)
        self.btn_clear_temp.setText("🧹 Clear Temp")

    def show_context_menu(self):
        menu = QMenu(self)
        if self.theme:
            menu.setStyleSheet(self.theme.get_menu_style())
        else:
            menu.setStyleSheet("""
                QMenu { background-color: #333; color: white; border: 1px solid #555; }
                QMenu::item { padding: 5px 20px; }
                QMenu::item:selected { background-color: #555; }
            """)
        
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

    def load_settings(self):
        pos = self.settings.value("pos", QPoint(250, 250))
        size = self.settings.value("size", QSize(250, 200))
        ontop = self.settings.value("always_on_top", False, type=bool)
        
        self.move(pos)
        self.resize(size)
        if ontop:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

    def save_settings(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("size", self.size())
        self.settings.setValue("always_on_top", bool(self.windowFlags() & Qt.WindowStaysOnTopHint))

    def close_or_hide(self):
        self.save_settings()
        self.hide()

    def closeEvent(self, event):
        self.save_settings()
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
        event.accept()

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
    w = MacanDisk()
    w.show()
    sys.exit(app.exec())