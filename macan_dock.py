import sys
import os
import subprocess
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QApplication, 
                               QMenu, QFrame, QFileIconProvider, QGraphicsDropShadowEffect)
from PySide6.QtCore import (Qt, QSize, QPoint, QSettings, QFileInfo, QUrl, 
                            QEasingCurve, QVariantAnimation, QMimeData)
from PySide6.QtGui import (QDragEnterEvent, QDropEvent, QAction, QDesktopServices, 
                           QColor, QIcon, QDrag, QPixmap, QPainter)

# --- IMPORT THEME MANAGER ---
try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

# --- CUSTOM BUTTON DENGAN ANIMASI ELASTIS & DRAG REORDER ---
class DockIcon(QPushButton):
    def __init__(self, app_path, parent=None, is_system_shortcut=False, theme_manager=None):
        super().__init__(parent)
        self.app_path = app_path
        self.is_system_shortcut = is_system_shortcut
        self.theme = theme_manager
        
        self.default_size = 45
        self.hover_size = 75
        self.click_size = 40
        
        self.setFixedSize(self.default_size, self.default_size)
        self.setIconSize(QSize(32, 32))
        self.setCursor(Qt.PointingHandCursor)
        
        # Shadow
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setOffset(0, 2)
        self.setGraphicsEffect(self.shadow)

        self.apply_theme_style()

        # Load Icon
        if is_system_shortcut:
            self.setToolTip(app_path)
            if "explorer" in app_path.lower():
                self.setText("📁")
                self.setStyleSheet(self.styleSheet() + "QPushButton { font-size: 28px; }")
            elif "control" in app_path.lower():
                self.setText("⚙️")
                self.setStyleSheet(self.styleSheet() + "QPushButton { font-size: 28px; }")
            elif "recycle" in app_path.lower():
                self.setText("🗑️")
                self.setStyleSheet(self.styleSheet() + "QPushButton { font-size: 28px; }")
        else:
            file_info = QFileInfo(app_path)
            icon_provider = QFileIconProvider()
            self.base_icon = icon_provider.icon(file_info)
            self.setIcon(self.base_icon)
            self.setToolTip(file_info.fileName())
        
        # Animation
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self.update_geometry_anim)
        
        # --- DRAG UNTUK REORDER ---
        self.drag_start_pos = None
        self.is_dragging = False

    def apply_theme_style(self):
        """Apply theme to button"""
        hover_bg = "rgba(255, 255, 255, 30)" # Default Dark Mode
        
        if self.theme and self.theme.get_theme() == "light":
             hover_bg = "rgba(0, 0, 0, 10)"
        
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
        
        if not self.is_system_shortcut:
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

    # --- DRAG EVENTS UNTUK REORDER ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
            # PENTING: Jangan langsung accept, biarkan propagate ke parent untuk clicked signal
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if self.drag_start_pos is None:
            return
        
        # Cek apakah sudah cukup jauh untuk mulai drag
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
        
        # Hanya user apps yang bisa di-drag reorder
        if self.is_system_shortcut:
            return
            
        # Set flag dragging dan perform drag
        self.is_dragging = True
        event.accept()  # Accept di sini untuk stop propagation
        self.perform_drag()

    def mouseReleaseEvent(self, event):
        # Jika sedang dragging, jangan emit clicked signal
        was_dragging = self.is_dragging
        self.drag_start_pos = None
        self.is_dragging = False
        
        if not was_dragging:
            super().mouseReleaseEvent(event)
        else:
            # Reset state tanpa emit signal
            event.accept()

    def perform_drag(self):
        """Mulai drag operation"""
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Set data khusus untuk internal reordering
        mime_data.setText(f"REORDER:{self.app_path}")
        drag.setMimeData(mime_data)
        
        # Buat pixmap dari button
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        # Fix: tambahkan targetOffset parameter
        self.render(painter, QPoint(0, 0))
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(self.rect().center())
        
        # Kembalikan ukuran saat drag
        self.anim.stop()
        self.setFixedSize(self.default_size, self.default_size)
        
        drag.exec(Qt.MoveAction)

