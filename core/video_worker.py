import os
import uuid
import cv2
import numpy as np
import difflib
from PySide6.QtCore import QThread, Signal
from core.vision_engine import VisionEngine
from database.models import QuestionEntry
from core.config import DETECTION_THRESHOLD_GREEN

def is_same_question(q1: str, q2: str) -> bool:
    if not q1 or not q2:
        return False
    s1 = " ".join(q1.lower().split())
    s2 = " ".join(q2.lower().split())
    return difflib.SequenceMatcher(None, s1, s2).ratio() >= 0.70

def normalize_station(station_name: str | None) -> str:
    if station_name and "POLSAT" in str(station_name).upper():
        return "POLSAT"
    return "TVN"


class VideoWorker(QThread):
    progress_changed = Signal(int, int)
    question_detected = Signal(dict)
    question_resolved = Signal(QuestionEntry)
    frame_question_captured = Signal(np.ndarray)
    frame_resolved_captured = Signal(np.ndarray)
    log_message = Signal(str, str, str)
    video_finished = Signal(str, int)
    video_started = Signal(str)

    def __init__(self, video_queue: list, engine: VisionEngine, captures_dir: str = "captures"):
        super().__init__()
        self.video_queue = video_queue
        self.engine = engine
        self.captures_dir = captures_dir
        self.is_running = True
        self.current_video_path = None

    def stop(self):
        self.is_running = False

    @staticmethod
    def frame_time_str(cap, fps: float) -> str:
        pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        sec = int(pos / fps) if fps > 0 else 0
        return f"{sec // 60:02d}:{sec % 60:02d}"

    def run(self):
        queue_snapshot = list(self.video_queue)
        for video_path in queue_snapshot:
            if not self.is_running:
                break
            self.current_video_path = video_path
            self.video_started.emit(video_path)
            self.log_message.emit("00:00", "INFO", f"Rozpoczęto analizę: {os.path.basename(video_path)}")
            unresolved = self._process_single_video(video_path)
            self.video_finished.emit(video_path, unresolved or 0)
        self.current_video_path = None

    def _emit_unresolved(self, pending_q: dict, station: str, reason_log: str):
        actual_station = normalize_station(pending_q.get("station") or station)
        entry = QuestionEntry(
            id=str(uuid.uuid4())[:8],
            pytanie=str(pending_q.get("pytanie", "")),
            warianty=dict(pending_q.get("warianty", {})),
            poprawna_odpowiedz=None,
            screenshot_path=pending_q.get("screenshot_path"),
            station=actual_station
        )
        self.question_resolved.emit(entry)
        self.log_message.emit(
            str(pending_q.get("time_captured", "--:--")),
            "UNRESOLVED",
            f"{reason_log}: \"{str(pending_q.get('pytanie', ''))[:45]}...\""
        )

    def _process_single_video(self, video_path: str):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            self.log_message.emit("00:00", "INFO", f"Błąd otwarcia pliku: {os.path.basename(video_path)}")
            return 0

        raw_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        raw_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        self.engine.set_scale(raw_width, raw_height)

        station_locked = False
        current_station = None

        STEP_SEARCH = max(1, int(fps * 1.5))
        STEP_WAIT_ANSWERS = max(1, int(fps * 0.8))
        STEP_POLL_ANSWER = max(1, int(fps * 0.35))

        state = "SEARCH_QUESTION"
        pending_question = None
        wait_answers_frames = 0
        poll_frames = 0
        frame_counter = 0
        bar_missing_frames = 0

        questions_found = 0
        unresolved_count = 0

        while cap.isOpened() and self.is_running:
            pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            self.progress_changed.emit(pos, total_frames)

            if state == "SEARCH_QUESTION":
                if not cap.grab():
                    break
                frame_counter += 1
                if frame_counter % STEP_SEARCH == 0:
                    ret, frame = cap.retrieve()
                    if not ret or frame is None:
                        continue

                    if not station_locked:
                        matched = self.engine.check_station_by_boxes(frame)
                        if matched:
                            current_station = matched
                            self.engine.apply_preset(current_station)
                            self.engine.load_templates_for_preset(current_station)
                            station_locked = True
                          #  self.log_message.emit(time_str, "INFO", f"Wykryto format stacji: {current_station}")
                            state = "WAIT_FOR_ALL_ANSWERS"
                            wait_answers_frames = 0
                            bar_missing_frames = 0
                    else:
                        bars_ok = self.engine.are_all_5_bars_visible(frame)
                        has_text = self.engine.has_question_text(frame) if bars_ok else False
                        if bars_ok and has_text:
                            state = "WAIT_FOR_ALL_ANSWERS"
                            wait_answers_frames = 0
                            bar_missing_frames = 0

            elif state == "WAIT_FOR_ALL_ANSWERS":
                if not cap.grab():
                    break
                wait_answers_frames += 1
                if wait_answers_frames % STEP_WAIT_ANSWERS == 0:
                    ret, frame = cap.retrieve()
                    if not ret or frame is None:
                        continue
                    time_str = self.frame_time_str(cap, fps)
                    if not self.engine.is_bar_present(frame):
                        bar_missing_frames += 1
                        if bar_missing_frames > int(fps * 2.0 / STEP_WAIT_ANSWERS):
                            state = "SEARCH_QUESTION"
                            bar_missing_frames = 0
                            frame_counter = 0
                        continue
                    else:
                        bar_missing_frames = 0
                    if self.engine.count_letters_present(frame) < 4:
                        continue
                    self.engine.auto_save_templates_if_missing(frame, current_station)
                    q_text, opts = self.engine.parse_question_card(frame)
                    if self.engine.is_qualification_question(q_text):
                        state = "SEARCH_QUESTION"
                        continue
                    if not self.engine.is_real_question_ocr(q_text):
                        continue
                    if self.engine.count_filled_answers(opts) == 4:
                        if pending_question and is_same_question(pending_question["pytanie"], q_text):
                            state = "WAIT_FOR_ANSWER_RESOLUTION"
                            poll_frames = 0
                            continue
                        if pending_question is not None:
                            self._emit_unresolved(pending_question, current_station, "Brak rozstrzygnięcia przed kolejnym pytaniem")
                            questions_found += 1
                            unresolved_count += 1
                        q_screenshot_name = f"q_{uuid.uuid4().hex[:8]}.jpg"
                        q_screenshot_path = os.path.join(self.captures_dir, q_screenshot_name)
                        cv2.imwrite(q_screenshot_path, frame)
                        pending_question = {
                            "time_captured": time_str,
                            "pytanie": q_text,
                            "warianty": opts,
                            "screenshot_path": q_screenshot_path,
                            "station": normalize_station(current_station)
                        }
                        self.question_detected.emit(pending_question)
                        self.frame_question_captured.emit(frame.copy())
                        self.log_message.emit(time_str, "QUESTION", f"{q_text}")
                        state = "WAIT_FOR_ANSWER_RESOLUTION"
                        poll_frames = 0
                        bar_missing_frames = 0
            elif state == "WAIT_FOR_ANSWER_RESOLUTION":
                if not cap.grab():
                    break
                poll_frames += 1
                if poll_frames % STEP_POLL_ANSWER == 0:
                    ret, frame = cap.retrieve()
                    if not ret or frame is None:
                        continue
                    time_str = self.frame_time_str(cap, fps)
                    if not self.engine.is_bar_present(frame):
                        bar_missing_frames += 1
                        if bar_missing_frames > int(fps * 10.0 / STEP_POLL_ANSWER):
                            state = "SEARCH_QUESTION"
                            bar_missing_frames = 0
                            frame_counter = 0
                        continue
                    else:
                        bar_missing_frames = 0
                    _, best_letter, best_ratio = self.engine.evaluate_green_scores(frame)
                    if best_letter and best_ratio >= DETECTION_THRESHOLD_GREEN:
                        ans_screenshot_name = f"ans_{uuid.uuid4().hex[:8]}.jpg"
                        ans_screenshot_path = os.path.join(self.captures_dir, ans_screenshot_name)
                        cv2.imwrite(ans_screenshot_path, frame)
                        old_q_shot = pending_question.get("screenshot_path")
                        if old_q_shot and os.path.exists(old_q_shot) and old_q_shot != ans_screenshot_path:
                            try:
                                os.remove(old_q_shot)
                            except OSError:
                                pass
                        db_station = "POLSAT" if (current_station and "POLSAT" in current_station) else "TVN"
                        entry = QuestionEntry(
                            id=str(uuid.uuid4())[:8],
                            pytanie=pending_question["pytanie"],
                            warianty=pending_question["warianty"],
                            poprawna_odpowiedz=best_letter,
                            screenshot_path=ans_screenshot_path,
                            station=db_station
                        )
                        self.question_resolved.emit(entry)
                        self.frame_resolved_captured.emit(frame.copy())
                        self.log_message.emit(
                            time_str, "RESOLVE",
                            f"Zatwierdzono [{best_letter}]: {pending_question['warianty'].get(best_letter, '')}"
                        )
                        questions_found += 1
                        pending_question = None
                        state = "WAIT_FOR_BAR_DISAPPEAR"
                        bar_missing_frames = 0
            elif state == "WAIT_FOR_BAR_DISAPPEAR":
                if not cap.grab():
                    break
                poll_frames += 1
                if poll_frames % STEP_POLL_ANSWER == 0:
                    ret, frame = cap.retrieve()
                    if not ret or frame is None:
                        continue
                    if not self.engine.is_bar_present(frame):
                        bar_missing_frames += 1
                        if bar_missing_frames >= 2:
                            state = "SEARCH_QUESTION"
                            bar_missing_frames = 0
                            frame_counter = 0
                    else:
                        bar_missing_frames = 0
        if pending_question is not None:
            self._emit_unresolved(pending_question, current_station, "Koniec wideo – brak rozstrzygnięcia")
            questions_found += 1
            unresolved_count += 1
        cap.release()
        summary = f"Ukończono: {os.path.basename(video_path)} · Znaleziono pytań: {questions_found}"
        if unresolved_count > 0:
            summary += f" (do weryfikacji: {unresolved_count})"
        total_sec = int(total_frames / fps) if fps > 0 else 0
        end_time_str = f"{total_sec // 60:02d}:{total_sec % 60:02d}"
        self.log_message.emit(end_time_str, "INFO", summary)
        return unresolved_count