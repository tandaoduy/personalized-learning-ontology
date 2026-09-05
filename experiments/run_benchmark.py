import pytest
import platform
import time
import sys
from pathlib import Path

class MarkdownReportPlugin:
    def __init__(self):
        self.results = []
        self.start_time = 0
        self.end_time = 0

    def pytest_sessionstart(self, session):
        self.start_time = time.time()

    def pytest_sessionfinish(self, session, exitstatus):
        self.end_time = time.time()

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            self.results.append(report)

def run():
    root_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root_dir))
    
    plugin = MarkdownReportPlugin()
    args = ["-v", "backend/tests/"]
    
    # Check if pytest.ini exists and we are in root
    root_dir = Path(__file__).resolve().parents[1]
    pytest.main(args, plugins=[plugin])
    
    passed = len([r for r in plugin.results if r.passed])
    failed = len([r for r in plugin.results if r.failed])
    skipped = len([r for r in plugin.results if r.skipped])
    total = len(plugin.results)
    
    md = f"""# Test & Benchmark Report

## Môi trường chạy
- **Hệ điều hành:** {platform.system()} {platform.release()}
- **Phiên bản Python:** {platform.python_version()}
- **Thời gian chạy (Test Suite):** {plugin.end_time - plugin.start_time:.2f} giây

## Tổng quan
- **Tổng số ca kiểm thử:** {total}
- **Đạt (Pass):** {passed}
- **Không đạt (Fail):** {failed}
- **Bỏ qua (Skip):** {skipped}

## Chi tiết các nhóm kiểm thử và yêu cầu nghiệp vụ
| File kiểm thử | Yêu cầu nghiệp vụ | Kết quả (Pass/Fail) |
|---|---|---|
"""
    # Group results by file
    file_results = {}
    for r in plugin.results:
        f = r.nodeid.split('::')[0]
        if f not in file_results:
            file_results[f] = {"pass": 0, "fail": 0}
        if r.passed:
            file_results[f]["pass"] += 1
        elif r.failed:
            file_results[f]["fail"] += 1
            
    mapping = {
        "backend/tests/test_security_controls.py": "Bảo mật (Hash, Session, Phân quyền)",
        "backend/tests/test_recommendation_api_integration.py": "API Gợi ý môn học",
        "backend/tests/test_recommendation_engine.py": "Thuật toán gợi ý môn học",
        "backend/tests/test_progress_risk_analyzer.py": "Phân tích rủi ro tiến độ",
        "backend/tests/test_deep_business_rules.py": "Quy tắc nghiệp vụ học vụ (Song hành, Tiên quyết)",
        "backend/tests/test_sparql.py": "Truy vấn Ontology SPARQL",
        "backend/tests/test_student_data_service.py": "Xử lý dữ liệu sinh viên",
        "backend/tests/test_ui_integration.py": "Luồng giao diện người dùng (UI Integration)",
    }
    
    for f, counts in file_results.items():
        req = mapping.get(f.replace("\\", "/"), "Kiểm thử chung")
        md += f"| `{f}` | {req} | {counts['pass']} Pass / {counts['fail']} Fail |\n"
        
    out_dir = root_dir / "benchmark_results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "test_report.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(md)
        
    print(f"Report saved at {out_file.relative_to(root_dir)}")

if __name__ == "__main__":
    run()
