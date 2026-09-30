"""Design tokens copied from the LANDAR HTML design (Tailwind config). Change colors here only."""
C = dict(
    bg="#0f131c", lowest="#0a0e17", low="#181b25", container="#1c1f29", high="#262a34", highest="#31353f",
    primary="#4cd7f6", primary_container="#06b6d4", on_primary_container="#00424f",
    secondary="#adc6ff", tertiary="#4edea3", error="#ffb4ab", error_container="#93000a", on_error="#690005",
    outline="#869397", outline_variant="#3d494c", on_surface="#dfe2ef", on_surface_variant="#bcc9cd", warn="#f5c451",
)
SANS, MONO = "Inter", "JetBrains Mono"
WARN_VALUES = {"Unknown"}
BAD_VALUES = {"Blocked", "Disabled", "Locked", "Suspended", "failure", "denied", "Expired", "Conflict", "Unreachable"}
GOOD_VALUES = {"Approved", "Active", "Online", "success", "Enabled", "In use", "Reachable", "Reserved"}

QSS = f"""
* {{ font-family: "{SANS}", "Segoe UI", sans-serif; font-size: 13px; color: {C['on_surface']}; outline: none; }}
QMainWindow, QDialog, #root, #content, QStackedWidget {{ background: {C['bg']}; }}
QLabel {{ background: transparent; }}
#sidebar, #topbar {{ background: {C['lowest']}; }}
#sideHead {{ background: {C['low']}; }}
#tenant {{ background: {C['container']}; border-radius: 4px; }}
#gateway {{ background: {C['lowest']}; border-radius: 2px; }}
#navItem {{ background: transparent; border: none; border-radius: 4px; text-align: left; padding: 6px 8px; color: {C['on_surface_variant']}; }}
#navItem:hover {{ background: {C['high']}; }}
#navItem:checked {{ background: {C['primary_container']}; }}
#navItem:checked * {{ color: {C['on_primary_container']}; }}
#search {{ background: {C['low']}; border: none; border-radius: 4px; padding: 6px 10px 6px 34px; font-size: 12px; }}
#search:focus {{ background: {C['container']}; }}
#chip {{ background: {C['low']}; border-radius: 4px; }}
#chipHigh {{ background: {C['high']}; border-radius: 2px; }}
#card {{ background: {C['low']}; border-radius: 4px; }}
#cardHead {{ border-bottom: 1px solid {C['outline_variant']}; }}
#row {{ background: {C['container']}; border-radius: 4px; }}
#kbd {{ background: {C['highest']}; border-radius: 3px; }}
QPushButton {{ background: {C['high']}; border: none; border-radius: 4px; padding: 6px 12px; font-size: 10px; font-weight: 700; }}
QPushButton:hover {{ background: {C['highest']}; }}
QPushButton:disabled {{ color: {C['outline_variant']}; background: {C['container']}; }}
QPushButton[kind="primary"] {{ background: {C['primary_container']}; color: {C['on_primary_container']}; }}
QPushButton[kind="primary"]:hover {{ background: {C['primary']}; }}
QPushButton[kind="danger"] {{ background: {C['error_container']}; color: {C['error']}; }}
QPushButton[kind="danger"]:hover {{ background: {C['error']}; color: {C['on_error']}; }}
QPushButton[kind="ghost"] {{ background: transparent; color: {C['primary']}; }}
QLineEdit, QComboBox, QSpinBox {{ background: {C['low']}; border: 1px solid {C['outline_variant']}; border-radius: 4px; padding: 6px 8px; selection-background-color: {C['primary_container']}; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {C['primary']}; }}
QComboBox QAbstractItemView {{ background: {C['container']}; selection-background-color: {C['primary_container']}; border: 1px solid {C['outline_variant']}; }}
QTableWidget {{ background: {C['low']}; alternate-background-color: {C['low']}; gridline-color: {C['container']}; border: none; border-radius: 4px; selection-background-color: {C['high']}; selection-color: {C['on_surface']}; }}
QTableWidget::item {{ padding: 6px 8px; border-bottom: 1px solid {C['container']}; }}
QHeaderView::section {{ background: {C['lowest']}; color: {C['outline']}; padding: 8px; border: none; font-size: 10px; font-weight: 700; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }} QScrollBar::handle:vertical {{ background: {C['highest']}; border-radius: 4px; min-height: 24px; }}
QScrollBar:horizontal {{ height: 8px; background: transparent; }} QScrollBar::handle:horizontal {{ background: {C['highest']}; border-radius: 4px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QCheckBox {{ spacing: 6px; }} QToolTip {{ background: {C['highest']}; border: 1px solid {C['outline_variant']}; padding: 4px; }}
QMessageBox {{ background: {C['bg']}; }}
"""
