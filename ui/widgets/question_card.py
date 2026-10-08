from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QCheckBox
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from database.models import QuestionEntry


class QuestionCard(QFrame):
    def __init__(self, entry: QuestionEntry, on_edit, on_delete, on_check_toggle, on_favorite_toggle, is_checked=False,
                 parent=None):
        super().__init__(parent)
        self.entry = entry
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_check_toggle = on_check_toggle
        self.on_favorite_toggle = on_favorite_toggle
        self.is_checked = is_checked

        self.setObjectName("questionCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 14, 18, 16)
        root.setSpacing(12)
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.chk = QCheckBox()
        self.chk.setChecked(self.is_checked)
        self.chk.stateChanged.connect(lambda state: self.on_check_toggle(self.entry.id, state == 2))
        top_bar.addWidget(self.chk)

        self.star_btn = QPushButton("★" if self.entry.is_favorite else "☆")
        self.star_btn.setObjectName("btnStarFav")
        if self.entry.is_favorite:
            self.star_btn.setProperty("favorite", True)
        self.star_btn.clicked.connect(self._toggle_fav)
        top_bar.addWidget(self.star_btn)

        id_lbl = QLabel(f"REKORD #{self.entry.id}")
        id_lbl.setObjectName("cardRecordId")
        top_bar.addWidget(id_lbl)

        top_bar.addStretch()

        if self.entry.poprawna_odpowiedz:
            correct_badge = QLabel(f"POPRAWNA: {self.entry.poprawna_odpowiedz}")
            correct_badge.setObjectName("badgeCorrect")
            top_bar.addWidget(correct_badge)
        else:
            unresolved_badge = QLabel("DO WERYFIKACJI")
            unresolved_badge.setObjectName("badgeUnresolved")
            top_bar.addWidget(unresolved_badge)

        edit_btn = QPushButton("EDYTUJ")
        edit_btn.setObjectName("btnCardEdit")
        edit_btn.clicked.connect(lambda: self.on_edit(self.entry))
        top_bar.addWidget(edit_btn)

        del_btn = QPushButton("USUŃ")
        del_btn.setObjectName("btnCardDelete")
        del_btn.clicked.connect(lambda: self.on_delete(self.entry.id))
        top_bar.addWidget(del_btn)

        root.addLayout(top_bar)
        q_label = QLabel(self.entry.pytanie)
        q_label.setObjectName("cardQuestionText")
        q_label.setWordWrap(True)
        root.addWidget(q_label)
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        positions = {"A": (0, 0), "B": (0, 1), "C": (1, 0), "D": (1, 1)}

        tag_font = QFont("Segoe UI", 10, QFont.ExtraBold)
        content_font = QFont("Segoe UI", 10, QFont.Bold)

        for letter, (row, col) in positions.items():
            val = self.entry.warianty.get(letter, "")
            tile = QFrame()
            tile.setObjectName("ansTileBox")
            tile.setFrameShape(QFrame.StyledPanel)
            tile.setAttribute(Qt.WA_StyledBackground, True)

            is_correct = (self.entry.poprawna_odpowiedz == letter)
            if is_correct:
                tile.setProperty("correct", True)

            t_layout = QHBoxLayout(tile)
            t_layout.setContentsMargins(12, 8, 12, 8)
            t_layout.setSpacing(8)

            letter_tag = QLabel(f"{letter}:")
            letter_tag.setFont(tag_font)
            letter_tag.setObjectName("ansLetterTag")
            if is_correct:
                letter_tag.setProperty("correct", True)
            t_layout.addWidget(letter_tag)

            text_lbl = QLabel(val if val else "-")
            text_lbl.setFont(content_font)
            text_lbl.setObjectName("ansTextContent")
            if is_correct:
                text_lbl.setProperty("correct", True)
            t_layout.addWidget(text_lbl, stretch=1)

            grid.addWidget(tile, row, col)

        root.addLayout(grid)

    def _toggle_fav(self):
        new_state = self.on_favorite_toggle(self.entry.id)
        self.entry.is_favorite = new_state
        self.star_btn.setText("★" if new_state else "☆")
        self.star_btn.setProperty("favorite", new_state)
        self.star_btn.style().unpolish(self.star_btn)
        self.star_btn.style().polish(self.star_btn)