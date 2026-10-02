# reporting.py
"""Plain-text report generation for NeuroScan.

The report is designed as an auditable export: it records the patient-level
classification, exam-completeness warnings, nerve-level diagnoses, observed
values, z-scores, and whether custom reference overrides were applied.
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Iterable, Optional
import base64
import html


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def _section(title: str) -> str:
    return f"\n{title}\n" + "-" * len(title) + "\n"


def build_text_report(results: Dict[str, Any], validation: Optional[Dict[str, Any]] = None,
                      patient_context: Optional[Dict[str, Any]] = None) -> str:
    """Build a deterministic plain-text report from analysis results."""
    patient_context = patient_context or {}
    validation = validation or {}
    now = _dt.datetime.now().isoformat(timespec="seconds")

    lines = [
        "NeuroScan electrodiagnostic pattern report",
        f"Generated: {now}",
        "",
        "Important: this output is a rule-based decision-support report and does not replace clinical judgement.",
    ]

    if patient_context:
        lines.append(_section("Patient / acquisition context"))
        for key, value in patient_context.items():
            lines.append(f"{key}: {value}")

    pnp = results.get("pnp_classification", {}) if isinstance(results, dict) else {}
    lines.append(_section("Patient-level PNP classification"))
    lines.append(f"Pattern: {pnp.get('pattern', '-')}")
    lines.append(f"Details: {pnp.get('details', '-')}")

    if validation:
        lines.append(_section("Exam completeness validation"))
        lines.append(f"Minimum criteria met: {validation.get('is_valid', False)}")
        errors = validation.get("errors", []) or []
        warnings = validation.get("warnings", []) or []
        if errors:
            lines.append("Errors:")
            lines.extend(f"  - {item}" for item in errors)
        if warnings:
            lines.append("Warnings:")
            lines.extend(f"  - {item}" for item in warnings)
        if not errors and not warnings:
            lines.append("No completeness warnings.")

    for modality in ("motor", "sensory", "fwave"):
        lines.append(_section(f"{modality.title()} nerve-level evidence"))
        records: Iterable[dict] = results.get(modality, []) or []
        any_record = False
        for rec in records:
            any_record = True
            ev = rec.get("evidence", {}) if isinstance(rec, dict) else {}
            observed = ev.get("observed", {}) if isinstance(ev, dict) else {}
            zscores = ev.get("z_scores", {}) if isinstance(ev, dict) else {}
            components = ev.get("components", {}) if isinstance(ev, dict) else {}
            notes = ev.get("notes", []) if isinstance(ev, dict) else []
            lines.append(f"Nerve: {rec.get('nerve', '-')}")
            lines.append(f"  Diagnosis: {rec.get('diagnosis', '-')}")
            if observed:
                obs_txt = ", ".join(f"{k}={_fmt(v)}" for k, v in observed.items())
                lines.append(f"  Observed: {obs_txt}")
            if zscores:
                z_txt = ", ".join(f"z_{k}={_fmt(v)}" for k, v in zscores.items())
                lines.append(f"  Z-scores: {z_txt}")
            if components:
                comp_txt = ", ".join(f"{k}: {v}" for k, v in components.items())
                lines.append(f"  Components: {comp_txt}")
            if ev.get("reference_override_applied"):
                lines.append("  Reference: custom modality-level preset applied")
            if notes:
                for note in notes:
                    lines.append(f"  Note: {note}")
            lines.append("")
        if not any_record:
            lines.append("No records.")

    return "\n".join(lines).rstrip() + "\n"


def build_html_report(results: Dict[str, Any], validation: Optional[Dict[str, Any]] = None,
                      patient_context: Optional[Dict[str, Any]] = None,
                      figure_png_bytes: Optional[bytes] = None) -> str:
    """Build a printable self-contained HTML report, optionally embedding the combined plots."""
    text_report = build_text_report(results, validation=validation, patient_context=patient_context)
    image_html = ""
    if figure_png_bytes:
        encoded = base64.b64encode(figure_png_bytes).decode("ascii")
        image_html = (
            '<h2>Diagnostic plots</h2>'
            '<p class="note">Single combined figure generated from the active analysis results.</p>'
            f'<img class="figure" src="data:image/png;base64,{encoded}" alt="NeuroScan combined diagnostic plots" />'
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>NeuroScan Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 32px; color: #1f2933; }}
h1 {{ font-size: 22px; margin-bottom: 6px; }}
h2 {{ margin-top: 28px; border-bottom: 1px solid #d9e2ec; padding-bottom: 6px; }}
pre {{ white-space: pre-wrap; background: #f7f9fb; border: 1px solid #d9e2ec; border-radius: 8px; padding: 16px; line-height: 1.35; }}
.figure {{ width: 100%; max-width: 1800px; border: 1px solid #d9e2ec; border-radius: 8px; }}
.note {{ color: #52606d; }}
@media print {{ body {{ margin: 12mm; }} .figure {{ page-break-inside: avoid; }} }}
</style>
</head>
<body>
<h1>NeuroScan electrodiagnostic pattern report</h1>
<p class="note">Rule-based decision-support output. The final interpretation remains clinical.</p>
{image_html}
<h2>Audit report</h2>
<pre>{html.escape(text_report)}</pre>
</body>
</html>
"""
