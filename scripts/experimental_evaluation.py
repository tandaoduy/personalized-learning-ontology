"""Sinh bộ kết quả nghiên cứu, biểu đồ SVG và mẫu ground truth cố vấn.

Chạy: python scripts/experimental_evaluation.py --limit 0
"""
from __future__ import annotations

import argparse, csv, html, json, sys, time
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from statistics import mean, median

from rdflib.namespace import OWL, RDF

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flask_app.config import Config
from flask_app.services.recommendation_engine import ELECTIVE_QUOTA_KEYS, RecommendationEngine
from flask_app.services.student_data_service import StudentDataService
from scripts.benchmark_algorithms import beam_search_plan, greedy_plan, rule_based_plan

METHODS = [("Rule + Semester Order", rule_based_plan), ("Greedy Heuristic", greedy_plan), ("Heuristic + Beam Search", beam_search_plan)]
ABLATIONS = [("Full Ontology", None), ("Without prerequisites", "prereqs"), ("Without corequisites", "corequisites"), ("Without specialization", "specialization"), ("Without semester offering", "semester")]


def engine():
    return RecommendationEngine(Config.ONTOLOGY_PATH, Config.BEAM_WIDTH, Config.REGISTER_MAX_CREDITS,
        Config.REGISTER_MIN_CREDITS, {"debt": Config.WEIGHT_DEBT, "link": Config.WEIGHT_LINK, "delay": Config.WEIGHT_DELAY}, Config.ELECTIVE_QUOTAS)


def relevant(info, student):
    norm = RecommendationEngine._normalize_text
    major, spec = norm(student.major or ""), norm(student.specialization or "")
    majors, specs = {norm(x) for x in info.get("majors", [])}, {norm(x) for x in info.get("specializations", [])}
    return (not majors or major in majors) and (not specs or (spec != "chua chon chuyen nganh" and spec in specs))


def violations(truth, student, plan, max_credits):
    codes, passed, count = {x.code for x in plan}, set(student.passed_courses), Counter()
    if len(codes) != len(plan): count["duplicate"] += len(plan) - len(codes)
    if sum(x.credits for x in plan) > max_credits: count["credit"] += 1
    for code in codes:
        info = truth.get(code, {})
        count["prerequisite"] += sum(x not in passed | codes for x in info.get("prereqs", []))
        count["corequisite"] += sum(x not in passed | codes for x in info.get("corequisites", []))
        count["program"] += not relevant(info, student)
        count["semester"] += int(info.get("openSemesterType", 3) or 3) not in (3, student.next_semester_type())
    count["total"] = sum(v for k, v in count.items() if k != "total")
    return count


def evaluate(e, truth, student, plan, elapsed):
    codes, passed = {x.code for x in plan}, set(student.passed_courses)
    required = {c for c, i in e.course_data.items() if c not in passed and relevant(i, student) and (i.get("is_required_major") or i.get("is_required_specialization"))}
    _, _, completed, _ = e.get_eligible_courses(student)
    needs = {k: max(0, e.elective_quotas.get(k, 0) - completed.get(k, 0)) for k in ELECTIVE_QUOTA_KEYS}
    chosen = Counter(e.course_data.get(c, {}).get("elective_category") for c in codes)
    filled = sum(min(needs[k], chosen[k]) for k in ELECTIVE_QUOTA_KEYS)
    bad = violations(truth, student, plan, e.max_credits)
    return {"valid_plan": bad["total"] == 0, "required_coverage_pct": round(100*len(codes & required)/max(1, len(required)), 2),
        "quota_fulfilment_pct": round(100*filled/max(1, sum(needs.values())), 2), "priority_score": round(sum(x.total_priority_score for x in plan), 2),
        "credits": sum(x.credits for x in plan), "processing_time_ms": round(elapsed, 3),
        "explanation_rate_pct": round(100*sum(bool(x.reasons) for x in plan)/max(1, len(plan)), 2), "violation_total": bad["total"]}


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else []); w.writeheader(); w.writerows(rows)


