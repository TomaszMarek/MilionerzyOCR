import math
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox,
    QPushButton, QLabel, QScrollArea, QFrame, QDialog
)
from PySide6.QtCore import Qt, Signal

from database.db_manager import DatabaseManager
from ui.widgets.question_card import QuestionCard
from ui.dialogs.edit_dialog import EditQuestionDialog
from ui.dialogs.confirmation_dialog import ConfirmationDialog


class DatabaseView(QWidget):
    records_count_changed = Signal(int)
    export_requested = Signal(list)

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.currently_displayed_entries = []
        self.selected_entry_ids = set()

        self.active_letter_filter = "ALL"
        self.active_station_filter = "ALL"
        self.active_sort_mode = "NEWEST"
        self.filter_only_favorites = False

        self.current_page = 1
        self.page_size = 25

        self._init_ui()
        self.refresh_cards()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchField")
        self.search_input.setPlaceholderText("Szukaj w pytaniach i wariantach...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_filter_changed)
        toolbar.addWidget(self.search_input, stretch=3)

        self.combo_station = QComboBox()
        self.combo_station.setObjectName("sortComboBox")
        self.combo_station.addItem("Wszystkie stacje", "ALL")
        self.combo_station.addItem("TVN", "TVN")
        self.combo_station.addItem("Polsat", "POLSAT")
        self.combo_station.currentIndexChanged.connect(self._on_station_combo_changed)
        toolbar.addWidget(self.combo_station)

        self.combo_answer = QComboBox()
        self.combo_answer.setObjectName("sortComboBox")
        self.combo_answer.addItem("Wszystkie rekordy", "ALL")
        self.combo_answer.addItem("Tylko z odpowiedzią (A-D)", "VALID_ONLY")
        self.combo_answer.addItem("Brak odpowiedzi (Do weryfikacji)", "NONE")
        self.combo_answer.addItem("Odpowiedź A", "A")
        self.combo_answer.addItem("Odpowiedź B", "B")
        self.combo_answer.addItem("Odpowiedź C", "C")
        self.combo_answer.addItem("Odpowiedź D", "D")
        self.combo_answer.currentIndexChanged.connect(self._on_answer_combo_changed)
        toolbar.addWidget(self.combo_answer)

        self.btn_fav_filter = QPushButton("★ Ulubione")
        self.btn_fav_filter.setCheckable(True)
        self.btn_fav_filter.setObjectName("pillFavFilterBtn")
        self.btn_fav_filter.clicked.connect(self._toggle_favorite_filter)
        toolbar.addWidget(self.btn_fav_filter)

        self.sort_combo = QComboBox()
        self.sort_combo.setObjectName("sortComboBox")
        self.sort_combo.addItem("Najnowsze", "NEWEST")
        self.sort_combo.addItem("Najstarsze", "OLDEST")
        self.sort_combo.addItem("Nazwa (A-Z)", "ALPHA")
        self.sort_combo.currentIndexChanged.connect(self._on_sort_change)
        toolbar.addWidget(self.sort_combo)

        self.counter_lbl = QLabel()
        self.counter_lbl.setObjectName("badgeRecordCounter")
        toolbar.addWidget(self.counter_lbl)
        layout.addLayout(toolbar)

        actions_bar = QHBoxLayout()
        actions_bar.setSpacing(8)

        self.btn_bulk_delete = QPushButton("Usuń zaznaczone (0)")
        self.btn_bulk_delete.setObjectName("btnTopAction")
        self.btn_bulk_delete.setEnabled(False)
        self.btn_bulk_delete.clicked.connect(self._delete_selected_records)
        actions_bar.addWidget(self.btn_bulk_delete)

        self.btn_select_all = QPushButton("Zaznacz wszystkie")
        self.btn_select_all.setObjectName("btnTopAction")
        self.btn_select_all.setEnabled(False)
        self.btn_select_all.clicked.connect(self._select_all_visible)
        actions_bar.addWidget(self.btn_select_all)

        self.btn_clear_selection = QPushButton("Odznacz")
        self.btn_clear_selection.setObjectName("btnTopAction")
        self.btn_clear_selection.setEnabled(False)
        self.btn_clear_selection.clicked.connect(self._clear_all_selection)
        actions_bar.addWidget(self.btn_clear_selection)

        actions_bar.addStretch()

        self.btn_clear_db = QPushButton("Wyczyść bazę")
        self.btn_clear_db.setObjectName("btnDangerAction")
        self.btn_clear_db.setEnabled(False)
        self.btn_clear_db.clicked.connect(self._clear_entire_database)
        actions_bar.addWidget(self.btn_clear_db)
        layout.addLayout(actions_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background: transparent;")

        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(10)
        self.card_layout.addStretch()

        self.scroll.setWidget(self.card_container)
        layout.addWidget(self.scroll)

        pagination_bar = QHBoxLayout()
        pagination_bar.setContentsMargins(0, 4, 0, 0)
        pagination_bar.setSpacing(12)
        pagination_bar.addStretch()

        self.btn_page_prev = QPushButton("◀ Poprzednia")
        self.btn_page_prev.setObjectName("btnPagination")
        self.btn_page_prev.clicked.connect(self._page_prev)
        pagination_bar.addWidget(self.btn_page_prev)

        self.lbl_page_info = QLabel("Strona 1 z 1")
        self.lbl_page_info.setObjectName("lblPaginationInfo")
        pagination_bar.addWidget(self.lbl_page_info)

        self.btn_page_next = QPushButton("Następna ▶")
        self.btn_page_next.setObjectName("btnPagination")
        self.btn_page_next.clicked.connect(self._page_next)
        pagination_bar.addWidget(self.btn_page_next)

        pagination_bar.addStretch()
        layout.addLayout(pagination_bar)

    def _on_station_combo_changed(self):
        self.active_station_filter = self.combo_station.currentData()
        self.current_page = 1
        self.refresh_cards()

    def _on_filter_changed(self):
        self.current_page = 1
        self.refresh_cards()

    def _on_answer_combo_changed(self):
        self.active_letter_filter = self.combo_answer.currentData()
        self.current_page = 1
        self.refresh_cards()

    def _toggle_favorite_filter(self):
        self.filter_only_favorites = self.btn_fav_filter.isChecked()
        self.current_page = 1
        self.refresh_cards()

    def _on_sort_change(self):
        self.active_sort_mode = self.sort_combo.currentData()
        self.refresh_cards()

    def _page_prev(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_cards()
            self.scroll.verticalScrollBar().setValue(0)

    def _page_next(self):
        total_pages = max(1, math.ceil(len(self.currently_displayed_entries) / self.page_size))
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_cards()
            self.scroll.verticalScrollBar().setValue(0)

    def refresh_cards(self):
        self._update_bulk_buttons()
        self.card_container.setUpdatesEnabled(False)
        try:
            while self.card_layout.count() > 1:
                item = self.card_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()

            entries = list(self.db.get_all())
            q = self.search_input.text().strip().lower()

            filtered = []
            for e in entries:
                match_txt = (not q) or (q in e.pytanie.lower()) or any(q in v.lower() for v in e.warianty.values())
                if self.active_letter_filter == "ALL":
                    match_ltr = True
                elif self.active_letter_filter == "VALID_ONLY":
                    match_ltr = bool(e.poprawna_odpowiedz and e.poprawna_odpowiedz.strip())
                elif self.active_letter_filter == "NONE":
                    match_ltr = (e.poprawna_odpowiedz is None or e.poprawna_odpowiedz == "")
                else:
                    match_ltr = (e.poprawna_odpowiedz == self.active_letter_filter)

                entry_station = getattr(e, "station", "TVN") or "TVN"
                if self.active_station_filter == "ALL":
                    match_st = True
                elif self.active_station_filter == "POLSAT":
                    match_st = "POLSAT" in entry_station
                else:
                    match_st = (entry_station == self.active_station_filter)

                match_fav = (not self.filter_only_favorites) or e.is_favorite

                if match_txt and match_ltr and match_st and match_fav:
                    filtered.append(e)

            if self.active_sort_mode == "NEWEST":
                filtered.sort(key=lambda x: str(x.id), reverse=True)
            elif self.active_sort_mode == "OLDEST":
                filtered.sort(key=lambda x: str(x.id))
            elif self.active_sort_mode == "ALPHA":
                filtered.sort(key=lambda x: x.pytanie.lower())

            self.currently_displayed_entries = filtered
            self.counter_lbl.setText(f"Rekordy: <span style='color: #00c8ff;'>{len(filtered)}</span> / {len(entries)}")
            self.records_count_changed.emit(len(entries))
            self._update_bulk_buttons()

            if not filtered:
                empty_frame = QFrame()
                empty_frame.setObjectName("emptyStateFrame")
                v_empty = QVBoxLayout(empty_frame)
                v_empty.setAlignment(Qt.AlignCenter)
                v_empty.setSpacing(8)

                lbl_main = QLabel("BRAK REKORDÓW W BAZIE")
                lbl_main.setObjectName("emptyStateTitle")
                lbl_main.setAlignment(Qt.AlignCenter)
                v_empty.addWidget(lbl_main)

                lbl_sub = QLabel("Rozpocznij analizę wideo lub zmień bieżące filtry wyszukiwania.")
                lbl_sub.setObjectName("emptyStateSubtitle")
                lbl_sub.setAlignment(Qt.AlignCenter)
                v_empty.addWidget(lbl_sub)

                self.card_layout.insertWidget(0, empty_frame)
                self.lbl_page_info.setText("Strona 1 z 1")
                self.btn_page_prev.setEnabled(False)
                self.btn_page_next.setEnabled(False)
                return

            total_pages = max(1, math.ceil(len(filtered) / self.page_size))
            if self.current_page > total_pages:
                self.current_page = total_pages

            self.lbl_page_info.setText(f"Strona {self.current_page} z {total_pages}")
            self.btn_page_prev.setEnabled(self.current_page > 1)
            self.btn_page_next.setEnabled(self.current_page < total_pages)

            start_idx = (self.current_page - 1) * self.page_size
            end_idx = start_idx + self.page_size
            page_entries = filtered[start_idx:end_idx]

            for e in page_entries:
                is_chk = e.id in self.selected_entry_ids
                card = QuestionCard(
                    e,
                    on_edit=lambda ent=e: self._open_edit_dialog(ent),
                    on_delete=self._delete_record,
                    on_check_toggle=self._toggle_checkbox,
                    on_favorite_toggle=self._on_favorite_toggled,
                    is_checked=is_chk
                )
                self.card_layout.insertWidget(self.card_layout.count() - 1, card)
        finally:
            self.card_container.setUpdatesEnabled(True)

    def _toggle_checkbox(self, entry_id: str, is_checked: bool):
        if is_checked:
            self.selected_entry_ids.add(entry_id)
        else:
            self.selected_entry_ids.discard(entry_id)
        self._update_bulk_buttons()

    def _select_all_visible(self):
        for e in self.currently_displayed_entries:
            self.selected_entry_ids.add(e.id)
        self.refresh_cards()

    def _clear_all_selection(self):
        self.selected_entry_ids.clear()
        self.refresh_cards()

    def _update_bulk_buttons(self):
        count = len(self.selected_entry_ids)
        total_in_db = self.db.count()
        visible_count = len(self.currently_displayed_entries)

        self.btn_bulk_delete.setText(f"Usuń zaznaczone ({count})")
        self.btn_bulk_delete.setEnabled(count > 0)
        self.btn_select_all.setEnabled(visible_count > 0 and count < visible_count)
        self.btn_clear_selection.setEnabled(count > 0)
        self.btn_clear_db.setEnabled(total_in_db > 0)

    def _delete_selected_records(self):
        if not self.selected_entry_ids:
            return
        count = len(self.selected_entry_ids)
        dialog = ConfirmationDialog(
            title="Usuwanie zaznaczonych pytań",
            message=f"Czy na pewno chcesz bezpowrotnie usunąć zaznaczone pytania ({count}) wraz ze zrzutami ekranu z dysku?",
            parent=self
        )
        if dialog.exec() == QDialog.Accepted:
            self.db.delete_bulk(self.selected_entry_ids)
            self.selected_entry_ids.clear()
            self.refresh_cards()

    def _clear_entire_database(self):
        total = self.db.count()
        if total == 0:
            return
        dialog = ConfirmationDialog(
            title="Wyczyszczenie całej bazy",
            message=f"Czy na pewno chcesz bezpowrotnie usunąć wszystkie pytania ({total}) oraz powiązane zrzuty ekranu z dysku?",
            parent=self
        )
        if dialog.exec() == QDialog.Accepted:
            self.db.clear_all()
            self.selected_entry_ids.clear()
            self.refresh_cards()

    def _on_favorite_toggled(self, entry_id: str) -> bool:
        new_state = self.db.toggle_favorite(entry_id)
        if self.filter_only_favorites:
            self.refresh_cards()
        return new_state

    def _open_edit_dialog(self, entry):
        if not self.currently_displayed_entries:
            return
        idx = next((i for i, el in enumerate(self.currently_displayed_entries) if el.id == entry.id), 0)
        dlg = EditQuestionDialog(self.currently_displayed_entries, idx, self._on_dialog_saved, self)
        dlg.exec()
        self.refresh_cards()

    def _on_dialog_saved(self, entry):
        self.db.update_entry(
            entry.id,
            entry.pytanie,
            entry.warianty,
            entry.poprawna_odpowiedz,
            getattr(entry, "station", "TVN")
        )

    def _delete_record(self, entry_id):
        self.db.delete_entry(entry_id)
        self.selected_entry_ids.discard(entry_id)
        self.refresh_cards()

    def get_export_candidates(self) -> list:
        if self.selected_entry_ids:
            return [e for e in self.db.get_all() if e.id in self.selected_entry_ids]
        return self.currently_displayed_entries