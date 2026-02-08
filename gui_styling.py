#!/usr/bin/env python3
from PyQt6 import QtGui, QtWidgets


def modern_stylesheet(app):
    stylesheet = """
    /* Main Font Settings */
    * {
        font-family: 'Inter', 'Roboto', 'Helvetica Neue', sans-serif;
        font-weight: 500;
    }

    /* LineEdit - abgerundete Ecken */
    QLineEdit {
        border: 2px solid #222;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 10pt;
        background-color: #1a1a1a;
        color: #d0d0d0;
    }

    QLineEdit:focus {
        border: 2px solid #0D47A1;
        background-color: #212121;
    }

    /* Buttons - abgerundete Ecken */
    QPushButton {
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 600;
        font-size: 10pt;
        background-color: #0D47A1;
        color: #e0e0e0;
    }

    QPushButton:hover {
        background-color: #0A3D91;
    }

    QPushButton:pressed {
        background-color: #082563;
    }

    QPushButton:disabled {
        background-color: #404040;
        color: #707070;
        border: none;
        border-radius: 6px;
    }

    /* ComboBox - abgerundete Ecken */
    QComboBox {
        border: 2px solid #222;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 10pt;
        background-color: #1a1a1a;
        color: #d0d0d0;
    }

    QComboBox:focus {
        border: 2px solid #0D47A1;
        background-color: #212121;
    }

    QComboBox::drop-down {
        border: none;
        border-radius: 5px;
        width: 20px;
    }

    QComboBox QAbstractItemView {
        background-color: #0f0f0f;
        color: #d0d0d0;
        outline: none;
        border: 2px solid #0D47A1;
        border-radius: 6px;
        margin: 0px;
    }

    QComboBox QAbstractItemView::item {
        padding: 10px 12px;
        margin: 2px 4px;
        border-radius: 5px;
        background-color: #0f0f0f;
        color: #d0d0d0;
    }

    QComboBox QAbstractItemView::item:hover {
        background-color: #1976D2;
        color: #ffffff;
        font-weight: bold;
        padding: 10px 12px;
    }

    QComboBox QAbstractItemView::item:selected {
        background-color: #0D47A1;
        color: #ffffff;
        font-weight: bold;
        padding: 10px 12px;
    }

    QComboBox QAbstractItemView::item:selected:hover {
        background-color: #1976D2;
        color: #ffffff;
        font-weight: bold;
    }

    /* GroupBox - abgerundete Ecken */
    QGroupBox {
        border: 2px solid #222;
        border-radius: 6px;
        margin-top: 8px;
        padding-top: 8px;
        padding-left: 6px;
        padding-right: 6px;
        padding-bottom: 6px;
        font-weight: 600;
        font-size: 10pt;
        color: #d0d0d0;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 2px 0 2px;
        color: #d0d0d0;
    }

    /* Label */
    QLabel {
        font-size: 10pt;
        color: #d0d0d0;
    }

    /* Error Label */
    QLabel#urlError {
        color: #ff6b6b;
        font-weight: bold;
        font-size: 9pt;
        margin-top: -8px;
    }
    """
    app.setStyleSheet(stylesheet)