def aggregate(rows):
    result = []
    for name, _ in METHODS:
        g = [x for x in rows if x["method"] == name]
        result.append({"method": name, "n": len(g), "valid_plan_rate_pct": round(100*mean(x["valid_plan"] for x in g), 2),
            "required_coverage_mean_pct": round(mean(x["required_coverage_pct"] for x in g), 2), "quota_fulfilment_mean_pct": round(mean(x["quota_fulfilment_pct"] for x in g), 2),
            "priority_score_mean": round(mean(x["priority_score"] for x in g), 2), "processing_time_mean_ms": round(mean(x["processing_time_ms"] for x in g), 3),
            "processing_time_median_ms": round(median(x["processing_time_ms"] for x in g), 3), "explanation_rate_mean_pct": round(mean(x["explanation_rate_pct"] for x in g), 2)})
    return result


@contextmanager
def ablated(e, target):
    original = deepcopy(e.course_data)
    try:
        for info in e.course_data.values():
            if target in ("prereqs", "corequisites"): info[target] = []
            elif target == "semester": info["openSemesterType"] = 3
            elif target == "specialization":
                info["specializations"] = []; info["is_required_specialization"] = False; info["is_elective_specialization"] = False
        yield
    finally: e.course_data = original


def run_ablation(e, truth, students):
    rows = []
    for label, target in ABLATIONS:
        totals, invalid = Counter(), 0
        with ablated(e, target):
            for s in students:
                bad = violations(truth, s, beam_search_plan(e, s), e.max_credits); totals.update(bad); invalid += bad["total"] > 0
        rows.append({"configuration": label, "plans": len(students), "invalid_recommendations": totals["total"], "valid_plan_rate_pct": round(100*(len(students)-invalid)/max(1,len(students)),2),
            "prerequisite_violations": totals["prerequisite"], "corequisite_violations": totals["corequisite"], "wrong_program_courses": totals["program"], "wrong_semester_courses": totals["semester"]})
    return rows


def chart(path, title, rows, metrics, unit):
    W,H,L,T,PW,PH=980,520,90,70,840,350; vals=[float(r[k]) for r in rows for k,_ in metrics]; maximum=max(vals+[1])*1.12; colors=["#2563eb","#f59e0b","#10b981","#ef4444"]
    x=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="100%" height="100%" fill="white"/>',f'<text x="490" y="30" text-anchor="middle" font-family="Arial" font-size="20" font-weight="bold">{html.escape(title)}</text>']
    for t in range(6):
        value=maximum*t/5; y=T+PH-PH*t/5; x += [f'<line x1="{L}" y1="{y}" x2="{L+PW}" y2="{y}" stroke="#ddd"/>',f'<text x="{L-7}" y="{y+4}" text-anchor="end" font-family="Arial" font-size="11">{value:.1f}</text>']
    gw=PW/len(rows); bw=min(55,gw/(len(metrics)+1))
    for i,r in enumerate(rows):
        center=L+gw*(i+.5)
        for j,(key,label) in enumerate(metrics):
            value=float(r[key]); h=PH*value/maximum; bx=center+(j-(len(metrics)-1)/2)*bw-bw*.4
            x += [f'<rect x="{bx}" y="{T+PH-h}" width="{bw*.8}" height="{h}" rx="3" fill="{colors[j]}"/>',f'<text x="{bx+bw*.4}" y="{T+PH-h-5}" text-anchor="middle" font-family="Arial" font-size="10">{value:g}</text>']
        x.append(f'<text x="{center}" y="{T+PH+22}" text-anchor="middle" font-family="Arial" font-size="10">{html.escape(r.get("method",r.get("configuration","")))}</text>')
    for j,(_,label) in enumerate(metrics): x += [f'<rect x="{L+j*215}" y="485" width="13" height="13" fill="{colors[j]}"/>',f'<text x="{L+18+j*215}" y="496" font-family="Arial" font-size="12">{html.escape(label)}</text>']
    x += [f'<text x="18" y="245" transform="rotate(-90 18 245)" text-anchor="middle" font-family="Arial" font-size="13">{html.escape(unit)}</text>',"</svg>"]
    path.write_text("\n".join(x), encoding="utf-8")


