import json
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, default=Path(__file__).resolve().parent / 'data' / 'DanhSachSinhVien.json')
args = parser.parse_args()

with open(args.input, 'r', encoding='utf-8') as f:
    data = json.load(f)

classes = set()
for s in data:
    classes.add(s.get('academic_class'))

print("Total students:", len(data))
print("Classes:", classes)
