from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFileDialog
)

from core.vision_engine import VisionEngine
from database.db_manager import DatabaseManager
from exporters.export_service import ExportService
from ui.dialogs.info_dialog import InfoDialog
from ui.views.database_view import DatabaseView
from ui.views.video_analysis_view import VideoAnalysisView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Milionerzy OCR")
        self.resize(1340, 880)

        self.db = DatabaseManager()
        self.engine = VisionEngine()

        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        central.setObjectName("centralView")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        nav_bar = QHBoxLayout()
        title_lbl = QLabel("MILIONERZY OCR")
        title_lbl.setObjectName("appLogo")
        nav_bar.addWidget(title_lbl)
        nav_bar.addSpacing(30)

        self.btn_nav_video = QPushButton("ANALIZA WIDEO")
        self.btn_nav_video.setObjectName("btnTopAction")
        self.btn_nav_video.clicked.connect(lambda: self._switch_view(0))
        nav_bar.addWidget(self.btn_nav_video)

        initial_count = self.db.count()
        self.btn_nav_db = QPushButton(f"BAZA PYTAŃ ({initial_count})")
        self.btn_nav_db.setObjectName("btnTopAction")
        self.btn_nav_db.clicked.connect(lambda: self._switch_view(1))
        nav_bar.addWidget(self.btn_nav_db)

        nav_bar.addStretch()

        self.btn_export = QPushButton("EKSPORTUJ")
        self.btn_export.setObjectName("btnExportAction")
        self.btn_export.clicked.connect(self._export_menu)
        self.btn_export.setVisible(False)
        nav_bar.addWidget(self.btn_export)

        root.addLayout(nav_bar)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self.view_video = VideoAnalysisView(self.engine)
        self.view_video.question_resolved_signal.connect(self._on_question_resolved)
        self.stack.addWidget(self.view_video)

        self.view_db = DatabaseView(self.db)
        self.view_db.records_count_changed.connect(lambda cnt: self.btn_nav_db.setText(f"BAZA PYTAŃ ({cnt})"))
        self.stack.addWidget(self.view_db)

        self._switch_view(0)

    def _switch_view(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.btn_nav_video.setStyleSheet("border-color: #00c8ff; color: #00c8ff;")
            self.btn_nav_db.setStyleSheet("")
            self.btn_export.setVisible(False)
        else:
            self.btn_nav_db.setStyleSheet("border-color: #00c8ff; color: #00c8ff;")
            self.btn_nav_video.setStyleSheet("")
            self.btn_export.setVisible(True)
            self.view_db.refresh_cards()

    def _on_question_resolved(self, entry):
        self.db.add_entry(entry)
        self.btn_nav_db.setText(f"BAZA PYTAŃ ({self.db.count()})")

    def _export_menu(self):
        pool = self.view_db.get_export_candidates()
        entries_to_export = [e for e in pool if e.poprawna_odpowiedz]

        if not entries_to_export:
            dialog = InfoDialog(
                title="Brak pytań do eksportu",
                message="Wszystkie wybrane pytania nie posiadają zaznaczonej poprawnej odpowiedzi i nie mogą zostać wyeksportowane.",
                parent=self
            )
            dialog.exec()
            return

        skipped = len(pool) - len(entries_to_export)
        if skipped > 0:
            dialog = InfoDialog(
                title="Pominięto pytania",
                message=f"Pominięto pytania bez poprawnej odpowiedzi ({skipped}).",
                parent=self
            )
            dialog.exec()

        filters = (
            "Dokument PDF (*.pdf);;"
            "Dokument programu Word (*.docx);;"
            "Skoroszyt programu Microsoft Excel (*.xlsx);;"
            "Plik wartości rozdzielanych przecinkami CSV (*.csv);;"
            "Fiszki programu Anki (*.txt)"
        )

        dialog = QFileDialog(self, "Eksportuj pytania", "arkusz_milionerzy", filters)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setDefaultSuffix("pdf")

        if not dialog.exec():
            return

        selected_files = dialog.selectedFiles()
        if not selected_files:
            return

        path = selected_files[0]
        selected_filter = dialog.selectedNameFilter()

        if "Dokument PDF" in selected_filter or path.endswith(".pdf"):
            ExportService.to_pdf(entries_to_export, path)
        elif "Dokument programu Word" in selected_filter or path.endswith(".docx"):
            if not path.endswith(".docx"):
                path += ".docx"
            ExportService.to_docx(entries_to_export, path)
        elif "Skoroszyt programu Microsoft Excel" in selected_filter or path.endswith(".xlsx"):
            ExportService.to_excel(entries_to_export, path)
        elif "Plik wartości rozdzielanych przecinkami" in selected_filter or path.endswith(".csv"):
            ExportService.to_csv(entries_to_export, path)
        else:
            ExportService.to_anki_txt(entries_to_export, path)