def scenario(s):
    if s.current_semester >= 7: return "near_graduation"
    if s.failed_courses: return "failed_course_or_prerequisite"
    if RecommendationEngine._normalize_text(s.specialization or "") == "chua chon chuyen_nganh": return "no_specialization"
    if s.study_goal == "học vượt": return "accelerated"
    return "on_track"


def make_advisor_template(path, e, students):
    rows=[]
    for s in students[:50]: rows.append({"student_id":s.student_id,"scenario":scenario(s),"system_courses":";".join(sorted(x.code for x in beam_search_plan(e,s))),"advisor_courses":"","accepted_system_courses":"","plan_acceptance":"","edit_level":"","advisor_note":""})
    write_csv(path,rows)


def advisor_metrics(path):
    if not path.exists(): return None
    with path.open(encoding="utf-8-sig",newline="") as f: rows=[r for r in csv.DictReader(f) if r.get("advisor_courses","").strip()]
    if not rows: return None
    agreement=[]; jaccard=[]; recall=[]; acceptance=[]
    for r in rows:
        system={x.strip().upper() for x in r["system_courses"].split(";") if x.strip()}; advisor={x.strip().upper() for x in r["advisor_courses"].split(";") if x.strip()}; text=r.get("accepted_system_courses","").strip(); approved={x.strip().upper() for x in text.split(";") if x.strip()} if text else system&advisor
        agreement.append(len(system&approved)/max(1,len(system))); jaccard.append(len(system&advisor)/max(1,len(system|advisor))); recall.append(len(system&advisor)/max(1,len(advisor))); acceptance.append(r.get("plan_acceptance","").strip().lower() in {"yes","accepted","chap nhan","chấp nhận"})
    return {"labelled_profiles":len(rows),"advisor_agreement_rate_pct":round(100*mean(agreement),2),"jaccard_mean_pct":round(100*mean(jaccard),2),"reference_recall_mean_pct":round(100*mean(recall),2),"plan_acceptance_rate_pct":round(100*mean(acceptance),2)}


def make_report(path, summary, abl, stats, advisor, n):
    beam=summary[2]; greedy=summary[1]; gain=100*(beam["priority_score_mean"]-greedy["priority_score_mean"])/max(1,abs(greedy["priority_score_mean"]))
    lines=["# Báo cáo thực nghiệm có thể tái lập","",f"Đánh giá trên **{n} hồ sơ**. Tính hợp lệ học vụ không được gọi là độ chính xác.","","## So sánh ba phương pháp","","| Phương pháp | Hợp lệ (%) | Bao phủ bắt buộc (%) | Quota (%) | Điểm ưu tiên | Thời gian TB (ms) |","|---|---:|---:|---:|---:|---:|"]
    for r in summary: lines.append(f"| {r['method']} | {r['valid_plan_rate_pct']} | {r['required_coverage_mean_pct']} | {r['quota_fulfilment_mean_pct']} | {r['priority_score_mean']} | {r['processing_time_mean_ms']} |")
    lines += ["","![Bao phủ và quota](figures/01_coverage_quota.svg)","","Hai chỉ số cùng thang phần trăm được đặt cạnh nhau. Mẫu số chỉ gồm môn bắt buộc phù hợp còn thiếu và quota còn thiếu.","","![Điểm ưu tiên](figures/02_priority.svg)","",f"Beam Search cải thiện **{gain:.3f}%** điểm heuristic so với tham lam; đây không phải Accuracy.","","![Thời gian](figures/03_time.svg)","","Thời gian được tách riêng do khác thang đo; khi trích dẫn cần ghi cấu hình máy.","","## Ablation ontology","","| Cấu hình | Hợp lệ (%) | Tổng sai | Tiên quyết | Song hành | Sai ngành/CN | Sai kỳ |","|---|---:|---:|---:|---:|---:|---:|"]
    for r in abl: lines.append(f"| {r['configuration']} | {r['valid_plan_rate_pct']} | {r['invalid_recommendations']} | {r['prerequisite_violations']} | {r['corequisite_violations']} | {r['wrong_program_courses']} | {r['wrong_semester_courses']} |")
    lines += ["","![Tỷ lệ kế hoạch hợp lệ](figures/04_ablation_valid_rate.svg)","","![Số lượt vi phạm](figures/05_ablation_violations.svg)","","Mỗi cấu hình vô hiệu hóa một nhóm tri thức lúc sinh kế hoạch rồi đối chiếu với ontology đầy đủ, nên chênh lệch đo trực tiếp vai trò nhóm tri thức.","","## Thống kê ontology","","```json",json.dumps(stats,ensure_ascii=False,indent=2),"```","","Thống kê cấu trúc không thay thế kết quả reasoner về tính nhất quán.","","## Độ phù hợp với cố vấn",""]
    lines += (["```json",json.dumps(advisor,ensure_ascii=False,indent=2),"```"] if advisor else ["**Chưa có ground truth cố vấn.** Điền `advisor_reference_template.csv` bằng đánh giá thật rồi chạy lại; hiện không công bố Accuracy/Precision/Recall."])
    lines += ["","## Pipeline","","Hồ sơ sinh viên → truy vấn ontology → tri thức học vụ → lọc hợp lệ → heuristic → Beam Search → kế hoạch + giải thích.","","Ontology bảo đảm ngữ nghĩa/học vụ; heuristic xếp ưu tiên; Beam Search tìm tổ hợp."]
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")


