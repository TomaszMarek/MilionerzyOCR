from PySide6.QtWidgets import QDialog, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

class ConfirmationDialog(QDialog):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(440, 190)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        main_box = QFrame(self)
        main_box.setGeometry(0, 0, 440, 190)
        main_box.setObjectName("sectionBox")
        main_box.setStyleSheet("""
            QFrame#sectionBox {
                background-color: #0b131e;
                border: 1px solid #1f2d3d;
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout(main_box)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet("color: #f85149; font-size: 13px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(lbl_title)

        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet("color: #c9d1d9; font-size: 13px; line-height: 1.4;")
        layout.addWidget(lbl_msg)

        layout.addStretch()

        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(10)
        btns_layout.addStretch()

        btn_cancel = QPushButton("ANULUJ")
        btn_cancel.setObjectName("btnTopAction")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setFixedHeight(34)
        btn_cancel.clicked.connect(self.reject)
        btns_layout.addWidget(btn_cancel)

        btn_confirm = QPushButton("WYCZYŚĆ BAZĘ")
        btn_confirm.setObjectName("btnDangerAction")
        btn_confirm.setCursor(Qt.PointingHandCursor)
        btn_confirm.setFixedHeight(34)
        btn_confirm.setStyleSheet("""
            QPushButton#btnDangerAction {
                background-color: #f85149;
                color: #ffffff;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
            }
            QPushButton#btnDangerAction:hover {
                background-color: #da3633;
            }
        """)
        btn_confirm.clicked.connect(self.accept)
        btns_layout.addWidget(btn_confirm)

        layout.addLayout(btns_layout)