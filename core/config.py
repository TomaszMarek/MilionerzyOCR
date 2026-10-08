import numpy as np

BASE_WIDTH = 1920
BASE_HEIGHT = 1080

LOWER_BLUE = np.array([95, 70, 30])
UPPER_BLUE = np.array([135, 255, 255])

LOWER_GREEN = np.array([35, 70, 70])
UPPER_GREEN = np.array([85, 255, 255])

LOWER_GOLD = np.array([10, 80, 90])
UPPER_GOLD = np.array([32, 255, 255])

DETECTION_THRESHOLD_BLUE = 0.35
DETECTION_THRESHOLD_GREEN = 0.07
TEMPLATE_MATCH_THRESHOLD = 0.60
OCR_SCALE = 1.2

ELIMINATION_PATTERNS = [
    r"\buporządkuj\b",
    r"\bułóż\b",
    r"\buszereguj\b",
    r"\bod naj\w+\b",
    r"\bw kolejności\b",
    r"\bchronologicznie\b",
    r"\bkolejno\b",
    r"\bwymień w kolejności\b",
]