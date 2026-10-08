from PySide6.QtWidgets import QDialog, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

class InfoDialog(QDialog):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(440, 180)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        main_box = QFrame(self)
        main_box.setGeometry(0, 0, 440, 180)
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
        layout.setSpacing(12)

        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet("color: #00c8ff; font-size: 13px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(lbl_title)

        lbl_msg = QLabel(message)
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet("color: #c9d1d9; font-size: 13px; line-height: 1.4;")
        layout.addWidget(lbl_msg)

        layout.addStretch()

        btns_layout = QHBoxLayout()
        btns_layout.addStretch()

        btn_ok = QPushButton("ROZUMIEM")
        btn_ok.setObjectName("btnTopAction")
        btn_ok.setCursor(Qt.PointingHandCursor)
        btn_ok.setFixedHeight(34)
        btn_ok.setStyleSheet("""
            QPushButton#btnTopAction {
                background-color: #1f2d3d;
                color: #00c8ff;
                font-weight: bold;
                border: 1px solid #00c8ff;
                border-radius: 6px;
                padding: 0 20px;
            }
            QPushButton#btnTopAction:hover {
                background-color: #00c8ff;
                color: #0b131e;
            }
        """)
        btn_ok.clicked.connect(self.accept)
        btns_layout.addWidget(btn_ok)

        layout.addLayout(btns_layout)