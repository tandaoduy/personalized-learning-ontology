"""Quality-gate a real Preference Dataset before any LTR experiment.

This tool intentionally does not synthesize labels.  It rejects records that
cannot be tied to a displayed, versioned, evidenced planning run and creates a
student-disjoint train/validation/test split only after that gate passes.
"""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path

REQUIRED = {"anonymous_student_id", "run_id", "source_manifest_hash", "displayed_order",
            "displayed_plan_ids", "plan_features_json", "evidence_ids_json", "action",
            "selected_plan_id", "adjustment_json", "actor_role", "created_at"}


def fail_reason(row: dict[str, str]) -> str | None:
    if any(not row.get(field, "").strip() for field in REQUIRED - {"selected_plan_id", "adjustment_json"}):
        return "MISSING_REQUIRED_PROVENANCE_OR_DISPLAY_FIELD"
    try:
        shown = json.loads(row["displayed_plan_ids"])
        order = json.loads(row["displayed_order"])
        features = json.loads(row["plan_features_json"])
        evidence = json.loads(row["evidence_ids_json"])
    except json.JSONDecodeError:
        return "INVALID_JSON"
    if not isinstance(shown, list) or not shown or not isinstance(order, list) or not order:
        return "INVALID_DISPLAY"
    if set(order) != set(shown) or not isinstance(features, (list, dict)) or not evidence:
        return "INCOMPLETE_DISPLAY_OR_EVIDENCE"
    if row["action"] == "select" and row["selected_plan_id"] not in shown:
        return "SELECTED_PLAN_NOT_DISPLAYED"
    if row["action"] == "adjust" and not row["adjustment_json"].strip():
        return "MISSING_ADJUSTMENT"
    if row["action"] not in {"select", "adjust", "dismiss"}:
        return "UNKNOWN_ACTION"
    return None


def bucket(student: str) -> str:
    value = int(sha256(student.encode()).hexdigest()[:8], 16) % 10
    return "train" if value < 7 else "validation" if value < 9 else "test"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate real feedback and create student-disjoint splits")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            missing = sorted(REQUIRED - set(reader.fieldnames or []))
            raise SystemExit("Missing columns: " + ", ".join(missing))
        rows = list(reader)
    accepted, rejected = [], []
    for row in rows:
        reason = fail_reason(row)
        if reason:
            rejected.append({"reason": reason, "anonymous_student_id": row.get("anonymous_student_id", "")})
        else:
            accepted.append(row | {"split": bucket(row["anonymous_student_id"])})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for split in ("train", "validation", "test"):
        values = [row for row in accepted if row["split"] == split]
        with (args.output_dir / f"{split}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(REQUIRED) + ["split"])
            writer.writeheader(); writer.writerows(values)
    (args.output_dir / "rejected.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"input_records": len(rows), "accepted_real_feedback_records": len(accepted),
        "rejected_records": len(rejected), "student_disjoint_split": True,
        "students": len({row["anonymous_student_id"] for row in accepted}),
        "split_records": {split: sum(row["split"] == split for row in accepted) for split in ("train", "validation", "test")},
        "ltr_ready": False,
        "note": "No threshold for sufficient real feedback is configured; do not train LTR from this output yet."}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
