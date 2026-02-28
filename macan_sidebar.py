import sys
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QApplication, 
                               QMenu, QFrame, QFileIconProvider, QGraphicsDropShadowEffect)
from PySide6.QtCore import (Qt, QSize, QPoint, QSettings, QFileInfo, QUrl, 
                            QEasingCurve, QVariantAnimation, QMimeData)
from PySide6.QtGui import (QDragEnterEvent, QDropEvent, QAction, QDesktopServices, 
                           QColor, QDrag, QPixmap, QPainter)

# --- IMPORT THEME MANAGER ---
try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False
    print("Warning: macan_theme.py not found. Using default dark theme.")

# --- CUSTOM BUTTON DENGAN ANIMASI ELASTIS & DRAG REORDER ---
class SidebarIcon(QPushButton):
    def __init__(self, app_path, theme_manager=None, parent=None):
        super().__init__(parent)
        self.app_path = app_path
        self.theme = theme_manager
        
        # --- KONFIGURASI UKURAN ---
        self.default_size = 45    # Ukuran diam
        self.hover_size = 75      # Ukuran saat hover
        self.click_size = 40      # Efek tekan
        
        # Setup Tampilan Awal
        self.setFixedSize(self.default_size, self.default_size)
        self.setIconSize(QSize(32, 32))
        self.setCursor(Qt.PointingHandCursor)
        
        # --- SHADOW (Bayangan Ikon) ---
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setOffset(2, 0)  # Shadow ke kanan untuk sidebar kiri
        self.setGraphicsEffect(self.shadow)

        # Apply Theme Styles
        self.apply_theme_style()

        # --- LOAD ICON ---
        file_info = QFileInfo(app_path)
        icon_provider = QFileIconProvider()
        self.base_icon = icon_provider.icon(file_info)
        self.setIcon(self.base_icon)
        self.setToolTip(file_info.fileName())
        
        # --- ANIMASI ---
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(200) 
        self.anim.setEasingCurve(QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self.update_geometry_anim)
        
        # --- DRAG UNTUK REORDER ---
        self.drag_start_pos = None
        self.is_dragging = False

    def apply_theme_style(self):
        """Menerapkan style hover berdasarkan tema"""
        hover_bg = "rgba(255, 255, 255, 30)" # Default (Dark Mode)
        
        if self.theme and self.theme.get_theme() == "light":
            # Untuk Light Mode, hover agak gelap/abu
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

    # --- DRAG EVENTS UNTUK REORDER (SAMA SEPERTI DOCK) ---
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
        """Mulai drag operation (SAMA SEPERTI DOCK)"""
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Set data khusus untuk internal reordering
        mime_data.setText(f"REORDER:{self.app_path}")
        drag.setMimeData(mime_data)
        
        # Buat pixmap dari button
        pixmap = QPixmap(self.size())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        self.render(painter, QPoint(0, 0))
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(self.rect().center())
        
        # Kembalikan ukuran saat drag
        self.anim.stop()
        self.setFixedSize(self.default_size, self.default_size)
        
        drag.exec(Qt.MoveAction)

# --- MAIN SIDEBAR DENGAN REORDER SUPPORT ---
class MacanSidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MacanAngkasa", "MacanSidebar")
        self.app_list = [] 
        
        # Inisialisasi Theme Manager
        self.theme = get_theme_manager() if THEME_AVAILABLE else None

        # Window Flags - Tanpa Always On Top
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
        self.container.setObjectName("SidebarContainer")
        
        # Terapkan Tema
        self.apply_theme()
        
        # Layout Vertikal untuk Sidebar
        self.layout_icons = QVBoxLayout(self.container)
        
        # Margin: (Kiri, Atas, Kanan, Bawah)
        self.layout_icons.setContentsMargins(3, 12, 3, 12) 
        self.layout_icons.setSpacing(8)
        
        # AlignLeft: Agar saat membesar, tumbuh ke kanan
        self.layout_icons.setAlignment(Qt.AlignLeft) 

        # Layout Utama Window
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0) 
        main_layout.addWidget(self.container)
        main_layout.setAlignment(Qt.AlignLeft)

        self.refresh_sidebar_icons()

    def apply_theme(self):
        """Mengambil style dari theme manager"""
        if self.theme:
            # Gunakan style container global
            self.container.setStyleSheet(self.theme.get_container_style())
        else:
            # Fallback jika theme tidak ada
            self.container.setStyleSheet("""
                QFrame#SidebarContainer {
                    background-color: rgba(20, 20, 20, 200);
                    border: 1px solid rgba(255, 255, 255, 20);
                    border-radius: 20px;
                }
            """)
        
        # Refresh icon styles jika list sudah ada
        if hasattr(self, 'layout_icons'):
            for i in range(self.layout_icons.count()):
                widget = self.layout_icons.itemAt(i).widget()
                if isinstance(widget, SidebarIcon):
                    widget.apply_theme_style()

    def refresh_sidebar_icons(self):
        while self.layout_icons.count():
            item = self.layout_icons.takeAt(0)
            widget = item.widget()
            if widget: widget.deleteLater()

        if not self.app_list:
            lbl = QPushButton("Drop\nApps")
            # Sesuaikan warna teks placeholder dengan tema
            text_color = "#888"
            if self.theme and self.theme.get_theme() == "light":
                text_color = "#555"
                
            lbl.setStyleSheet(f"color: {text_color}; border: none; font-style: italic; margin: 5px;")
            lbl.setEnabled(False)
            lbl.setFixedSize(45, 60)
            self.layout_icons.addWidget(lbl)
        
        for app_path in self.app_list:
            # Pass self.theme ke icon agar hover color sesuai
            btn = SidebarIcon(app_path, theme_manager=self.theme)
            btn.clicked.connect(lambda _, x=app_path: self.launch_app(x))
            btn.setContextMenuPolicy(Qt.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, b=btn, x=app_path: self.show_context_menu(pos, b, x))
            self.layout_icons.addWidget(btn)
        
        # Paksa resize window
        self.container.adjustSize()
        self.adjustSize()

    def launch_app(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def show_context_menu(self, pos, target_btn, app_path):
        menu = QMenu(self)
        
        # Terapkan Tema Menu
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

    # --- DRAG & DROP DENGAN REORDER (SAMA SEPERTI DOCK) ---
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
            self.refresh_sidebar_icons()
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
        self.refresh_sidebar_icons()

    def get_drop_index(self, pos):
        """Hitung index target berdasarkan posisi drop - FIXED UNTUK VERTICAL LAYOUT"""
        # Cari widget terdekat berdasarkan koordinat Y (bukan X seperti di dock)
        for i in range(len(self.app_list)):
            widget = self.layout_icons.itemAt(i).widget()
            if widget and isinstance(widget, SidebarIcon):
                widget_center = widget.geometry().center()
                # KUNCI PERBAIKAN: Gunakan pos.y() untuk vertical layout, bukan pos.x()
                if pos.y() < widget_center.y():
                    return i
        
        # Default: taruh di akhir
        return len(self.app_list)

    # --- WINDOW MOVING ---
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
        pos = self.settings.value("pos", QPoint(10, 200))
        self.move(pos)
        self.app_list = self.settings.value("apps", [])
        if not isinstance(self.app_list, list): self.app_list = []
        self.refresh_sidebar_icons()

    def save_settings(self):
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("apps", self.app_list)

    def closeEvent(self, event):
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    sidebar = MacanSidebar()
    sidebar.show()
    sys.exit(app.exec())