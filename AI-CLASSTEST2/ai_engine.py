import cv2
from deepface import DeepFace
import pandas as pd
from datetime import datetime
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_CANDIDATES = [
    os.path.join(BASE_DIR, "student_list_translated.csv"),
    os.path.join(os.path.dirname(BASE_DIR), "student_list_translated.csv"),
]

for csv_path in CSV_CANDIDATES:
    if os.path.exists(csv_path):
        break
else:
    raise FileNotFoundError("student_list_translated.csv was not found in the app folder or workspace root")

students_df = pd.read_csv(csv_path, encoding="utf-8-sig")
students_df.columns = students_df.columns.str.strip()

id_to_name = {
    int(row["Student ID"]): row["Student Name"]
    for _, row in students_df.iterrows()
    if not pd.isna(row["Student ID"])
}

CSV_FILE = os.path.join(BASE_DIR, "emotion_log.csv")
DB_PATH = os.path.join(BASE_DIR, "students")
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "0")
LECTURE_ID = "L1"

FONT_PATH = "arial.ttf"   # لو مش موجود عندك قولى

if not os.path.exists(CSV_FILE):
    pd.DataFrame(
        columns=["Student_ID", "Time", "Emotion", "Confidence", "Lecture_ID"]
    ).to_csv(CSV_FILE, index=False)

def open_camera(source):
    if source.lower() == "auto":
        for idx in [0, 1, 2, 3]:
            cam = cv2.VideoCapture(idx)
            ok, _ = cam.read()
            if ok:
                return cam
            cam.release()
        return None

    if source.isdigit():
        cam = cv2.VideoCapture(int(source))
        ok, _ = cam.read()
        if ok:
            return cam
        cam.release()

    return None

cap = open_camera(CAMERA_SOURCE)

if cap is None:
    raise RuntimeError("Could not open camera")

print("AI Engine Started")
print("Press Q to Quit")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    try:
        results = DeepFace.analyze(
            frame,
            actions=["emotion"],
            enforce_detection=False,
            detector_backend="opencv",
            silent=True
        )

        if isinstance(results, dict):
            results = [results]

        for res in results:
            x = res["region"]["x"]
            y = res["region"]["y"]
            w = res["region"]["w"]
            h = res["region"]["h"]

            try:
                identities = DeepFace.find(
                    img_path=frame,
                    db_path=DB_PATH,
                    enforce_detection=False,
                    detector_backend="opencv",
                    model_name="Facenet",
                    distance_metric="cosine",
                    silent=True
                )

                if len(identities) > 0 and not identities[0].empty:
                    best_match = identities[0].sort_values("distance").iloc[0]

                    print("Distance:", best_match["distance"])

                    if best_match["distance"] > 0.4:
                        name = "Not Registered"
                    else:
                        matched_path = best_match["identity"]
                        student_id = os.path.basename(matched_path).split(".")[0]

                        try:
                            student_id = int(student_id)
                            name = id_to_name.get(student_id, str(student_id))
                        except:
                            name = str(student_id)
                else:
                    name = "Not Registered"

            except Exception as e:
                print("Recognition Error:", e)
                name = "Not Registered"

            emotion = res["dominant_emotion"].capitalize()
            confidence = round(res["emotion"][res["dominant_emotion"]] / 100, 2)

            row = [[
                name,
                datetime.now().strftime("%H:%M:%S"),
                emotion,
                confidence,
                LECTURE_ID
            ]]

            pd.DataFrame(row).to_csv(
                CSV_FILE,
                mode="a",
                header=False,
                index=False
            )

            color = (0, 255, 0)
            if name == "Not Registered":
                color = (0, 0, 255)

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

            img_pil = Image.fromarray(frame)
            draw = ImageDraw.Draw(img_pil)

            try:
                font = ImageFont.truetype(FONT_PATH, 20)
            except:
                font = ImageFont.load_default()

            text = f"{name} ({emotion} {confidence})"

            draw.text((x, y - 25), text, font=font, fill=(0, 255, 0))

            frame = np.array(img_pil)

    except Exception as e:
        print("Analyze Error:", e)

    cv2.imshow("AI Classroom Monitor", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()