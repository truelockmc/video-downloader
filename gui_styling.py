#!/usr/bin/env python3
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

    /* ── Download Table ── */
    QTableWidget {
        background-color: #111111;
        alternate-background-color: #1a1a1a;
        color: #d0d0d0;
        border: 2px solid #222;
        border-radius: 6px;
        gridline-color: #222;
        font-size: 9pt;
        selection-background-color: transparent;
        selection-color: #d0d0d0;
    }

    QTableWidget::item {
        padding: 4px 8px;
        border: none;
        border-right: 1px solid #1e1e1e;
    }

    QTableWidget::item:last-child {
        border-right: none;
    }

    QTableWidget::item:hover {
        background-color: #1e1e1e;
        border-right: 1px solid #2a2a2a;
    }

    QTableWidget::item:selected {
        background-color: #1a2a3a;
        color: #e0e0e0;
        border-right: 1px solid #0D47A1;
    }

    /* Header */
    QHeaderView::section {
        background-color: #0a0a0a;
        color: #909090;
        font-size: 8pt;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        padding: 6px 8px;
        border: none;
        border-bottom: 2px solid #0D47A1;
        border-right: 1px solid #222;
    }

    QHeaderView::section:last {
        border-right: none;
    }

    QHeaderView::section:hover {
        background-color: #111;
        color: #c0c0c0;
    }

    /* Scrollbar */
    QScrollBar:vertical {
        background: #111;
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: #333;
        border-radius: 4px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: #0D47A1;
    }
    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        height: 0px;
    }
    QScrollBar:horizontal {
        background: #111;
        height: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:horizontal {
        background: #333;
        border-radius: 4px;
        min-width: 20px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #0D47A1;
    }
    QScrollBar::add-line:horizontal,
    QScrollBar::sub-line:horizontal {
        width: 0px;
    }
    """
    app.setStyleSheet(stylesheet)