# --- MAIN DOCK DENGAN REORDER SUPPORT ---
class MacanDock(QWidget):
    def __init__(self):
        super().__init__()
        self.theme = get_theme_manager() if THEME_AVAILABLE else None
        self.settings = QSettings("MacanAngkasa", "MacanDock")
        self.app_list = []
        
        self.system_shortcuts = [
            ("Windows Explorer", "explorer"),
            ("Control Panel", "control"),
            ("Recycle Bin", "shell:RecycleBinFolder")
        ]

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_AlwaysShowToolTips, True)
        self.setAcceptDrops(True)

        self.old_pos = None
        self.drag_over_index = -1  # Track posisi hover saat drag
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        self.container = QFrame(self)
        self.container.setObjectName("DockContainer")
        self.apply_theme()
        
        self.layout_icons = QHBoxLayout(self.container)
        self.layout_icons.setContentsMargins(12, 3, 12, 3)
        self.layout_icons.setSpacing(8)
        self.layout_icons.setAlignment(Qt.AlignBottom)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)
        main_layout.setAlignment(Qt.AlignBottom)

        self.refresh_dock_icons()

    def apply_theme(self):
        """Apply theme to container"""
        if self.theme:
            self.container.setStyleSheet(self.theme.get_container_style())
        else:
            self.container.setStyleSheet("""
                QFrame#DockContainer {
                    background-color: rgba(20, 20, 20, 200);
                    border: 1px solid rgba(255, 255, 255, 20);
                    border-radius: 20px;
                }
            """)

    def refresh_dock_icons(self):
        while self.layout_icons.count():
            item = self.layout_icons.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()

        # System shortcuts
        for name, command in self.system_shortcuts:
            btn = DockIcon(command, is_system_shortcut=True, theme_manager=self.theme)
            btn.clicked.connect(lambda _, cmd=command: self.launch_system_shortcut(cmd))
            self.layout_icons.addWidget(btn)
        
        # Separator
        if self.app_list:
            separator = QFrame()
            separator.setFrameShape(QFrame.VLine)
            
            sep_color = "rgba(255, 255, 255, 30)"
            if self.theme:
                if self.theme.get_theme() == "light":
                    sep_color = "rgba(0, 0, 0, 20)"
                
            separator.setStyleSheet(f"background-color: {sep_color}; width: 2px;")
            separator.setFixedHeight(40)
            self.layout_icons.addWidget(separator)
        
        # User apps
        if not self.app_list:
            lbl = QPushButton("Drop Apps")
            
            text_color = "#888"
            if self.theme:
                c = self.theme.get_colors()
                text_color = c['text_muted']
                
            lbl.setStyleSheet(f"color: {text_color}; border: none; font-style: italic; margin: 5px;")
            lbl.setEnabled(False)
            self.layout_icons.addWidget(lbl)
        else:
            for app_path in self.app_list:
                btn = DockIcon(app_path, theme_manager=self.theme)
                btn.clicked.connect(lambda _, x=app_path: self.launch_app(x))
                btn.setContextMenuPolicy(Qt.CustomContextMenu)
                btn.customContextMenuRequested.connect(lambda pos, b=btn, x=app_path: self.show_context_menu(pos, b, x))
                self.layout_icons.addWidget(btn)
        
        self.container.adjustSize()
        self.adjustSize()

    def launch_system_shortcut(self, command):
        try:
            if command == "explorer":
                subprocess.Popen(["explorer.exe"])
            elif command == "control":
                subprocess.Popen(["control.exe"])
            elif "shell:" in command:
                # Gunakan subprocess dengan shell=True agar tidak blocking
                subprocess.Popen(f'explorer "{command}"', shell=True)
        except Exception as e:
            print(f"Error launching {command}: {e}")

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
            self.refresh_dock_icons()

    # --- DRAG & DROP DENGAN REORDER ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        elif event.mimeData().hasText() and event.mimeData().text().startswith("REORDER:"):
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Track posisi mouse saat drag untuk highlight & terima file eksternal"""
        if event.mimeData().hasUrls():
            event.accept()
        elif event.mimeData().hasText() and event.mimeData().text().startswith("REORDER:"):
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        mime_data = event.mimeData()
        
        # Cek apakah ini reorder internal
        if mime_data.hasText() and mime_data.text().startswith("REORDER:"):
            app_path = mime_data.text().replace("REORDER:", "")
            self.reorder_app(app_path, event.position().toPoint())
            event.accept()
            return
        
        # Atau drop file baru dari luar
        if mime_data.hasUrls():
            files = [u.toLocalFile() for u in mime_data.urls()]
            for f in files:
                if os.path.exists(f) and f not in self.app_list:
                    self.app_list.append(f)
            self.save_settings()
            self.refresh_dock_icons()
            event.accept()

    def reorder_app(self, app_path, drop_pos):
        """Pindahkan posisi app di list"""
        if app_path not in self.app_list:
            return
        
        # Hapus dari posisi lama
        old_index = self.app_list.index(app_path)
        self.app_list.pop(old_index)
        
        # Cari posisi baru berdasarkan drop position
        new_index = self.get_drop_index(drop_pos)
        
        # Insert di posisi baru
        self.app_list.insert(new_index, app_path)
        
        self.save_settings()
        self.refresh_dock_icons()

    def get_drop_index(self, pos):
        """Hitung index target berdasarkan posisi drop"""
        # Hitung offset dari system shortcuts + separator
        system_count = len(self.system_shortcuts)
        separator_count = 1 if self.app_list else 0
        offset = system_count + separator_count
        
        # Cari widget terdekat
        for i in range(len(self.app_list)):
            widget = self.layout_icons.itemAt(i + offset).widget()
            if widget and isinstance(widget, DockIcon):
                widget_center = widget.geometry().center()
                if pos.x() < widget_center.x():
                    return i
        
        # Default: taruh di akhir
        return len(self.app_list)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Cek apakah klik di area kosong (bukan di icon)
            if self.childAt(event.pos()) == self.container or self.childAt(event.pos()) == self:
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
        pos = self.settings.value("pos", QPoint(100, 600))
        self.move(pos)
        self.app_list = self.settings.value("apps", [])
        if not isinstance(self.app_list, list): self.app_list = []
        self.refresh_dock_icons()

    def save_settings(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("apps", self.app_list)

    def closeEvent(self, event):
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dock = MacanDock()
    dock.show()
    sys.exit(app.exec())