import os
import re

import cv2
import easyocr
import numpy as np

from core.config import (
    BASE_WIDTH,
    BASE_HEIGHT,
    LOWER_BLUE,
    UPPER_BLUE,
    LOWER_GREEN,
    UPPER_GREEN,
    LOWER_GOLD,
    UPPER_GOLD,
    DETECTION_THRESHOLD_BLUE,
    TEMPLATE_MATCH_THRESHOLD,
    OCR_SCALE,
    ELIMINATION_PATTERNS
)
from core.presets import PRESETS


class VisionEngine:
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = templates_dir
        os.makedirs(self.templates_dir, exist_ok=True)
        self.loaded_templates = {}
        self.scale_x = 1.0
        self.scale_y = 1.0

        self.has_qualification = False
        self.question_box = None
        self.bar_test_question = None
        self.letter_boxes = None
        self.content_boxes = None
        self.answers_band_y = None
        self.answers_band_x = None

        try:
            self.reader = easyocr.Reader(["pl"], gpu=True)
        except Exception:
            self.reader = easyocr.Reader(["pl"], gpu=False)

    def set_scale(self, width: float, height: float) -> None:
        self.scale_x = width / BASE_WIDTH
        self.scale_y = height / BASE_HEIGHT

    def apply_preset(self, name: str) -> None:
        if name not in PRESETS:
            raise ValueError(f"Nieznany preset profilu: {name}")
        p = PRESETS[name]
        self.has_qualification = p.get("HAS_QUALIFICATION", False)
        self.question_box = p["QUESTION_BOX"]
        self.bar_test_question = p["BAR_TEST_QUESTION"]
        self.letter_boxes = p["LETTER_BOXES"]
        self.content_boxes = p["CONTENT_BOXES"]
        self.answers_band_y = p["ANSWERS_BAND_Y"]
        self.answers_band_x = p["ANSWERS_BAND_X"]

    def crop_scaled(self, frame: np.ndarray, box_tuple: tuple) -> np.ndarray:
        y1, x1, y2, x2 = box_tuple
        ry1 = int(y1 * self.scale_y)
        ry2 = int(y2 * self.scale_y)
        rx1 = int(x1 * self.scale_x)
        rx2 = int(x2 * self.scale_x)
        return frame[ry1:ry2, rx1:rx2]

    def load_templates_for_preset(self, station: str) -> None:
        self.loaded_templates = {}
        for letter in ("A", "B", "C", "D"):
            path = os.path.join(self.templates_dir, f"{station.lower()}_{letter}.png")
            if os.path.exists(path):
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.loaded_templates[letter] = img

    def auto_save_templates_if_missing(self, frame_raw: np.ndarray, station: str) -> None:
        for letter in ("A", "B", "C", "D"):
            path = os.path.join(self.templates_dir, f"{station.lower()}_{letter}.png")
            if letter not in self.loaded_templates and not os.path.exists(path):
                crop = self.crop_scaled(frame_raw, self.letter_boxes[letter])
                if crop.size > 0:
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    cv2.imwrite(path, gray)
                    self.loaded_templates[letter] = gray

    def is_letter_present(self, frame_raw: np.ndarray, letter: str) -> bool:
        if not self.letter_boxes or letter not in self.letter_boxes:
            return False
        roi = self.crop_scaled(frame_raw, self.letter_boxes[letter])
        if roi.size == 0:
            return False
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        if letter in self.loaded_templates:
            tmpl = self.loaded_templates[letter]
            if roi_gray.shape[0] >= tmpl.shape[0] and roi_gray.shape[1] >= tmpl.shape[1]:
                res = cv2.matchTemplate(roi_gray, tmpl, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                return max_val >= TEMPLATE_MATCH_THRESHOLD

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask_o = cv2.inRange(hsv, np.array([10, 100, 100]), np.array([30, 255, 255]))
        _, mask_w = cv2.threshold(roi_gray, 130, 255, cv2.THRESH_BINARY)
        mask = cv2.bitwise_or(mask_o, mask_w)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            if cv2.contourArea(c) >= (20 * self.scale_y * self.scale_x):
                _, _, _, h = cv2.boundingRect(c)
                if h >= (10 * self.scale_y):
                    return True
        return False

    def count_letters_present(self, frame_raw: np.ndarray) -> int:
        return sum(1 for letter in self.letter_boxes.keys() if self.is_letter_present(frame_raw, letter))

    def check_station_by_boxes(self, frame_raw: np.ndarray) -> str | None:
        scores = {}

        for preset_name in ("TVN", "POLSAT_WIDE", "POLSAT_SLIM"):
            preset = PRESETS[preset_name]
            valid_letters = 0

            for letter, box in preset["LETTER_BOXES"].items():
                l_crop = self.crop_scaled(frame_raw, box)
                if l_crop.size == 0:
                    continue

                hsv = cv2.cvtColor(l_crop, cv2.COLOR_BGR2HSV)
                l_mask = cv2.inRange(hsv, LOWER_GOLD, UPPER_GOLD)
                cnts, _ = cv2.findContours(l_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                has_letter = any(
                    (10 * self.scale_y) <= cv2.boundingRect(c)[3] <= (45 * self.scale_y)
                    and (4 * self.scale_x) <= cv2.boundingRect(c)[2] <= (40 * self.scale_x)
                    for c in cnts
                )
                if has_letter:
                    valid_letters += 1

            q_crop = self.crop_scaled(frame_raw, preset["QUESTION_BOX"])
            if q_crop.size == 0:
                continue

            gray_q = cv2.cvtColor(q_crop, cv2.COLOR_BGR2GRAY)
            _, thresh_q = cv2.threshold(gray_q, 180, 255, cv2.THRESH_BINARY)
            q_cnts, _ = cv2.findContours(thresh_q, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            has_q_text = sum(
                1 for c in q_cnts
                if (10 * self.scale_y) <= cv2.boundingRect(c)[3] <= (55 * self.scale_y)
            ) >= 8

            scores[preset_name] = valid_letters if has_q_text else 0

        best_preset, best_score = max(scores.items(), key=lambda item: item[1])
        if best_score >= 3:
            return best_preset
        return None

    def are_all_5_bars_visible(self, frame_raw: np.ndarray) -> bool:
        q_roi = self.crop_scaled(frame_raw, self.bar_test_question)
        if q_roi.size == 0:
            return False
        q_hsv = cv2.cvtColor(q_roi, cv2.COLOR_BGR2HSV)
        q_blue = cv2.inRange(q_hsv, LOWER_BLUE, UPPER_BLUE)
        if (cv2.countNonZero(q_blue) / q_blue.size) < DETECTION_THRESHOLD_BLUE:
            return False

        for letter, box in self.content_boxes.items():
            box_sample = self.crop_scaled(frame_raw, box)
            if box_sample.size == 0:
                return False
            h, w = box_sample.shape[:2]
            mid_y, mid_x = h // 2, w // 2
            dy = max(2, int(10 * self.scale_y))
            dx = max(4, int(40 * self.scale_x))
            center_crop = box_sample[max(0, mid_y - dy): min(h, mid_y + dy), max(0, mid_x - dx): min(w, mid_x + dx)]
            if center_crop.size == 0:
                return False
            b_hsv = cv2.cvtColor(center_crop, cv2.COLOR_BGR2HSV)
            b_blue = cv2.inRange(b_hsv, LOWER_BLUE, UPPER_BLUE)
            if (cv2.countNonZero(b_blue) / b_blue.size) < 0.30:
                return False
        return True

    def has_question_text(self, frame_raw: np.ndarray) -> bool:
        roi = self.crop_scaled(frame_raw, self.bar_test_question)
        if roi.size == 0:
            return False
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        letter_like_contours = sum(
            1 for c in contours
            if (10 * self.scale_y) < cv2.boundingRect(c)[3] < (55 * self.scale_y)
            and (4 * self.scale_x) < cv2.boundingRect(c)[2] < (80 * self.scale_x)
        )
        return letter_like_contours >= 8

    def is_bar_present(self, frame_raw: np.ndarray) -> bool:
        roi = self.crop_scaled(frame_raw, self.bar_test_question)
        if roi.size == 0:
            return False
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask_blue = cv2.inRange(hsv, LOWER_BLUE, UPPER_BLUE)
        return (cv2.countNonZero(mask_blue) / mask_blue.size) >= DETECTION_THRESHOLD_BLUE

    @staticmethod
    def is_qualification_question(text: str) -> bool:
        t = text.lower().strip()
        return any(re.search(pat, t) for pat in ELIMINATION_PATTERNS)

    @staticmethod
    def clean_answer_text(text: str) -> str:
        cleaned = re.sub(r"^([ABCD3oO])\s*[:.)]\s*", "", text).strip()
        cleaned = re.sub(r"^[^\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+", "", cleaned).strip()
        return cleaned if cleaned else text.strip()

    @staticmethod
    def _preprocess_roi(img_crop: np.ndarray) -> np.ndarray:
        return cv2.resize(img_crop, (0, 0), fx=OCR_SCALE, fy=OCR_SCALE, interpolation=cv2.INTER_CUBIC)

    @staticmethod
    def _join_readtext_results(results) -> str:
        lines = [item[1].strip() for item in results if item[2] > 0.30]
        return " ".join(lines).strip()

    def parse_question_card(self, frame_raw: np.ndarray) -> tuple[str, dict]:
        q_roi = self.crop_scaled(frame_raw, self.question_box)
        q_processed = self._preprocess_roi(q_roi)
        q_results = self.reader.readtext(q_processed)
        q_text = self._join_readtext_results(q_results)
        if "?" in q_text:
            q_text = q_text[: q_text.index("?") + 1]

        answers = {}
        for letter, box in self.content_boxes.items():
            ans_roi = self.crop_scaled(frame_raw, box)
            ans_processed = self._preprocess_roi(ans_roi)
            ans_results = self.reader.readtext(ans_processed)
            answers[letter] = self.clean_answer_text(self._join_readtext_results(ans_results))

        return q_text, answers

    def evaluate_green_scores(self, frame_raw: np.ndarray) -> tuple[dict, str | None, float]:
        green_scores = {}
        for letter, box in self.content_boxes.items():
            roi = self.crop_scaled(frame_raw, box)
            if roi.size == 0:
                continue
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            mask_g = cv2.inRange(hsv, LOWER_GREEN, UPPER_GREEN)
            ratio = cv2.countNonZero(mask_g) / mask_g.size
            green_scores[letter] = ratio

        best_letter = max(green_scores, key=green_scores.get) if green_scores else None
        best_ratio = green_scores.get(best_letter, 0.0)
        return green_scores, best_letter, best_ratio

    @staticmethod
    def is_real_question_ocr(q_text: str) -> bool:
        if not q_text:
            return False
        q_clean = q_text.strip()
        return sum(1 for c in q_clean if c.isalpha()) >= 3

    @staticmethod
    def count_filled_answers(opts: dict) -> int:
        return sum(1 for k in ("A", "B", "C", "D") if opts.get(k, "").strip())