def main():
    p=argparse.ArgumentParser(); p.add_argument("--limit",type=int,default=0); p.add_argument("--output-dir",default="benchmark_results/experiment"); a=p.parse_args(); out=ROOT/a.output_dir; figs=out/"figures"; figs.mkdir(parents=True,exist_ok=True)
    students=StudentDataService(Config.STUDENT_DATA_JSON,Config.STUDENT_DATA_CSV).get_all_students(force_reload=True); students=students[:a.limit] if a.limit else students; e=engine(); truth=deepcopy(e.course_data); detail=[]
    for s in students:
        for name,method in METHODS:
            start=time.perf_counter(); plan=method(e,s); detail.append({"student_id":s.student_id,"scenario":scenario(s),"method":name,**evaluate(e,truth,s,plan,(time.perf_counter()-start)*1000)})
    summary=aggregate(detail); abl=run_ablation(e,truth,students); write_csv(out/"algorithm_detail.csv",detail); write_csv(out/"algorithm_summary.csv",summary); write_csv(out/"ontology_ablation.csv",abl)
    template=out/"advisor_reference_template.csv"; make_advisor_template(template,e,students) if not template.exists() else None
    g=e.graph; stats={"classes":len(set(g.subjects(RDF.type,OWL.Class))),"object_properties":len(set(g.subjects(RDF.type,OWL.ObjectProperty))),"datatype_properties":len(set(g.subjects(RDF.type,OWL.DatatypeProperty))),"courses":len(e.course_data),"prerequisite_relations":sum(len(i.get("prereqs",[])) for i in e.course_data.values()),"corequisite_relations":sum(len(i.get("corequisites",[])) for i in e.course_data.values()),"rdf_triples":len(g)}; (out/"ontology_statistics.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding="utf-8")
    chart(figs/"01_coverage_quota.svg","Coverage and quota fulfilment",summary,[("required_coverage_mean_pct","Required coverage"),("quota_fulfilment_mean_pct","Quota fulfilment")],"Percent (%)"); chart(figs/"02_priority.svg","Mean heuristic priority score",summary,[("priority_score_mean","Priority score")],"Score"); chart(figs/"03_time.svg","Mean processing time",summary,[("processing_time_mean_ms","Mean time")],"Milliseconds"); chart(figs/"04_ablation_valid_rate.svg","Valid plan rate after ontology ablation",abl,[("valid_plan_rate_pct","Valid plan rate")],"Percent (%)"); chart(figs/"05_ablation_violations.svg","Violations after ontology ablation",abl,[("prerequisite_violations","Prerequisite"),("corequisite_violations","Corequisite"),("wrong_program_courses","Program"),("wrong_semester_courses","Semester")],"Violations")
    make_report(out/"EXPERIMENT_REPORT.md",summary,abl,stats,advisor_metrics(template),len(students)); print(f"Completed {len(students)} profiles: {out/'EXPERIMENT_REPORT.md'}")

if __name__ == "__main__": main()
