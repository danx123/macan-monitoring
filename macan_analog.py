import sys
from PySide6.QtWidgets import QWidget, QApplication, QMenu
from PySide6.QtCore import Qt, QTimer, QTime, QDate, QPoint, QSettings 
from PySide6.QtGui import QPainter, QColor, QPen, QPolygon, QBrush, QAction, QFont

try:
    from macan_theme import get_theme_manager
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

class MacanAnalog(QWidget):
    def __init__(self):
        super().__init__()
        self.theme = get_theme_manager() if THEME_AVAILABLE else None
        
        self.settings = QSettings("MacanAngkasa", "MacanAnalog")
        
        # Setup Window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(200, 200)

        self.old_pos = None
        
        # Timer untuk update jarum detik
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)

        self.load_settings()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Hitung titik tengah
        side = min(self.width(), self.height())
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(side / 200.0, side / 200.0)

        # --- WARNA TEMA ---
        if self.theme:
            c = self.theme.get_colors()
            is_dark = self.theme.get_theme() == "dark"
            
            bg_color = QColor(20, 20, 20, 200) if is_dark else QColor(245, 245, 245, 230)
            tick_color = QColor(200, 200, 200) if is_dark else QColor(100, 100, 100)
            
            hour_color = c['accent_orange']
            minute_color = c['text_primary']
            second_color = c['accent_red']
            
            # Warna untuk Tanggal
            date_bg_color = QColor(255, 255, 255, 20) if is_dark else QColor(0, 0, 0, 10)
            text_color = c['text_secondary']
            
        else:
            bg_color = QColor(30, 30, 30, 200)
            tick_color = QColor(200, 200, 200)
            hour_color = "#ff9800"
            minute_color = "#ffffff"
            second_color = "#ff5555"
            date_bg_color = QColor(255, 255, 255, 30)
            text_color = "#e0e0e0"

        # --- 1. GAMBAR MUKA JAM (Background) ---
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawEllipse(-90, -90, 180, 180)

        # --- 2. GAMBAR TICK MARK (Garis Jam) ---
        painter.setPen(QPen(tick_color, 2))
        for i in range(12):
            # Jangan gambar garis di posisi jam 3 (index 3) biar tidak menabrak kotak tanggal
            if i != 3: 
                painter.drawLine(0, -80, 0, -90)
            painter.rotate(30)
        
        # Reset rotasi painter manual karena loop di atas berputar 360 derajat
        # Posisi painter sekarang sudah kembali ke 0 (normal)

        # --- 3. FITUR TANGGAL & HARI (DIPERBAIKI) ---
        curr_date = QDate.currentDate()
        
        # PERBAIKAN DI SINI: gunakan "ddd" bukan "DDD"
        # "ddd" = Wed, "dddd" = Wednesday, "DDD" = Salah/Day of Year
        day_name = curr_date.toString("ddd").upper() 
        day_num = curr_date.toString("dd")           

        # A. Label Hari (Di atas tengah, bawah angka 12)
        font_day = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font_day)
        painter.setPen(QPen(QColor(text_color)))
        # Koordinat (x, y, w, h)
        painter.drawText(-20, -55, 40, 20, Qt.AlignCenter, day_name)

        # B. Kotak Tanggal (Di posisi jam 3 / Kanan)
        # Background Kotak
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(date_bg_color))
        # Gambar kotak di posisi kanan (x=50)
        painter.drawRoundedRect(50, -12, 28, 24, 4, 4)

        # Teks Anggal
        painter.setPen(QPen(QColor(text_color)))
        font_date = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font_date)
        painter.drawText(50, -12, 28, 24, Qt.AlignCenter, day_num)

        # --- 4. LOGIKA JARUM JAM ---
        time = QTime.currentTime()

        # Jarum Jam
        painter.save()
        painter.rotate(30.0 * ((time.hour() + time.minute() / 60.0)))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(hour_color) if isinstance(hour_color, str) else hour_color)
        painter.drawPolygon(QPolygon([QPoint(-3, 0), QPoint(0, -50), QPoint(3, 0), QPoint(0, 5)]))
        painter.restore()

        # Jarum Menit
        painter.save()
        painter.rotate(6.0 * (time.minute() + time.second() / 60.0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(minute_color) if isinstance(minute_color, str) else minute_color)
        painter.drawPolygon(QPolygon([QPoint(-2, 0), QPoint(0, -70), QPoint(2, 0), QPoint(0, 5)]))
        painter.restore()

        # Jarum Detik
        painter.save()
        painter.rotate(6.0 * time.second())
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(second_color) if isinstance(second_color, str) else second_color)
        painter.drawPolygon(QPolygon([QPoint(-1, 0), QPoint(0, -80), QPoint(1, 0), QPoint(0, 10)]))
        painter.restore()

        # Titik Tengah
        painter.setBrush(QColor(minute_color) if isinstance(minute_color, str) else minute_color)
        painter.drawEllipse(-3, -3, 6, 6)

    def apply_theme(self):
        """Refresh theme colors"""
        self.update()

    # --- DRAG LOGIC ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPosition().toPoint()
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event)

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        self.save_settings()

    def show_context_menu(self, event):
        menu = QMenu(self)
        if self.theme:
            menu.setStyleSheet(self.theme.get_menu_style())
        else:
            menu.setStyleSheet("QMenu { background: #333; color: #fff; border: 1px solid #555; }")
        
        action_reset = QAction("Reset Position", self)
        action_reset.triggered.connect(lambda: self.move(100, 100))
        menu.addAction(action_reset)
        menu.exec(event.globalPos())

    # --- SETTINGS ---
    def load_settings(self):
        pos = self.settings.value("pos", QPoint(50, 50))
        self.move(pos)

    def save_settings(self):
        self.settings.setValue("pos", self.pos())

    def closeEvent(self, event):
        if hasattr(self, 'timer') and self.timer.isActive():
            self.timer.stop()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    clock = MacanAnalog()
    clock.show()
    sys.exit(app.exec())