"""Validation metrics for NeuroScan Phase-2 expert review tables."""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _read_csv(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: str | Path, rows: List[Dict], fieldnames: List[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _patient_predictions(predictions_rows: List[Dict[str, str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for row in predictions_rows:
        case_id = row.get("case_id", "")
        pattern = row.get("patient_pnp_pattern", "")
        if case_id and pattern and case_id not in out:
            out[case_id] = pattern
    return out


def cohen_kappa(labels_a: List[str], labels_b: List[str]) -> float:
    if len(labels_a) != len(labels_b):
        raise ValueError("Label lists must have the same length")
    n = len(labels_a)
    if n == 0:
        return 0.0
    observed = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n
    ca, cb = Counter(labels_a), Counter(labels_b)
    expected = sum((ca[label] / n) * (cb[label] / n) for label in set(ca) | set(cb))
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - expected) / (1.0 - expected)


def compute_classification_metrics(predicted: Dict[str, str], gold: Dict[str, str]) -> Dict[str, object]:
    paired = [(predicted[cid], gold[cid]) for cid in sorted(set(predicted) & set(gold)) if predicted.get(cid) and gold.get(cid)]
    classes = sorted(set([p for p, _ in paired] + [g for _, g in paired]))
    n = len(paired)
    accuracy = sum(1 for p, g in paired if p == g) / n if n else 0.0
    kappa = cohen_kappa([p for p, _ in paired], [g for _, g in paired]) if n else 0.0

    per_class = []
    for cls in classes:
        tp = sum(1 for p, g in paired if p == cls and g == cls)
        fp = sum(1 for p, g in paired if p == cls and g != cls)
        fn = sum(1 for p, g in paired if p != cls and g == cls)
        tn = sum(1 for p, g in paired if p != cls and g != cls)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        specificity = tn / (tn + fp) if tn + fp else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class.append({
            "class": cls,
            "support": tp + fn,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": f"{precision:.4f}",
            "sensitivity_recall": f"{recall:.4f}",
            "specificity": f"{specificity:.4f}",
            "f1": f"{f1:.4f}",
        })

    macro_f1 = sum(float(r["f1"]) for r in per_class) / len(per_class) if per_class else 0.0
    balanced_accuracy = sum(float(r["sensitivity_recall"]) for r in per_class) / len(per_class) if per_class else 0.0
    return {
        "n": n,
        "classes": classes,
        "accuracy": accuracy,
        "balanced_accuracy": balanced_accuracy,
        "macro_f1": macro_f1,
        "cohen_kappa": kappa,
        "per_class": per_class,
        "paired": paired,
    }


def build_confusion_matrix(predicted: Dict[str, str], gold: Dict[str, str]) -> Tuple[List[str], List[Dict[str, str]]]:
    paired = [(predicted[cid], gold[cid]) for cid in sorted(set(predicted) & set(gold)) if predicted.get(cid) and gold.get(cid)]
    classes = sorted(set([p for p, _ in paired] + [g for _, g in paired]))
    matrix = {g: Counter() for g in classes}
    for p, g in paired:
        matrix[g][p] += 1
    rows = []
    for g in classes:
        row = {"gold_standard": g}
        for p in classes:
            row[p] = str(matrix[g][p])
        rows.append(row)
    return classes, rows


def compute_validation_from_csv(predictions_csv: str | Path, expert_labels_csv: str | Path, output_dir: str | Path) -> Dict[str, object]:
    predictions = _patient_predictions(_read_csv(predictions_csv))
    labels_rows = _read_csv(expert_labels_csv)
    gold = {r.get("case_id", ""): r.get("consensus_label", "") for r in labels_rows if r.get("case_id") and r.get("consensus_label")}
    expert1 = {r.get("case_id", ""): r.get("expert_1_label", "") for r in labels_rows if r.get("case_id") and r.get("expert_1_label")}
    expert2 = {r.get("case_id", ""): r.get("expert_2_label", "") for r in labels_rows if r.get("case_id") and r.get("expert_2_label")}

    metrics = compute_classification_metrics(predictions, gold)
    output_dir = Path(output_dir)
    summary_rows = [{
        "n_cases": metrics["n"],
        "accuracy": f"{metrics['accuracy']:.4f}",
        "balanced_accuracy": f"{metrics['balanced_accuracy']:.4f}",
        "macro_f1": f"{metrics['macro_f1']:.4f}",
        "cohen_kappa_software_vs_consensus": f"{metrics['cohen_kappa']:.4f}",
    }]

    common_expert_cases = sorted(set(expert1) & set(expert2))
    if common_expert_cases:
        k = cohen_kappa([expert1[c] for c in common_expert_cases], [expert2[c] for c in common_expert_cases])
        summary_rows[0]["cohen_kappa_expert1_vs_expert2"] = f"{k:.4f}"
        summary_rows[0]["n_expert_overlap"] = len(common_expert_cases)
    else:
        summary_rows[0]["cohen_kappa_expert1_vs_expert2"] = ""
        summary_rows[0]["n_expert_overlap"] = 0

    _write_csv(output_dir / "validation_summary.csv", summary_rows, list(summary_rows[0].keys()))
    _write_csv(output_dir / "validation_per_class.csv", metrics["per_class"], ["class", "support", "tp", "fp", "fn", "tn", "precision", "sensitivity_recall", "specificity", "f1"])
    classes, matrix_rows = build_confusion_matrix(predictions, gold)
    _write_csv(output_dir / "confusion_matrix.csv", matrix_rows, ["gold_standard"] + classes)
    return metrics


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compute NeuroScan Phase-2 validation metrics after expert review.")
    parser.add_argument("--predictions", required=True, help="reports/neuroscan_predictions.csv")
    parser.add_argument("--expert-labels", required=True, help="Completed expert_labels_template.csv with consensus_label")
    parser.add_argument("--output", required=True, help="Output folder for validation metrics")
    args = parser.parse_args(argv)
    metrics = compute_validation_from_csv(args.predictions, args.expert_labels, args.output)
    print(f"Validation metrics computed for {metrics['n']} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
