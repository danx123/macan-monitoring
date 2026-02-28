import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, QLabel, 
                               QApplication, QFrame, QHBoxLayout, QPushButton)
from PySide6.QtCore import Qt, QPoint, QSettings, QSize
from PySide6.QtGui import QColor, QFont

try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

class MacanMemo(QWidget):
    def __init__(self):
        super().__init__()
        self.theme = get_theme_manager() if THEME_AVAILABLE else None
        self.settings = QSettings("MacanAngkasa", "MacanMemo")
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.old_pos = None
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        # Container Utama
        self.container = QFrame()
        self.apply_theme()

        layout_main = QVBoxLayout(self)
        layout_main.setContentsMargins(0, 0, 0, 0)
        layout_main.addWidget(self.container)

        layout_inner = QVBoxLayout(self.container)
        layout_inner.setContentsMargins(5, 5, 5, 5)
        layout_inner.setSpacing(0)

        # Header
        self.header = QLabel("MEMO")
        self.header.setAlignment(Qt.AlignCenter)
        self.apply_header_style()
        self.header.setFixedHeight(20)
        layout_inner.addWidget(self.header)

        # Text Area
        self.text_edit = QTextEdit()
        self.text_edit.setFrameStyle(QFrame.NoFrame)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setPlaceholderText("Write note here...")
        self.apply_text_edit_style()
        
        self.text_edit.textChanged.connect(self.save_content)
        
        layout_inner.addWidget(self.text_edit)
        self.resize(200, 250)

    def apply_theme(self):
        """Apply theme to container"""
        if self.theme:
            c = self.theme.get_colors()
            self.container.setStyleSheet(f"""
                QFrame {{
                    background-color: {c['bg_secondary']};
                    border: 1px solid {c['border_main']};
                    border-radius: 5px;
                }}
            """)
        else:
            self.container.setStyleSheet("""
                QFrame {
                    background-color: #333333;
                    border: 1px solid #555;
                    border-radius: 5px;
                }
            """)

    def apply_header_style(self):
        """Apply theme to header"""
        if self.theme:
            c = self.theme.get_colors()
            self.header.setStyleSheet(f"""
                background-color: {c['bg_header']}; 
                color: {c['text_muted']}; 
                font-weight: bold; 
                font-size: 10px;
                border-radius: 3px;
                padding: 2px;
            """)
        else:
            self.header.setStyleSheet("""
                background-color: #444; 
                color: #aaa; 
                font-weight: bold; 
                font-size: 10px;
                border-radius: 3px;
                padding: 2px;
            """)

    def apply_text_edit_style(self):
        """Apply theme to text edit"""
        if self.theme:
            c = self.theme.get_colors()
            self.text_edit.setStyleSheet(f"""
                QTextEdit {{
                    background-color: transparent;
                    color: {c['text_primary']};
                    selection-background-color: {c['accent_orange']};
                }}
            """)
        else:
            self.text_edit.setStyleSheet("""
                QTextEdit {
                    background-color: transparent;
                    color: #f0f0f0;
                    selection-background-color: #ff9800;
                }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.position().toPoint())
            if child == self.header or child == self.container:
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
        pos = self.settings.value("pos", QPoint(300, 300))
        size = self.settings.value("size", QSize(200, 250))
        content = self.settings.value("content", "")
        
        self.move(pos)
        self.resize(size)
        self.text_edit.setPlainText(content)

    def save_content(self):
        self.settings.setValue("content", self.text_edit.toPlainText())

    def save_settings(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("size", self.size())
        self.save_content()

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    memo = MacanMemo()
    memo.show()
    sys.exit(app.exec())