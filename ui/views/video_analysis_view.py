import os

import cv2
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPixmap, QImage
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QScrollArea, QFileDialog, QListWidgetItem
)

from core.video_worker import VideoWorker
from core.vision_engine import VisionEngine
from ui.widgets.deselectable_list import DeselectableListWidget


def _create_scrollable_container(spacing: int = 8) -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("border: none; background: transparent;")

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    layout.addStretch()

    scroll.setWidget(container)
    return scroll, layout

class VideoAnalysisView(QWidget):
    question_resolved_signal = Signal(object)

    def __init__(self, engine: VisionEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.worker = None
        self.video_queue = []
        self._init_ui()
        self.is_interrupted = False

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 8, 0, 0)
        main_layout.setSpacing(18)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        q_box = QFrame()
        q_box.setObjectName("sectionBox")
        q_layout = QVBoxLayout(q_box)
        q_layout.setContentsMargins(12, 10, 12, 12)
        q_layout.setSpacing(8)

        self.lbl_q = QLabel("KOLEJKA ODCINKÓW (0)")
        self.lbl_q.setObjectName("sectionTitle")
        q_layout.addWidget(self.lbl_q)

        self.queue_list = DeselectableListWidget()
        self.queue_list.setObjectName("queueList")
        self.queue_list.setFixedHeight(120)
        self.queue_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.queue_list.itemSelectionChanged.connect(self._update_queue_buttons_state)
        q_layout.addWidget(self.queue_list)

        q_btns = QHBoxLayout()
        q_btns.setSpacing(6)

        self.add_btn = QPushButton("+ Dodaj")
        self.add_btn.setObjectName("btnTopAction")
        self.add_btn.clicked.connect(self._add_video_to_queue)
        q_btns.addWidget(self.add_btn)

        self.del_btn = QPushButton("Usuń zaznaczony")
        self.del_btn.setObjectName("btnTopAction")
        self.del_btn.setEnabled(False)
        self.del_btn.clicked.connect(self._remove_selected_from_queue)
        q_btns.addWidget(self.del_btn)

        self.clear_q_btn = QPushButton("Wyczyść ukończone")
        self.clear_q_btn.setObjectName("btnTopAction")
        self.clear_q_btn.setEnabled(False)
        self.clear_q_btn.clicked.connect(self._clear_finished_from_queue)
        q_btns.addWidget(self.clear_q_btn)

        q_layout.addLayout(q_btns)
        left_col.addWidget(q_box)

        self.start_btn = QPushButton("▶ ROZPOCZNIJ ANALIZĘ")
        self.start_btn.setObjectName("btnStartAnalysis")
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._toggle_analysis)
        left_col.addWidget(self.start_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("analysisProgress")
        self.progress_bar.setValue(0)
        left_col.addWidget(self.progress_bar)

        reg_box = QFrame()
        reg_box.setObjectName("sectionBox")
        reg_layout = QVBoxLayout(reg_box)
        reg_layout.setContentsMargins(14, 12, 14, 12)
        reg_layout.setSpacing(10)

        reg_header = QHBoxLayout()
        lbl_reg = QLabel("DZIENNIK PRZEBIEGU ANALIZY")
        lbl_reg.setObjectName("sectionTitle")
        reg_header.addWidget(lbl_reg)
        reg_header.addStretch()

        self.btn_clear_log = QPushButton("Wyczyść")
        self.btn_clear_log.setObjectName("btnTopAction")
        self.btn_clear_log.setEnabled(False)
        self.btn_clear_log.clicked.connect(self._clear_log)
        reg_header.addWidget(self.btn_clear_log)
        reg_layout.addLayout(reg_header)
        self.log_scroll = QScrollArea()
        self.log_scroll.setWidgetResizable(True)
        self.log_scroll.setStyleSheet("border: none; background: transparent;")
        self.log_container = QWidget()
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_layout.setSpacing(8)
        self.log_layout.addStretch()
        self.log_scroll.setWidget(self.log_container)
        reg_layout.addWidget(self.log_scroll)
        left_col.addWidget(reg_box, stretch=1)
        main_layout.addLayout(left_col, stretch=4)

        right_box = QFrame()
        right_box.setObjectName("sectionBox")
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(16, 12, 16, 16)
        right_layout.setSpacing(12)

        lbl_p1 = QLabel("KLATKA: WYKRYTE PYTANIE")
        lbl_p1.setObjectName("sectionTitle")
        right_layout.addWidget(lbl_p1)

        self.img_question = QLabel("Oczekiwanie na planszę z pytaniem...")
        self.img_question.setObjectName("previewFrameLarge")
        self.img_question.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.img_question, stretch=1)

        lbl_p2 = QLabel("KLATKA: ROZSTRZYGNIĘCIE")
        lbl_p2.setObjectName("sectionTitle")
        right_layout.addWidget(lbl_p2)

        self.img_resolved = QLabel("Oczekiwanie na zielony kafelek odpowiedzi...")
        self.img_resolved.setObjectName("previewFrameLarge")
        self.img_resolved.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.img_resolved, stretch=1)

        main_layout.addWidget(right_box, stretch=6)

    @staticmethod
    def _format_item_text(filename: str, status: str) -> str:
        max_len = 34
        if len(filename) > max_len:
            display_name = filename[:max_len - 3] + "..."
        else:
            display_name = filename
        return f"{display_name}   ·   {status}"

    def _update_queue_buttons_state(self):
        total_items = self.queue_list.count()
        self.lbl_q.setText(f"KOLEJKA ODCINKÓW ({total_items})")

        selected_items = self.queue_list.selectedItems()
        if not selected_items:
            self.del_btn.setEnabled(False)
        else:
            txt = selected_items[0].text().upper()
            self.del_btn.setEnabled("W TRAKCIE" not in txt and "ANALIZOWANIE" not in txt)

        has_finished = any(
            any(k in self.queue_list.item(i).text().upper() for k in ("UKOŃCZONO", "PRZERWANO", "DO WERYFIKACJI"))
            for i in range(total_items)
        )
        self.clear_q_btn.setEnabled(has_finished)

    def _toggle_analysis(self):
        if self.worker and self.worker.isRunning():
            self._stop_analysis()
        else:
            self._start_analysis()

    def _start_analysis(self):
        if not self.video_queue:
            return
        self.is_interrupted = False

        selected_items = self.queue_list.selectedItems()
        if selected_items:
            start_path = selected_items[0].data(Qt.UserRole)
            if start_path in self.video_queue:
                start_idx = self.video_queue.index(start_path)
                queue_to_process = self.video_queue[start_idx:]
            else:
                queue_to_process = list(self.video_queue)
        else:
            queue_to_process = list(self.video_queue)

        if not queue_to_process:
            return

        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            p = item.data(Qt.UserRole)
            if p in queue_to_process and "PRZERWANO" in item.text():
                item.setText(self._format_item_text(os.path.basename(p), "OCZEKUJE"))
                item.setForeground(QColor("#8b949e"))
        self.start_btn.setText("PRZERWIJ ANALIZĘ")
        self.start_btn.setObjectName("btnStopAnalysis")
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        self.start_btn.setEnabled(True)
        self.worker = VideoWorker(queue_to_process, self.engine)
        self.worker.progress_changed.connect(self._on_progress)
        self.worker.log_message.connect(self._add_log_entry)
        self.worker.frame_question_captured.connect(self._display_question_frame)
        self.worker.frame_resolved_captured.connect(self._display_resolved_frame)
        self.worker.question_resolved.connect(self.question_resolved_signal.emit)
        self.worker.video_started.connect(self._on_video_started)
        self.worker.video_finished.connect(self._on_video_finished)
        self.worker.finished.connect(self._on_analysis_ended)
        self.worker.start()


    def _on_video_started(self, path):
        norm_path = os.path.normpath(path)
        base_name = os.path.basename(norm_path)
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            if os.path.normpath(item.data(Qt.UserRole)) == norm_path:
                item.setText(self._format_item_text(base_name, "W TRAKCIE..."))
                item.setForeground(QColor("#00c8ff"))
                self.queue_list.scrollToItem(item, self.queue_list.ScrollHint.PositionAtCenter)
                break
        self._update_queue_buttons_state()

    def _stop_analysis(self):
        if self.worker:
            self.is_interrupted = True
            self._add_log_entry("--:--", "INFO", "Zatrzymywanie analizy...")
            for i in range(self.queue_list.count()):
                item = self.queue_list.item(i)
                if "W TRAKCIE" in item.text():
                    path = item.data(Qt.UserRole)
                    item.setText(self._format_item_text(os.path.basename(path), "PRZERWANO"))
                    item.setForeground(QColor("#f85149"))
                    break
            self.worker.stop()
            self.start_btn.setEnabled(False)

    def _on_analysis_ended(self):
        self.start_btn.setText("▶ ROZPOCZNIJ ANALIZĘ")
        self.start_btn.setObjectName("btnStartAnalysis")
        self.start_btn.style().unpolish(self.start_btn)
        self.start_btn.style().polish(self.start_btn)
        self.start_btn.setEnabled(len(self.video_queue) > 0)
        self._update_queue_buttons_state()

    def _on_video_finished(self, path, unresolved_count=0):
        if self.is_interrupted:
            return
        norm_path = os.path.normpath(path)
        if norm_path in self.video_queue:
            self.video_queue.remove(norm_path)
        base_name = os.path.basename(norm_path)
        for i in range(self.queue_list.count()):
            item = self.queue_list.item(i)
            if os.path.normpath(item.data(Qt.UserRole)) == norm_path:
                if unresolved_count == 0:
                    item.setText(self._format_item_text(base_name, "UKOŃCZONO"))
                    item.setForeground(QColor("#00ff88"))
                else:
                    item.setText(self._format_item_text(base_name, f"DO WERYFIKACJI ({unresolved_count})"))
                    item.setForeground(QColor("#e3b341"))
                break
        if len(self.video_queue) == 0:
            self.progress_bar.setValue(100)
        self._update_queue_buttons_state()

    def _add_log_entry(self, time_str: str, entry_type: str, text: str):
        card = QFrame()
        card.setObjectName("logItemCard")
        if entry_type == "UNRESOLVED":
            card.setProperty("unresolved", True)

        v_box = QVBoxLayout(card)
        v_box.setContentsMargins(10, 8, 10, 8)
        v_box.setSpacing(4)
        header = QHBoxLayout()
        header.setSpacing(8)
        time_lbl = QLabel(time_str)
        time_lbl.setObjectName("logTimeBadge")
        header.addWidget(time_lbl)

        status_tag = QLabel()
        if entry_type == "QUESTION":
            status_tag.setText("WYKRYTO PYTANIE")
            status_tag.setObjectName("logTagQuestion")
        elif entry_type == "RESOLVE":
            status_tag.setText("POPRAWNA ODPOWIEDŹ")
            status_tag.setObjectName("logTagResolve")
        elif entry_type == "UNRESOLVED":
            status_tag.setText("DO WERYFIKACJI")
            status_tag.setObjectName("logTagUnresolved")
        else:
            status_tag.setText("STATUS PROCESU")
            status_tag.setObjectName("logTagInfo")
        header.addWidget(status_tag)
        header.addStretch()
        v_box.addLayout(header)

        msg = QLabel(text)
        if entry_type == "QUESTION":
            msg.setObjectName("logTextQuestion")
        elif entry_type == "RESOLVE":
            msg.setObjectName("logTextResolve")
        elif entry_type == "UNRESOLVED":
            msg.setObjectName("logTextUnresolved")
        else:
            msg.setObjectName("logTextInfo")
        msg.setWordWrap(True)
        v_box.addWidget(msg)

        self.log_layout.insertWidget(0, card)
        self.btn_clear_log.setEnabled(True)

    def _clear_log(self):
        while self.log_layout.count() > 1:
            item = self.log_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.btn_clear_log.setEnabled(False)

    def _add_video_to_queue(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Wybierz pliki wideo", "", "Pliki wideo (*.mp4 *.mkv *.avi)"
        )
        bold_font = QFont("Segoe UI", 10, QFont.Bold)
        for f in files:
            norm_f = os.path.normpath(f)
            if norm_f not in self.video_queue:
                self.video_queue.append(norm_f)
                base_name = os.path.basename(norm_f)
                item = QListWidgetItem(self._format_item_text(base_name, "OCZEKUJE"))
                item.setFont(bold_font)
                item.setData(Qt.UserRole, norm_f)
                item.setToolTip(base_name)
                item.setForeground(QColor("#8b949e"))
                self.queue_list.addItem(item)
        self.start_btn.setEnabled(len(self.video_queue) > 0)
        self._update_queue_buttons_state()

    def _remove_selected_from_queue(self):
        selected_items = self.queue_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        file_path = item.data(Qt.UserRole)
        if self.worker and self.worker.isRunning():
            if getattr(self.worker, 'current_video_path', None) == file_path:
                return

        if file_path in self.video_queue:
            self.video_queue.remove(file_path)

        row = self.queue_list.row(item)
        self.queue_list.takeItem(row)
        self.queue_list.clearSelection()
        self.queue_list.setCurrentItem(None)
        self.start_btn.setEnabled(len(self.video_queue) > 0)
        self._update_queue_buttons_state()

    def _clear_finished_from_queue(self):
        for i in reversed(range(self.queue_list.count())):
            item = self.queue_list.item(i)
            file_path = item.data(Qt.UserRole)
            if file_path not in self.video_queue:
                self.queue_list.takeItem(i)
        self.queue_list.clearSelection()
        self.queue_list.setCurrentItem(None)
        self._update_queue_buttons_state()

    def _on_progress(self, current, total):
        if total > 0:
            self.progress_bar.setValue(int((current / total) * 100))

    def _display_question_frame(self, frame_bgr):
        pix = self._cv_to_pixmap(frame_bgr)
        self.img_question.setPixmap(pix.scaled(self.img_question.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _display_resolved_frame(self, frame_bgr):
        pix = self._cv_to_pixmap(frame_bgr)
        self.img_resolved.setPixmap(pix.scaled(self.img_resolved.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    @staticmethod
    def _cv_to_pixmap(frame_bgr) -> QPixmap:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)