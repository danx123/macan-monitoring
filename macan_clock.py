import sys
from PySide6.QtWidgets import (QWidget, QLabel, QVBoxLayout, QApplication)
from PySide6.QtCore import Qt, QTimer, QTime, QDate, QPoint, QSettings

try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

class MacanClock(QWidget):
    def __init__(self):
        super().__init__()
        self.theme = get_theme_manager() if THEME_AVAILABLE else None
        self.settings = QSettings("MacanAngkasa", "MacanClock")
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(290, 110)

        self.old_pos = None
        self.setup_ui()
        self.load_settings()

        # Timer untuk update waktu setiap detik
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()

    def setup_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Apply theme to container
        self.apply_theme()

        # Label Jam
        self.lbl_time = QLabel()
        self.lbl_time.setAlignment(Qt.AlignCenter)
        
        # Label Tanggal
        self.lbl_date = QLabel()
        self.lbl_date.setAlignment(Qt.AlignCenter)
        
        # Apply text styles
        self.apply_text_styles()

        self.layout.addWidget(self.lbl_time)
        self.layout.addWidget(self.lbl_date)
        self.setLayout(self.layout)

    def apply_theme(self):
        """Apply theme to widget background"""
        if self.theme:
            c = self.theme.get_colors()
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: {c['bg_container']};
                    border-radius: 15px;
                    border: 1px solid {c['border_main']};
                }}
            """)
        else:
            self.setStyleSheet("""
                QWidget {
                    background-color: rgba(0, 0, 0, 180);
                    border-radius: 15px;
                    border: 1px solid #666;
                }
            """)

    def apply_text_styles(self):
        """Apply theme to text labels"""
        if self.theme:
            c = self.theme.get_colors()
            self.lbl_time.setStyleSheet(f"""
                color: {c['text_primary']}; 
                font-weight: bold; 
                font-size: 60px; 
                background: transparent; 
                border: none;
                margin-bottom: -10px;
            """)
            self.lbl_date.setStyleSheet(f"""
                color: {c['text_muted']}; 
                font-weight: normal; 
                font-size: 20px; 
                background: transparent; 
                border: none;
                padding-bottom: 10px;
            """)
        else:
            self.lbl_time.setStyleSheet("""
                color: #ffffff; 
                font-weight: bold; 
                font-size: 60px; 
                background: transparent; 
                border: none;
                margin-bottom: -10px;
            """)
            self.lbl_date.setStyleSheet("""
                color: #ccc; 
                font-weight: normal; 
                font-size: 20px; 
                background: transparent; 
                border: none;
                padding-bottom: 10px;
            """)

    def update_time(self):
        current_time = QTime.currentTime().toString("HH:mm")
        current_date = QDate.currentDate().toString("dddd, dd MMMM yyyy")
        
        self.lbl_time.setText(current_time)
        self.lbl_date.setText(current_date)

    # --- DRAG LOGIC ---
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

    # --- SETTINGS ---
    def load_settings(self):
        pos = self.settings.value("pos", QPoint(200, 100))
        self.move(pos)

    def save_settings(self):
        self.settings.setValue("pos", self.pos())

    def closeEvent(self, event):
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    clk = MacanClock()
    clk.show()
    sys.exit(app.exec())