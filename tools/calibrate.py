import sys
import os
import cv2
from core.vision_engine import VisionEngine

def calibrate(video_input: str, target_sec: float, profile: str = "TVN"):
    if video_input.isdigit():
        video_path = f"odcinek{video_input}.mp4"
    else:
        video_path = video_input
    if not os.path.exists(video_path):
        print(f"[BŁĄD] Plik nie istnieje: {video_path}")
        return
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[BŁĄD] Nie można otworzyć wideo: {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    raw_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    raw_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    target_frame = int(target_sec * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        print(f"[BŁĄD] Nie udało się odczytać klatki z sekundy {target_sec}")
        return

    profile_upper = profile.upper()
    engine = VisionEngine()
    engine.apply_preset(profile_upper)
    engine.set_scale(raw_w, raw_h)
    engine.load_templates_for_preset(profile_upper)
    os.makedirs("../captures/calibration", exist_ok=True)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    raw_out = f"captures/calibration/{base_name}_{int(target_sec)}s_raw.jpg"
    cv2.imwrite(raw_out, frame)
    debug_frame = frame.copy()
    letters_detected = engine.count_letters_present(frame)

    if engine.question_box:
        y1, x1, y2, x2 = engine.question_box
        ry1, ry2 = int(y1 * engine.scale_y), int(y2 * engine.scale_y)
        rx1, rx2 = int(x1 * engine.scale_x), int(x2 * engine.scale_x)
        cv2.rectangle(debug_frame, (rx1, ry1), (rx2, ry2), (255, 200, 0), 2)
        cv2.putText(debug_frame, "PYTANIE", (rx1, ry1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
    if hasattr(engine, 'letter_boxes') and engine.letter_boxes:
        for letter, box in engine.letter_boxes.items():
            y1, x1, y2, x2 = box
            ry1, ry2 = int(y1 * engine.scale_y), int(y2 * engine.scale_y)
            rx1, rx2 = int(x1 * engine.scale_x), int(x2 * engine.scale_x)
            cv2.rectangle(debug_frame, (rx1, ry1), (rx2, ry2), (0, 255, 0), 2)
            cv2.putText(debug_frame, letter, (rx1, ry1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    if hasattr(engine, 'content_boxes') and engine.content_boxes:
        for letter, box in engine.content_boxes.items():
            y1, x1, y2, x2 = box
            ry1, ry2 = int(y1 * engine.scale_y), int(y2 * engine.scale_y)
            rx1, rx2 = int(x1 * engine.scale_x), int(x2 * engine.scale_x)
            cv2.rectangle(debug_frame, (rx1, ry1), (rx2, ry2), (255, 100, 0), 1)
    debug_out = f"captures/calibration/{base_name}_{int(target_sec)}s_debug_{profile_upper}.jpg"
    cv2.imwrite(debug_out, debug_frame)
    print(f"\n=== WYNIK KALIBRACJI ({profile_upper}) ===")
    print(f"Plik: {video_path} (sekunda: {target_sec}s, wymiary: {int(raw_w)}x{int(raw_h)})")
    print(f"Współczynniki skali: scale_x={engine.scale_x:.3f}, scale_y={engine.scale_y:.3f}")
    print(f"Wykryte litery A-D: {letters_detected}/4")
    print(f"Podgląd boxów zapisano w: {debug_out}\n")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Użycie: python calibrate.py <ścieżka/numer_odcinka> <sekunda> [profil]")
        sys.exit(1)
    vid = sys.argv[1]
    sec = float(sys.argv[2])
    prof = sys.argv[3] if len(sys.argv) > 3 else "TVN"
    calibrate(vid, sec, prof)