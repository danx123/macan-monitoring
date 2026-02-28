"""
Macan Theme Manager - Global Theme System untuk Macan Monitoring Suite
File: macan_theme.py
"""

from PySide6.QtCore import QSettings, QObject, Signal

class MacanTheme(QObject):
    """
    Centralized Theme Manager dengan dukungan Signal untuk update realtime.
    Inherits QObject untuk menggunakan Signal.
    """
    themeChanged = Signal(str) # Signal memancarkan tema baru ('dark'/'light')
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MacanAngkasa", "MacanTheme")
        self.current_theme = self.settings.value("theme", "dark")
    
    def get_theme(self):
        """Get current theme: 'dark' or 'light'"""
        return self.current_theme
    
    def set_theme(self, theme):
        """Set theme: 'dark' or 'light' and emit signal"""
        if theme in ["dark", "light"]:
            self.current_theme = theme
            self.settings.setValue("theme", theme)
            self.themeChanged.emit(theme) # Emit signal perubahan
            return True
        return False
    
    def toggle_theme(self):
        """Toggle between dark and light theme"""
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.set_theme(new_theme)
        return new_theme

    # ==========================================
    # THEME COLORS - DARK MODE (Opacity ~50%)
    # ==========================================
    
    @staticmethod
    def get_dark_colors():
        return {
            # Background - Alpha 130 is approx 51% Opacity
            "bg_main": "rgba(20, 20, 20, 130)",
            "bg_container": "rgba(20, 20, 20, 130)",
            "bg_input": "rgba(0, 0, 0, 80)",
            "bg_button": "rgba(75, 79, 82, 180)",
            "bg_button_hover": "rgba(100, 100, 100, 200)",
            "bg_header": "rgba(64, 64, 64, 150)",
            "bg_secondary": "rgba(51, 51, 51, 150)",
            
            # Border
            "border_main": "rgba(85, 85, 85, 150)",
            "border_light": "rgba(255, 255, 255, 30)",
            "border_input": "#444",
            "border_focus": "#ff9800",
            
            # Text
            "text_primary": "#f0f0f0",
            "text_secondary": "#e0e0e0",
            "text_muted": "#ccc", # Lebih terang sedikit agar terbaca di background 50%
            "text_dark": "#ddd",
            
            # Accent Colors
            "accent_orange": "#ff9800",
            "accent_blue": "#00bcd4",
            "accent_green": "#8bc34a",
            "accent_red": "#ff5555",
            "accent_yellow": "#ffc107",
            "accent_cyan": "#00ffcc",
            "accent_pink": "#E91E63",
            
            # Status Colors
            "cpu_color": "#00bcd4",
            "ram_color": "#8bc34a",
            "swap_color": "#ffc107",
            "download_color": "#2196f3",
            "upload_color": "#ff9800",
            
            # Progress Bar
            "progress_bg": "rgba(255, 255, 255, 30)",
            "progress_chunk": "#00bcd4",
            
            # Grid & Lines
            "grid_color": "rgba(68, 68, 68, 150)",
            "separator_color": "rgba(100, 100, 100, 150)",
        }
    
    # ==========================================
    # THEME COLORS - LIGHT MODE
    # ==========================================
    
    @staticmethod
    def get_light_colors():
        return {
            # Background
            "bg_main": "rgba(245, 245, 245, 220)",
            "bg_container": "rgba(255, 255, 255, 200)",
            "bg_input": "rgba(255, 255, 255, 200)",
            "bg_button": "#e0e0e0",
            "bg_button_hover": "#d0d0d0",
            "bg_header": "#f5f5f5",
            "bg_secondary": "#fafafa",
            
            # Border
            "border_main": "#ccc",
            "border_light": "rgba(0, 0, 0, 10)",
            "border_input": "#ddd",
            "border_focus": "#ff6f00",
            
            # Text
            "text_primary": "#212121",
            "text_secondary": "#424242",
            "text_muted": "#757575",
            "text_dark": "#616161",
            
            # Accent Colors
            "accent_orange": "#f57c00",
            "accent_blue": "#0097a7",
            "accent_green": "#689f38",
            "accent_red": "#d32f2f",
            "accent_yellow": "#ffa000",
            "accent_cyan": "#00acc1",
            "accent_pink": "#c2185b",
            
            # Status Colors
            "cpu_color": "#0097a7",
            "ram_color": "#689f38",
            "swap_color": "#ffa000",
            "download_color": "#1976d2",
            "upload_color": "#f57c00",
            
            # Progress Bar
            "progress_bg": "#e0e0e0",
            "progress_chunk": "#0097a7",
            
            # Grid & Lines
            "grid_color": "#e0e0e0",
            "separator_color": "#ddd",
        }
    
    def get_colors(self):
        """Get colors based on current theme"""
        if self.current_theme == "dark":
            return self.get_dark_colors()
        else:
            return self.get_light_colors()
    
    # ==========================================
    # STYLESHEET GENERATORS
    # ==========================================
    
    def get_main_window_style(self):
        c = self.get_colors()
        return f"""
            QFrame#MainFrame {{
                background-color: {c['bg_main']}; 
                border: 1px solid {c['border_main']};
                border-radius: 12px;
            }}
            QLabel {{
                color: {c['text_secondary']};
            }}
            QPushButton {{
                background-color: transparent;
                color: {c['text_muted']};
                border: none;
            }}
            QPushButton:hover {{
                color: {c['accent_orange']};
            }}
            QProgressBar {{
                border: none;
                background-color: {c['progress_bg']};
                border-radius: 3px;
            }}
        """
    
    def get_container_style(self):
        c = self.get_colors()
        return f"""
            QFrame#DockContainer, QFrame#SidebarContainer {{
                background-color: {c['bg_container']};
                border: 1px solid {c['border_light']};
                border-radius: 20px;
            }}
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 10px;
            }}
            QPushButton:hover {{
                background-color: rgba(128, 128, 128, 50);
            }}
        """
    
    def get_input_style(self):
        c = self.get_colors()
        return f"""
            QLineEdit {{
                background-color: {c['bg_input']};
                border: 1px solid {c['border_input']};
                border-radius: 6px;
                color: {c['text_secondary']};
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {c['border_focus']};
            }}
            QTextEdit {{
                background-color: transparent;
                color: {c['text_primary']};
                selection-background-color: {c['accent_orange']};
            }}
        """
    
    def get_menu_style(self):
        bg = "#222" if self.current_theme == "dark" else "#fff"
        border = "rgba(255,255,255,30)" if self.current_theme == "dark" else "#ccc"
        text = "white" if self.current_theme == "dark" else "#212121"
        hover = "#444" if self.current_theme == "dark" else "#e0e0e0"
        
        return f"""
            QMenu {{
                background-color: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 5px;
            }}
            QMenu::item {{
                padding: 5px 25px 5px 20px;
            }}
            QMenu::item:selected {{
                background-color: {hover};
            }}
            QMenu::separator {{
                background-color: {border};
                height: 1px;
                margin: 4px 0px;
            }}
        """
    
    def get_table_style(self):
        if self.current_theme == "dark":
            return """
                QTableWidget { 
                    background-color: rgba(30, 30, 30, 150); 
                    color: #ffffff; 
                    gridline-color: rgba(68, 68, 68, 100);
                    border: none;
                    selection-background-color: #0078d7;
                    selection-color: white;
                }
                QHeaderView::section {
                    background-color: rgba(64, 64, 64, 200);
                    color: #cccccc;
                    padding: 6px;
                    border: none;
                    border-right: 1px solid #555;
                    font-weight: bold;
                }
                QTableWidget::item:hover {
                    background-color: rgba(255, 255, 255, 20);
                }
            """
        else:
            return """
                QTableWidget { 
                    background-color: #ffffff; 
                    color: #212121; 
                    gridline-color: #e0e0e0;
                    border: none;
                    selection-background-color: #2196f3;
                    selection-color: white;
                }
                QHeaderView::section {
                    background-color: #f5f5f5;
                    color: #424242;
                    padding: 6px;
                    border: none;
                    border-right: 1px solid #ddd;
                    font-weight: bold;
                }
            """
    
    def get_button_style(self):
        c = self.get_colors()
        return f"""
            QPushButton {{
                background-color: {c['bg_button']};
                color: {c['text_primary']};
                border: 1px solid {c['border_main']};
                padding: 6px 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {c['bg_button_hover']};
            }}
            QPushButton#killBtn {{
                background-color: {c['accent_red']};
                border: 1px solid {c['accent_red']};
                color: white;
            }}
            QPushButton#killBtn:hover {{
                background-color: #d32f2f;
            }}
            QPushButton#newTaskBtn {{
                background-color: {c['accent_green']};
                border: 1px solid {c['accent_green']};
                color: white;
            }}
            QPushButton#newTaskBtn:hover {{
                background-color: #388E3C;
            }}
        """

# Global Theme Instance
_theme_instance = None

def get_theme_manager():
    """Get global theme manager instance (Singleton)"""
    global _theme_instance
    if _theme_instance is None:
        _theme_instance = MacanTheme()
    return _theme_instance