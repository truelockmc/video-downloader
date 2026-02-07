#!/usr/bin/env python3
from PyQt6 import QtWidgets


def modern_stylesheet(app):
    """Apply modern rounded styling WITHOUT changing background colors"""
    stylesheet = """
    /* LineEdit - abgerundete Ecken */
    QLineEdit {
        border: 2px solid #555;
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 12px;
    }

    QLineEdit:focus {
        border: 2px solid #0d47a1;
    }

    /* Buttons - abgerundete Ecken */
    QPushButton {
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: bold;
        font-size: 12px;
        background-color: #2196F3;
        color: white;
    }

    QPushButton:hover {
        background-color: #1976D2;
    }

    QPushButton:pressed {
        background-color: #0d47a1;
    }

    /* ComboBox - abgerundete Ecken */
    QComboBox {
        border: 2px solid #555;
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 12px;
    }

    QComboBox:focus {
        border: 2px solid #0d47a1;
    }

    QComboBox::drop-down {
        border: none;
        border-radius: 6px;
    }

    /* GroupBox - abgerundete Ecken */
    QGroupBox {
        border: 2px solid #555;
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 10px;
        font-weight: bold;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 3px 0 3px;
    }
    """
    app.setStyleSheet(stylesheet)
