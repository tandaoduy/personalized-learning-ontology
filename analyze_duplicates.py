import json
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, default=Path(__file__).resolve().parent / 'data' / 'DanhSachSinhVien.json')
args = parser.parse_args()

with open(args.input, 'r', encoding='utf-8') as f:
    data = json.load(f)

has_duplicates = False
for s in data:
    codes = [c['course_code'] for c in s.get('course_grades', [])]
    if len(codes) != len(set(codes)):
        print(f"Student {s['student_id']} has duplicate courses: {codes}")
        has_duplicates = True
        break
if not has_duplicates:
    print("No duplicate courses found in course_grades.")
