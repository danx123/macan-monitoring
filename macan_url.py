import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLineEdit, QPushButton, QFrame, QMessageBox, QSizeGrip)
from PySide6.QtCore import Qt, QPoint, QSettings, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QIcon, QAction

try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

class MacanURL(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = get_theme_manager() if THEME_AVAILABLE else None
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.settings = QSettings("MacanAngkasa", "MacanURL")
        self.old_pos = None

        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        # Container Utama
        self.container = QFrame()
        self.container.setObjectName("MainFrame")
        self.apply_theme()
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

        # Layout Isi
        content_layout = QHBoxLayout(self.container)
        content_layout.setContentsMargins(10, 8, 20, 8)
        content_layout.setSpacing(8)

        # Search Icon
        self.lbl_icon = QPushButton("🔍")
        self.lbl_icon.setCursor(Qt.PointingHandCursor)
        self.lbl_icon.setFixedWidth(20)
        self.lbl_icon.clicked.connect(self.process_input)
        
        # Input Field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type URL or Search Google...")
        self.input_field.returnPressed.connect(self.process_input)
        self.apply_input_style()

        # Go Button
        self.btn_go = QPushButton("➜")
        self.btn_go.setCursor(Qt.PointingHandCursor)
        self.btn_go.setFixedWidth(20)
        self.btn_go.clicked.connect(self.process_input)

        # Close Button
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("BtnClose")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setFixedWidth(20)
        self.btn_close.clicked.connect(self.hide_widget)

        self.apply_button_styles()

        content_layout.addWidget(self.lbl_icon)
        content_layout.addWidget(self.input_field)
        content_layout.addWidget(self.btn_go)
        content_layout.addWidget(self.btn_close)

        # SizeGrip
        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setVisible(True)

        self.resize(350, 50)

    def apply_theme(self):
        """Apply theme to container"""
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

    def apply_input_style(self):
        """Apply theme to input field"""
        if self.theme:
            self.input_field.setStyleSheet(self.theme.get_input_style())
        else:
            self.input_field.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(0, 0, 0, 50);
                    border: 1px solid #444;
                    border-radius: 6px;
                    color: #e0e0e0;
                    padding: 4px 8px;
                    font-size: 12px;
                }
                QLineEdit:focus {
                    border: 1px solid #ff9800;
                }
            """)

    def apply_button_styles(self):
        """Apply theme to buttons"""
        if self.theme:
            c = self.theme.get_colors()
            base_style = f"""
                QPushButton {{
                    background-color: transparent;
                    color: {c['text_muted']};
                    border: none;
                    font-weight: bold;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    color: {c['accent_orange']};
                }}
            """
            close_style = f"""
                QPushButton#BtnClose {{
                    background-color: transparent;
                    color: {c['text_muted']};
                    border: none;
                    font-weight: bold;
                    font-size: 14px;
                }}
                QPushButton#BtnClose:hover {{
                    color: {c['accent_red']};
                }}
            """
            self.lbl_icon.setStyleSheet(base_style)
            self.btn_go.setStyleSheet(base_style)
            self.btn_close.setStyleSheet(close_style)
        else:
            base_style = """
                QPushButton {
                    background-color: transparent;
                    color: #aaa;
                    border: none;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    color: #ff9800;
                }
            """
            self.lbl_icon.setStyleSheet(base_style)
            self.btn_go.setStyleSheet(base_style)
            self.btn_close.setStyleSheet("""
                QPushButton#BtnClose {
                    background-color: transparent;
                    color: #aaa;
                    border: none;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton#BtnClose:hover {
                    color: #ff5555;
                }
            """)

    def resizeEvent(self, event):
        rect = self.rect()
        self.sizegrip.move(rect.right() - self.sizegrip.width(), 
                           rect.bottom() - self.sizegrip.height())
        super().resizeEvent(event)

    def process_input(self):
        text = self.input_field.text().strip()
        if not text:
            return

        url = ""
        if "." in text and " " not in text:
            if not text.startswith("http://") and not text.startswith("https://"):
                url = "https://" + text
            else:
                url = text
        else:
            query = text.replace(" ", "+")
            url = f"https://www.google.com/search?q={query}"

        QDesktopServices.openUrl(QUrl(url))
        self.input_field.clear()

    def hide_widget(self):
        self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not self.sizegrip.geometry().contains(event.position().toPoint()):
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
        pos = self.settings.value("pos", QPoint(200, 200))
        size = self.settings.value("size", QSize(350, 50))
        self.move(pos)
        self.resize(size)

    def save_settings(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("size", self.size())

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MacanURL()
    window.show()
    sys.exit(app.exec())