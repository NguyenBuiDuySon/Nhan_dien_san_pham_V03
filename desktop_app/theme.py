APP_STYLE = """
QWidget {
    background-color: #0b1220;
    color: #e5e7eb;
    font-family: Segoe UI, Arial;
    font-size: 14px;
}

QMainWindow {
    background-color: #0b1220;
}

QFrame#Card {
    background-color: #111827;
    border: 1px solid #243042;
    border-radius: 14px;
}

QGroupBox {
    background-color: #111827;
    border: 1px solid #243042;
    border-radius: 10px;
    margin-top: 10px;
    padding: 12px 8px 8px 8px;
    font-weight: 700;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #cbd5e1;
}

QGroupBox[locked="true"] {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    color: #64748b;
}

QPushButton {
    border: none;
    border-radius: 10px;
    padding: 11px 14px;
    font-weight: 700;
    color: white;
    background-color: #334155;
}

QPushButton:hover {
    background-color: #475569;
}

QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
}

QLabel#Title {
    font-size: 22px;
    font-weight: 900;
    color: #f8fafc;
}

QLabel#Subtitle {
    color: #94a3b8;
}

QLabel#Badge {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: 700;
    min-height: 24px;
    max-height: 30px;
}

QLabel#SmallCard {
    background-color: #0f172a;
    border: 1px solid #243042;
    border-radius: 12px;
    padding: 10px;
}

QPlainTextEdit {
    background-color: #020617;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 10px;
    color: #22c55e;
    font-family: Consolas, monospace;
}

QLineEdit {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px;
    color: #e5e7eb;
}

QCheckBox {
    spacing: 8px;
    font-weight: 700;
}

QDoubleSpinBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px;
    color: #e5e7eb;
}

QDoubleSpinBox:disabled {
    background-color: #1e293b;
    color: #64748b;
}

QLabel:disabled {
    color: #94a3b8;
}

QPushButton:disabled {
    background-color: #263244;
    color: #94a3b8;
}

QDoubleSpinBox:disabled {
    background-color: #1e293b;
    color: #94a3b8;
    border: 1px solid #334155;
}

QComboBox {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px;
    color: #e5e7eb;
}

QComboBox:disabled {
    background-color: #1e293b;
    color: #94a3b8;
}

"""