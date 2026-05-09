import pandas as pd
import requests
import os
import re

CSV_FILE = "students.csv"
OUTPUT_FOLDER = "students"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def extract_file_id(link):
    match = re.search(r"id=([^&]+)", link)
    if match:
        return match.group(1)
    return None

def download_image(file_id, student_id):
    path = os.path.join(OUTPUT_FOLDER, f"{student_id}.jpg")

    # لو الصورة موجودة خلاص → skip
    if os.path.exists(path):
        print(f"Skipped {student_id} (already exists)")
        return

    url = f"https://drive.google.com/uc?export=download&id={file_id}"

    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200 and "image" in response.headers.get("Content-Type", ""):
            with open(path, "wb") as f:
                f.write(response.content)
            print(f"Downloaded {student_id}")
        else:
            print(f"Failed {student_id}")
    except Exception as e:
        print(f"Error {student_id}: {e}")

df = pd.read_csv(CSV_FILE, encoding="utf-8-sig")

# تنظيف الأعمدة (احتياطي)
df.columns = df.columns.str.strip()

# إزالة التكرار
df = df.drop_duplicates(subset=["Student ID"])

for _, row in df.iterrows():
    student_id = row["Student ID"]
    link = row["Photo Link"]

    # لو الـ ID فاضي
    if pd.isna(student_id):
        print("Skipping row (no student ID)")
        continue

    student_id = int(student_id)

    # لو اللينك فاضي
    if pd.isna(link):
        print(f"Skipping {student_id} (no link)")
        continue

    file_id = extract_file_id(link)
    if file_id:
        download_image(file_id, student_id)
    else:
        print(f"Invalid link for {student_id}")