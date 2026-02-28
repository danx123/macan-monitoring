import sys
import os
import json
import urllib.request
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, 
                               QMessageBox, QHBoxLayout, QFrame)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon

# Coba import theme manager
try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

# URL Konfigurasi
# Pastikan Anda mengupload file version.json ke repository Anda nanti.
# URL Raw GitHub biasanya: https://raw.githubusercontent.com/username/repo/branch/file
UPDATE_JSON_URL = "https://raw.githubusercontent.com/danx123/macan-monitoring/main/version.json"
RELEASE_PAGE_URL = "https://github.com/danx123/macan-monitoring/releases"

# --- WORKER THREAD UNTUK CEK UPDATE (NON-BLOCKING) ---
class UpdateWorker(QThread):
    result_signal = Signal(dict) # Mengirim data JSON atau dict error
    
    def run(self):
        try:
            # Timeout 5 detik agar tidak hang lama jika internet lemot
            with urllib.request.urlopen(UPDATE_JSON_URL, timeout=5) as response:
                data = json.loads(response.read().decode())
                self.result_signal.emit(data)
        except Exception as e:
            self.result_signal.emit({"error": str(e)})

# --- FUNGSI HELPER ICON ---
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

# --- DIALOG ABOUT ---
class MacanAboutDialog(QDialog):
    def __init__(self, app_version, parent=None):
        super().__init__(parent)
        self.setWindowIcon(get_app_icon())
        self.theme = get_theme_manager() if THEME_AVAILABLE else None
        self.setWindowTitle("About Macan Monitoring")        
        self.setFixedSize(450, 350)
        
        # Setup Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 30, 20, 20)
        
        # 1. Judul / Logo
        lbl_title = QLabel("Macan Monitoring")
        lbl_title.setAlignment(Qt.AlignCenter)
        font_title = QFont("Segoe UI", 18, QFont.Bold)
        lbl_title.setFont(font_title)
        
        # 2. Versi
        lbl_version = QLabel(f"Version {app_version}")
        lbl_version.setAlignment(Qt.AlignCenter)
        lbl_version.setStyleSheet("color: #888; margin-bottom: 10px;")
        
        # 3. Deskripsi Profesional
        desc_text = (
            "Macan Monitoring is a comprehensive system diagnostics suite designed "
            "to provide real-time visibility into your hardware resources and network activity.\n\n"
            "Engineered for efficiency and aesthetics, it seamlessly integrates with your "
            "desktop environment, offering a modular dashboard for CPU, Memory, Disk, and Network telemetry.\n\n"
            "Developed by MacanAngkasa, this tool represents our commitment to precision, "
            "utility, and user-centric design."
        )
        lbl_desc = QLabel(desc_text)
        lbl_desc.setWordWrap(True)
        lbl_desc.setAlignment(Qt.AlignJustify)
        lbl_desc.setStyleSheet("margin: 10px 0px;")

        # 4. Copyright
        lbl_copy = QLabel("© 2026 MacanAngkasa Corp. All rights reserved.")
        lbl_copy.setAlignment(Qt.AlignCenter)
        lbl_copy.setStyleSheet("font-size: 10px; color: #666; margin-top: 10px;")
        
        # 5. Tombol Close
        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.close)
        btn_close.setFixedWidth(100)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        btn_layout.addStretch()

        # Add widgets
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_version)
        layout.addWidget(lbl_desc)
        layout.addStretch()
        layout.addWidget(lbl_copy)
        layout.addLayout(btn_layout)
        
        self.apply_theme(lbl_title, lbl_desc, btn_close)

    def apply_theme(self, title, desc, btn):
        if self.theme:
            c = self.theme.get_colors()
            is_dark = self.theme.get_theme() == "dark"
            
            bg = c['bg_main']
            text = c['text_primary']
            text_mute = c['text_muted']
            
            self.setStyleSheet(f"QDialog {{ background-color: {bg}; color: {text}; }}")
            title.setStyleSheet(f"color: {c['accent_orange']};")
            desc.setStyleSheet(f"color: {text}; font-size: 13px;")
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c['bg_button']};
                    color: {c['text_primary']};
                    border: 1px solid {c['border_main']};
                    padding: 6px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ background-color: {c['bg_button_hover']}; }}
            """)
        else:
            # Fallback Dark theme
            self.setStyleSheet("QDialog { background-color: #2b2b2b; color: #fff; }")
            title.setStyleSheet("color: #ff9800;")
            desc.setStyleSheet("color: #ddd; font-size: 13px;")
            btn.setStyleSheet("""
                QPushButton { background-color: #444; color: white; border: 1px solid #555; padding: 6px; border-radius: 4px; }
                QPushButton:hover { background-color: #555; }
            """)

# --- FUNGSI HELPER UNTUK DIPANGGIL DARI MAIN ---
class UpdateChecker(QDialog):
    def __init__(self, current_version, parent=None):
        super().__init__(parent)        
        self.current_version = current_version
        self.parent_widget = parent
        self.check_updates()

    def check_updates(self):
        # Tampilkan loading sederhana (opsional, atau biarkan background)
        self.worker = UpdateWorker()
        self.worker.result_signal.connect(self.handle_response)
        self.worker.start()

    def handle_response(self, data):
        # Helper kecil untuk membuat message box dengan icon custom
        def show_msg(icon_type, title, text, informative_text=None, buttons=QMessageBox.Ok):
            msg = QMessageBox(self.parent_widget)
            msg.setWindowIcon(get_app_icon())  # <--- Set Icon Window (Pojok Kiri Atas)
            msg.setIcon(icon_type)             # Set Icon Konten (Info/Warning/Error)
            msg.setWindowTitle(title)
            msg.setText(text)
            if informative_text:
                msg.setInformativeText(informative_text)
            msg.setStandardButtons(buttons)
            return msg

        if "error" in data:
            msg = show_msg(QMessageBox.Warning, "Update Check Failed", 
                           f"Could not connect to update server.\nError: {data['error']}")
            msg.exec()
            return

        remote_version = data.get("version", "0.0.0")
        notes = data.get("release_notes", "No release notes available.")
        
        # Logika perbandingan versi
        if remote_version > self.current_version:
            msg = QMessageBox(self.parent_widget)
            msg.setWindowIcon(get_app_icon()) # <--- Set Icon Window
            msg.setWindowTitle("Update Available")
            msg.setText(f"<b>A new version ({remote_version}) is available!</b>")
            msg.setInformativeText(f"Current version: {self.current_version}\n\nNotes:\n{notes}")
            msg.setIcon(QMessageBox.Information)
            
            btn_download = msg.addButton("Download", QMessageBox.AcceptRole)
            btn_cancel = msg.addButton("Later", QMessageBox.RejectRole)
            
            msg.exec()
            
            if msg.clickedButton() == btn_download:
                QDesktopServices.openUrl(QUrl(RELEASE_PAGE_URL))
        else:
            # Jika sudah versi terbaru
            msg = show_msg(QMessageBox.Information, "Up to Date", 
                           f"You are using the latest version ({self.current_version}).")
            msg.exec()

def show_about(current_version, parent):
    dlg = MacanAboutDialog(current_version, parent)
    dlg.exec()

def check_update_manual(current_version, parent):
    # Kita instansiasi class tapi tidak perlu exec(), karena worker berjalan async
    # Kita simpan referensi agar tidak di-garbage collect
    checker = UpdateChecker(current_version, parent)
    # Trik agar object checker tetap hidup sampai worker selesai:
    # (Di aplikasi simple ini, garbage collection Python biasanya aman menangani ini 
    # selama thread berjalan, tapi idealnya di handle di main window class property)
    setattr(parent, "_update_checker_ref", checker)