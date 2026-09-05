"""Tạo năm biểu đồ thực nghiệm tiếng Việt bằng Matplotlib."""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmark_results" / "experiment"
FIGURES = RESULTS / "figures"
LABELS = {
    "Rule + Semester Order": "Rule-based",
    "Greedy Heuristic": "Greedy Heuristic",
    "Heuristic + Beam Search": "Heuristic +\nBeam Search",
    "Full Ontology": "Ontology đầy đủ",
    "Without prerequisites": "Bỏ tiên quyết",
    "Without corequisites": "Bỏ song hành",
    "Without specialization": "Bỏ chuyên ngành",
    "Without semester offering": "Bỏ kỳ mở",
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def setup_style():
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
                         "axes.unicode_minus": False, "font.size": 9, "figure.dpi": 120})


def save(fig, path):
    fig.savefig(path, format="svg", bbox_inches="tight")
    fig.savefig(path.with_suffix(".png"), dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def format_number(value, decimals=2):
    """Định dạng số theo quy ước tiếng Việt dùng trong luận văn."""
    text = f"{value:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return text.rstrip("0").rstrip(",")



def draw_grouped(path, title, rows, metrics, ylabel):
    names = [LABELS[row["method"]] for row in rows]
    x = np.arange(len(rows)); width = 0.78 / len(metrics)
    fig, ax = plt.subplots(figsize=(7.2, 4.15), constrained_layout=True)
    colors = ["#2563EB", "#F59E0B"]
    values_all = []
    for index, (key, label) in enumerate(metrics):
        values = [float(row[key]) for row in rows]; values_all.extend(values)
        offset = (index - (len(metrics) - 1) / 2) * width
        bars = ax.bar(x + offset, values, width * .9, label=label, color=colors[index], edgecolor="white")
        decimals = 3 if ylabel == "Thời gian (ms)" else 2
        ax.bar_label(bars, labels=[format_number(v, decimals) for v in values], padding=3, fontsize=8.5)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10); ax.set_ylabel(ylabel, fontweight="bold")
    ax.set_xticks(x, names); ax.tick_params(axis="x", labelsize=8.5, pad=5)
    ax.set_ylim(0, max(values_all + [1]) * 1.17)
    ax.grid(axis="y", linestyle="--", alpha=.3); ax.set_axisbelow(True); ax.spines[["top", "right"]].set_visible(False)
    if len(metrics) > 1:
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.18), ncol=len(metrics), frameon=False,
                  fontsize=8.5, handlelength=2.2, columnspacing=1.8)
    save(fig, path)


def draw_ablation_rates(path, rows):
    """Vẽ riêng tỷ lệ kế hoạch hợp lệ của các cấu hình ablation."""
    names = [LABELS[row["configuration"]] for row in rows]
    rates = np.array([float(row["valid_plan_rate_pct"]) for row in rows])
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(7.2, 4.15), constrained_layout=True)
    bars = ax.barh(y, rates, height=.58, color="#2563EB", edgecolor="white", linewidth=.8)
    ax.bar_label(bars, labels=[f"{format_number(value)}%" for value in rates], padding=4, fontsize=8.5)
    ax.set_yticks(y, names); ax.invert_yaxis(); ax.set_xlim(0, 112)
    ax.set_xlabel("Kế hoạch hợp lệ (%)", fontweight="bold")
    ax.set_title("Tỷ lệ kế hoạch hợp lệ khi loại bỏ tri thức ontology",
                 fontsize=12, fontweight="bold", pad=10)
    ax.grid(axis="x", linestyle="--", alpha=.25); ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=8.5, pad=7)
    save(fig, path)


def draw_ablation_violations(path, rows):
    """Vẽ riêng số lượt vi phạm phát sinh của các cấu hình ablation."""
    names = [LABELS[row["configuration"]] for row in rows]
    metrics = [("prerequisite_violations", "Vi phạm tiên quyết", "#2563EB"),
               ("corequisite_violations", "Vi phạm song hành", "#F59E0B"),
               ("wrong_program_courses", "Sai ngành/chuyên ngành", "#10B981"),
               ("wrong_semester_courses", "Sai kỳ mở", "#EF4444")]
    y = np.arange(len(rows)); left = np.zeros(len(rows))
    fig, ax = plt.subplots(figsize=(7.2, 4.15), constrained_layout=True)
    for key, label, color in metrics:
        values = np.array([int(row[key]) for row in rows])
        bars = ax.barh(y, values, left=left, height=.58, label=label, color=color, edgecolor="white", linewidth=.8)
        for bar, value in zip(bars, values):
            if value:
                ax.text(bar.get_x() + bar.get_width() + 12, bar.get_y() + bar.get_height()/2, str(value),
                        ha="left", va="center", color="#374151", fontsize=9, fontweight="bold")
        left += values
    for index, total in enumerate(left):
        if total == 0:
            ax.text(8, index, "0", va="center", color="#166534", fontweight="bold")
    ax.set_yticks(y, names); ax.invert_yaxis(); ax.set_xlabel("Số lượt vi phạm", fontweight="bold")
    ax.set_title("Số lượt vi phạm khi loại bỏ tri thức ontology",
                 fontsize=12, fontweight="bold", pad=10)
    ax.set_xlim(0, max(left) * 1.20); ax.grid(axis="x", linestyle="--", alpha=.25); ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=8.5, pad=7)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.18), ncol=2, frameon=False, fontsize=7.5,
              columnspacing=1.2, handlelength=2)
    save(fig, path)


def main():
    setup_style(); FIGURES.mkdir(parents=True, exist_ok=True)
    summary = read_csv(RESULTS / "algorithm_summary.csv")
    ablation = read_csv(RESULTS / "ontology_ablation.csv")
    draw_grouped(FIGURES / "01_coverage_quota.svg", "So sánh mức bao phủ và đáp ứng quota", summary,
                 [("required_coverage_mean_pct", "Bao phủ học phần bắt buộc"), ("quota_fulfilment_mean_pct", "Đáp ứng quota tự chọn")], "Tỷ lệ (%)")
    draw_grouped(FIGURES / "02_priority.svg", "So sánh điểm ưu tiên trung bình", summary,
                 [("priority_score_mean", "Điểm ưu tiên trung bình")], "Điểm ưu tiên")
    draw_grouped(FIGURES / "03_time.svg", "So sánh thời gian xử lý trung bình", summary,
                 [("processing_time_mean_ms", "Thời gian trung bình")], "Thời gian (ms)")
    draw_ablation_rates(FIGURES / "04_ablation_valid_rate.svg", ablation)
    draw_ablation_violations(FIGURES / "05_ablation_violations.svg", ablation)
    print(f"Da tao 5 bieu do SVG va 5 anh PNG tai: {FIGURES}")


if __name__ == "__main__":
    main()
