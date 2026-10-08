import os
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QPushButton, QButtonGroup
)


class EditQuestionDialog(QDialog):
    def __init__(self, entries_list: list, current_index: int, on_save_callback, parent=None):
        super().__init__(parent)
        self.entries_list = entries_list
        self.current_index = current_index
        self.on_save_callback = on_save_callback

        self.setObjectName("editDialog")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setFixedWidth(900)

        self.selected_letter = None
        self.selected_station = "TVN"

        self._build_ui()
        self._load_current_entry()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 24)
        root.setSpacing(12)

        header_bar = QHBoxLayout()
        self.btn_prev = QPushButton("Poprzednie")
        self.btn_prev.setObjectName("btnSpeedNav")
        self.btn_prev.clicked.connect(self._go_previous)
        header_bar.addWidget(self.btn_prev)

        header_bar.addStretch()
        self.title_lbl = QLabel("EDYCJA PYTANIA")
        self.title_lbl.setObjectName("modalTitle")
        header_bar.addWidget(self.title_lbl)
        header_bar.addStretch()

        self.btn_next = QPushButton("Następne")
        self.btn_next.setObjectName("btnSpeedNav")
        self.btn_next.clicked.connect(self._go_next)
        header_bar.addWidget(self.btn_next)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("modalCloseBtn")
        btn_close.setFixedSize(30, 30)
        btn_close.clicked.connect(self.accept)
        header_bar.addWidget(btn_close)
        root.addLayout(header_bar)

        self.img_container = QLabel()
        self.img_container.setObjectName("modalImageFrame")
        self.img_container.setFixedHeight(300)
        self.img_container.setAlignment(Qt.AlignCenter)
        root.addWidget(self.img_container)

        lbl_q = QLabel("TREŚĆ PYTANIA")
        lbl_q.setObjectName("modalFieldLabel")
        root.addWidget(lbl_q)

        self.txt_question = QTextEdit()
        self.txt_question.setObjectName("modalQuestionInput")
        self.txt_question.setFixedHeight(75)
        root.addWidget(self.txt_question)

        ans_layout = QVBoxLayout()
        ans_layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        self.input_a = self._create_variant_field("WARIANT A", row1)
        self.input_b = self._create_variant_field("WARIANT B", row1)
        ans_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(16)
        self.input_c = self._create_variant_field("WARIANT C", row2)
        self.input_d = self._create_variant_field("WARIANT D", row2)
        ans_layout.addLayout(row2)
        root.addLayout(ans_layout)

        options_bar = QHBoxLayout()
        options_bar.setSpacing(10)

        lbl_corr = QLabel("POPRAWNA ODPOWIEDŹ:")
        lbl_corr.setObjectName("modalFieldLabel")
        options_bar.addWidget(lbl_corr)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)
        self.letter_buttons = {}

        for letter in ("A", "B", "C", "D"):
            btn = QPushButton(letter)
            btn.setCheckable(True)
            btn.setObjectName("letterChoiceBtn")
            btn.setFixedSize(48, 36)
            btn.clicked.connect(lambda _, l=letter: self._set_correct(l))
            self.btn_group.addButton(btn)
            self.letter_buttons[letter] = btn
            options_bar.addWidget(btn)

        self.btn_none = QPushButton("BRAK")
        self.btn_none.setCheckable(True)
        self.btn_none.setObjectName("letterChoiceBtn")
        self.btn_none.setFixedSize(60, 36)
        self.btn_none.clicked.connect(lambda: self._set_correct(None))
        self.btn_group.addButton(self.btn_none)
        options_bar.addWidget(self.btn_none)

        options_bar.addSpacing(30)

        lbl_st = QLabel("STACJA:")
        lbl_st.setObjectName("modalFieldLabel")
        options_bar.addWidget(lbl_st)

        self.st_group = QButtonGroup(self)
        self.st_group.setExclusive(True)
        self.btn_tvn = QPushButton("TVN")
        self.btn_tvn.setCheckable(True)
        self.btn_tvn.setObjectName("letterChoiceBtn")
        self.btn_tvn.setFixedSize(55, 36)
        self.btn_tvn.clicked.connect(lambda: self._set_station("TVN"))
        self.st_group.addButton(self.btn_tvn)
        options_bar.addWidget(self.btn_tvn)

        self.btn_polsat = QPushButton("POLSAT")
        self.btn_polsat.setCheckable(True)
        self.btn_polsat.setObjectName("letterChoiceBtn")
        self.btn_polsat.setFixedSize(70, 36)
        self.btn_polsat.clicked.connect(lambda: self._set_station("POLSAT"))
        self.st_group.addButton(self.btn_polsat)
        options_bar.addWidget(self.btn_polsat)

        options_bar.addStretch()
        root.addLayout(options_bar)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        actions.addStretch()

        self.btn_save = QPushButton("ZAPISZ I ZAMKNIJ")
        self.btn_save.setObjectName("modalSaveBtn")
        self.btn_save.clicked.connect(self._on_save_clicked)
        actions.addWidget(self.btn_save)

        root.addLayout(actions)

    @staticmethod
    def _create_variant_field(label_text: str, parent_layout: QHBoxLayout) -> QLineEdit:
        col = QVBoxLayout()
        col.setSpacing(4)
        lbl = QLabel(label_text)
        lbl.setObjectName("modalFieldLabel")
        col.addWidget(lbl)

        inp = QLineEdit()
        inp.setObjectName("modalVariantInput")
        col.addWidget(inp)
        parent_layout.addLayout(col)
        return inp

    def _load_current_entry(self):
        entry = self.entries_list[self.current_index]
        self.title_lbl.setText(f"EDYCJA: REKORD #{entry.id} ({self.current_index + 1}/{len(self.entries_list)})")
        self.btn_prev.setEnabled(self.current_index > 0)
        self.btn_next.setEnabled(self.current_index < len(self.entries_list) - 1)

        if entry.screenshot_path and os.path.exists(entry.screenshot_path):
            pix = QPixmap(entry.screenshot_path)
            self.img_container.setPixmap(
                pix.scaled(840, 295, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.img_container.setText("Brak zapisanego kadru wideo z rozstrzygnięciem")

        self.txt_question.setPlainText(entry.pytanie)
        self.input_a.setText(entry.warianty.get("A", ""))
        self.input_b.setText(entry.warianty.get("B", ""))
        self.input_c.setText(entry.warianty.get("C", ""))
        self.input_d.setText(entry.warianty.get("D", ""))

        self.selected_letter = entry.poprawna_odpowiedz
        if self.selected_letter in self.letter_buttons:
            self.letter_buttons[self.selected_letter].setChecked(True)
        else:
            self.btn_none.setChecked(True)

        self.selected_station = getattr(entry, "station", "TVN")
        if self.selected_station == "POLSAT":
            self.btn_polsat.setChecked(True)
        else:
            self.btn_tvn.setChecked(True)

    def _set_correct(self, letter: Optional[str]):
        self.selected_letter = letter

    def _set_station(self, station: str):
        self.selected_station = station

    def _persist_fields_to_model(self):
        entry = self.entries_list[self.current_index]
        entry.pytanie = self.txt_question.toPlainText().strip()
        entry.warianty["A"] = self.input_a.text().strip()
        entry.warianty["B"] = self.input_b.text().strip()
        entry.warianty["C"] = self.input_c.text().strip()
        entry.warianty["D"] = self.input_d.text().strip()
        entry.poprawna_odpowiedz = self.selected_letter
        entry.station = self.selected_station
        self.on_save_callback(entry)

    def _on_save_clicked(self):
        self._persist_fields_to_model()
        self.btn_save.setText("ZAPISANO!")
        self.btn_save.setStyleSheet("background-color: #238636; color: #ffffff; font-weight: bold;")
        self.btn_save.setEnabled(False)
        QTimer.singleShot(350, self.accept)

    def _go_previous(self):
        self._persist_fields_to_model()
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current_entry()

    def _go_next(self):
        self._persist_fields_to_model()
        if self.current_index < len(self.entries_list) - 1:
            self.current_index += 1
            self._load_current_entry()