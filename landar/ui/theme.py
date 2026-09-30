QSS = """
QWidget{background:#0b1220;color:#e2e8f0;font-size:13px}
#side{background:#0f172a;border:none;min-width:190px;padding:8px} #side::item{padding:10px;border-radius:6px}
#side::item:selected{background:#22d3ee;color:#04202a}
QTableWidget{background:#0f172a;gridline-color:#1e293b;border:1px solid #1e293b;selection-background-color:#164e63}
QHeaderView::section{background:#111c33;color:#94a3b8;padding:6px;border:none}
QPushButton{background:#1e293b;border:1px solid #334155;padding:7px 14px;border-radius:6px}
QPushButton:hover{background:#22d3ee;color:#04202a} QPushButton:disabled{color:#475569}
QLineEdit,QComboBox{background:#111c33;border:1px solid #334155;padding:6px;border-radius:4px}
#card{background:#0f172a;border:1px solid #1e293b;border-radius:8px} #big{font-size:28px;font-weight:600;color:#22d3ee}
#h{font-size:20px;font-weight:600}
"""
WARN_VALUES = {"Unknown"}
BAD_VALUES = {"Blocked", "Disabled", "Locked", "Suspended", "failure", "denied"}
