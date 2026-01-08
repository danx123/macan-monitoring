# 🐯 Macan Monitoring

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green)

**Macan Monitoring** is a lightweight, elegant, and semi-transparent desktop widget built with **Python (PySide6)**. It provides real-time monitoring of your system's vital statistics—CPU, RAM, Swap, and Network speeds—packaged in a sleek, dark-themed UI.

Designed to be unobtrusive yet informative, it features a frameless design that blends perfectly into your desktop environment.

---

## ✨ Key Features

* **📊 Real-Time Monitoring**: Instantly view CPU load, RAM usage, and Swap memory with visual progress bars.
* **⚡ Network Stats**: Monitor real-time Download and Upload speeds (auto-scaling units: B/s, KB/s, MB/s).
* **🎨 Modern UI/UX**:
    * **Dark Theme**: Easy on the eyes with a professional color palette.
    * **Glass Effect**: 50% semi-transparent background.
    * **Frameless Design**: Rounded corners with a custom title bar.
* **🎛️ User Controls**:
    * **Draggable**: Click and drag anywhere to move the widget.
    * **Always on Top**: Toggle via the settings menu to keep stats visible over other apps.
    * **Run on Startup**: (Windows Only) Automatically launch the widget when your computer starts.
* 🌏Public Ip Address
* Power Indicator
* Internal TaskManager

---

## 📸 Screenshots
<img width="1365" height="767" alt="Cuplikan layar 2026-01-02 135325" src="https://github.com/user-attachments/assets/2a93a11b-77b2-4af0-b4b4-baee5d5d36b0" />


## Changelog:
- fixed tooltip sidebar & dock


> *The widget running in the corner of a desktop with transparency enabled.*

---

## 🛠️ Installation

### Prerequisites
Ensure you have Python 3.x installed on your system.

### 1. Clone the Repository
```bash
git clone [https://github.com/danx123/macan-monitoring.git](https://github.com/danx123/macan-monitoring.git)
cd macan-monitoring

2. Install Dependencies
Install the required libraries (PySide6 for the GUI and psutil for system fetching) using pip:
Bash
pip install -r requirements.txt

Note: If you don't have a requirements.txt, simply run:
Bash
pip install PySide6 psutil


🚀 Usage
Run the main script to start the widget:
Bash
python main.py

Controls
Move: Click and hold the widget background to drag it around your screen.
Settings (⚙️): Click the gear icon next to the close button to:
Toggle "Always on Top".
Enable/Disable "Run on Startup" (Windows).
Close (✕): Click the "X" button to terminate the application.

📦 Building an Executable (Optional)
If you want to create a standalone .exe file so you don't need to run Python every time, use PyInstaller:
Install PyInstaller:
Bash
pip install pyinstaller

Build the project (noconsole removes the black terminal window):
Bash
pyinstaller --noconsole --onefile --name="MacanMonitoring" main.py

Find your executable in the dist/ folder.

🤝 Contributing
Contributions are welcome! If you have suggestions for new features (e.g., GPU monitoring, skin support), feel free to open an issue or submit a pull request.
Fork the Project
Create your Feature Branch (git checkout -b feature/AmazingFeature)
Commit your Changes (git commit -m 'Add some AmazingFeature')
Push to the Branch (git push origin feature/AmazingFeature)
Open a Pull Request

📝 License
Distributed under the MIT License. See LICENSE for more information.


Made with ❤️ using Python & PySide6


-----

