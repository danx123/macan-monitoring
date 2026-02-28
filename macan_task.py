import sys
import os
import psutil
import ctypes
import subprocess
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QLabel, 
    QMessageBox, QMenu, QToolBar, QApplication, QInputDialog,
    QFileIconProvider
)
from PySide6.QtCore import (
    QTimer, Qt, QUrl, QThread, Signal, QSettings, QFileInfo, QSize
)
from PySide6.QtGui import QAction, QBrush, QColor, QDesktopServices, QIcon

try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

# --- WORKER THREAD ---
class ProcessWorker(QThread):
    data_signal = Signal(list, int)

    def __init__(self):
        super().__init__()
        self.running = True
        self.proc_cache = {}

    def run(self):
        while self.running:
            try:
                current_pids = set(psutil.pids())
                cached_pids = list(self.proc_cache.keys())
                for pid in cached_pids:
                    if pid not in current_pids:
                        del self.proc_cache[pid]

                table_data = []
                
                for pid in current_pids:
                    try:
                        if pid not in self.proc_cache:
                            p = psutil.Process(pid)
                            self.proc_cache[pid] = p
                            p.cpu_percent(interval=None)
                        else:
                            p = self.proc_cache[pid]

                        with p.oneshot():
                            name = p.name()
                            try:
                                username = p.username()
                            except:
                                username = "System"
                            
                            try:
                                exe_path = p.exe()
                            except:
                                exe_path = ""

                            mem_mb = p.memory_info().rss / (1024 * 1024)
                            cpu = p.cpu_percent(interval=None)
                        
                        table_data.append({
                            "pid": pid,
                            "name": name,
                            "user": username,
                            "mem": mem_mb,
                            "cpu": cpu,
                            "path": exe_path
                        })

                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        if pid in self.proc_cache: del self.proc_cache[pid]
                        continue
                
                self.data_signal.emit(table_data, len(table_data))
                self.sleep(2)

            except Exception as e:
                print(f"Worker Error: {e}")
                self.sleep(2)

    def stop(self):
        self.running = False
        self.wait(3000)

# --- MAIN WINDOW ---
class MacanTask(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = get_theme_manager() if THEME_AVAILABLE else None
        self.setWindowTitle("Macan Task Manager Pro")
        
        self.settings = QSettings("MacanCorp", "MacanTaskPro")
        
        # Icon
        icon_path = "monitoring.ico"
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, icon_path)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            self.setWindowIcon(QFileIconProvider().icon(QFileIconProvider.Computer))

        # Apply theme
        self.apply_theme()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self.setup_toolbar()

        # Info Label
        self.info_container = QHBoxLayout()
        self.info_container.setContentsMargins(10, 5, 10, 0)
        self.info_label = QLabel(f"Initializing... | System: {os.name.upper()}")
        self.apply_info_label_style()
        self.info_container.addWidget(self.info_label)
        self.layout.addLayout(self.info_container)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Name", "PID", "User", "Memory (MB)", "CPU %"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.setIconSize(QSize(16, 16))
        
        self.layout.addWidget(self.table)

        # Bottom Controls
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(10, 10, 10, 10)
        
        self.new_task_btn = QPushButton("➕ New Task")
        self.new_task_btn.setObjectName("newTaskBtn")
        self.new_task_btn.clicked.connect(self.run_new_task)

        self.end_task_btn = QPushButton("☠️ End Task")
        self.end_task_btn.setObjectName("killBtn")
        self.end_task_btn.clicked.connect(self.kill_selected_process)
        
        btn_layout.addWidget(self.new_task_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.end_task_btn)
        self.layout.addLayout(btn_layout)

        # Icon Cache
        self.icon_provider = QFileIconProvider()
        self.icon_cache = {}
        self.default_icon = self.icon_provider.icon(QFileIconProvider.Computer)

        # Restore Settings
        self.restore_app_settings()

        # Start Worker
        self.worker = ProcessWorker()
        self.worker.data_signal.connect(self.update_table)
        self.worker.start()

    def apply_theme(self):
        """Apply theme to dialog"""
        if self.theme:
            c = self.theme.get_colors()
            dialog_bg = c['bg_main'] if self.theme.get_theme() == "dark" else c['bg_secondary']
            text_color = c['text_primary']
            
            self.setStyleSheet(f"""
                QDialog {{ 
                    background-color: {dialog_bg}; 
                    color: {text_color}; 
                    font-family: 'Segoe UI', sans-serif; 
                }}
                {self.theme.get_table_style()}
                {self.theme.get_button_style()}
                QToolBar {{ border: none; background: {c['bg_header']}; spacing: 5px; padding: 5px; }}
                QToolBar QToolButton {{ 
                    color: {text_color}; 
                    background: {c['bg_button']}; 
                    padding: 5px; 
                    border-radius: 3px; 
                }}
                QToolBar QToolButton:hover {{ background: {c['bg_button_hover']}; }}
            """)
        else:
            self.setStyleSheet("""
                QDialog { background-color: #2b2b2b; color: #f0f0f0; font-family: 'Segoe UI', sans-serif; }
                QTableWidget { 
                    background-color: #333333; 
                    color: #ffffff; 
                    gridline-color: #444444;
                    border: none;
                    selection-background-color: #0078d7;
                    selection-color: white;
                }
                QTableWidget::item { padding: 5px; }
                QHeaderView::section {
                    background-color: #404040;
                    color: #cccccc;
                    padding: 6px;
                    border: none;
                    border-right: 1px solid #555;
                    font-weight: bold;
                }
                QPushButton {
                    background-color: #4b4f52;
                    color: #f0f0f0;
                    border: 1px solid #5f6366;
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #666666; }
                QPushButton#killBtn { background-color: #8B0000; border: 1px solid #ff4444; }
                QPushButton#killBtn:hover { background-color: #cc0000; }
                QPushButton#newTaskBtn { background-color: #2E7D32; border: 1px solid #4CAF50; }
                QPushButton#newTaskBtn:hover { background-color: #388E3C; }
                QToolBar { border: none; background: #333; spacing: 5px; padding: 5px; }
                QToolBar QToolButton { color: white; background: #444; padding: 5px; border-radius: 3px; }
                QToolBar QToolButton:hover { background: #555; }
            """)

    def apply_info_label_style(self):
        """Apply theme to info label"""
        if self.theme:
            c = self.theme.get_colors()
            self.info_label.setStyleSheet(f"color: {c['text_muted']}; font-size: 12px;")
        else:
            self.info_label.setStyleSheet("color: #aaa; font-size: 12px;")

    def setup_toolbar(self):
        toolbar = QToolBar()
        self.layout.addWidget(toolbar)

        action_recycle = QAction("🗑️ Recycle Bin", self)
        action_recycle.triggered.connect(self.open_recycle_bin)
        toolbar.addAction(action_recycle)

        action_conquer = QAction("⚔️ Macan Conquer (Admin)", self)
        action_conquer.setToolTip("Runs Macan Conquer with Administrator Privileges")
        action_conquer.triggered.connect(self.open_macan_conquer)
        toolbar.addAction(action_conquer)

    def restore_app_settings(self):
        if self.settings.value("geometry"):
            self.restoreGeometry(self.settings.value("geometry"))
        else:
            self.resize(900, 650)
            
        if self.settings.value("tableState"):
            self.table.horizontalHeader().restoreState(self.settings.value("tableState"))

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("tableState", self.table.horizontalHeader().saveState())
        self.worker.stop()
        super().closeEvent(event)

    def run_new_task(self):
        text, ok = QInputDialog.getText(self, 'Run New Task', 'Open (Type command or path):')
        if ok and text:
            try:
                subprocess.Popen(text, shell=True)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not run task:\n{e}")

    def update_table(self, data_list, total_count):
        self.table.setSortingEnabled(False)
        
        current_scroll = self.table.verticalScrollBar().value()
        selected_pid = None
        current_row = self.table.currentRow()
        if current_row >= 0:
            pid_item = self.table.item(current_row, 1)
            if pid_item: selected_pid = int(pid_item.text())

        self.table.setRowCount(len(data_list))
        self.info_label.setText(f"Processes: {total_count} | Threads Active | Mode: {os.name.upper()}")

        for i, data in enumerate(data_list):
            name = data['name']
            path = data['path']
            
            if path and os.path.exists(path):
                if name not in self.icon_cache:
                    file_info = QFileInfo(path)
                    icon = self.icon_provider.icon(file_info)
                    self.icon_cache[name] = icon
                display_icon = self.icon_cache[name]
            else:
                display_icon = self.default_icon

            name_item = QTableWidgetItem(name)
            name_item.setIcon(display_icon)
            self.table.setItem(i, 0, name_item)

            pid_item = QTableWidgetItem()
            pid_item.setData(Qt.DisplayRole, data['pid'])
            self.table.setItem(i, 1, pid_item)

            self.table.setItem(i, 2, QTableWidgetItem(data['user']))

            mem_item = QTableWidgetItem()
            mem_item.setData(Qt.DisplayRole, data['mem'])
            mem_item.setText(f"{data['mem']:.2f}")
            mem_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 3, mem_item)

            cpu_val = data['cpu']
            cpu_item = QTableWidgetItem()
            cpu_item.setData(Qt.DisplayRole, cpu_val)
            cpu_item.setText(f"{cpu_val:.1f}")
            cpu_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            
            if cpu_val > 50:
                cpu_item.setForeground(QBrush(QColor("#ff5555")))
            elif cpu_val > 20:
                cpu_item.setForeground(QBrush(QColor("#ff9800")))
                
            self.table.setItem(i, 4, cpu_item)

            if selected_pid and data['pid'] == selected_pid:
                self.table.selectRow(i)

        self.table.setSortingEnabled(True)
        self.table.verticalScrollBar().setValue(current_scroll)

    def open_recycle_bin(self):
        try:
            os.system('start shell:RecycleBinFolder')
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed: {e}")

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
                ctypes.windll.shell32.ShellExecuteW(None, "runas", found_path, None, None, 1)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed: {e}")
        else:
            QMessageBox.warning(self, "Not Found", "Macan Conquer not found.")

    def kill_selected_process(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            return

        pid_item = self.table.item(current_row, 1)
        name_item = self.table.item(current_row, 0)

        if not pid_item: return
        
        pid = int(pid_item.text())
        name = name_item.text()

        confirm = QMessageBox.question(
            self, "End Task", 
            f"Kill process: {name} ({pid})?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                self.worker.start()
                QMessageBox.information(self, "Success", f"Process {name} terminated.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MacanTask()
    window.show()
    sys.exit(app.exec())