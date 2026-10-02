# NeuroScan

NeuroScan is a rule-based clinical decision-support system for the electrodiagnostic classification of polyneuropathy. It converts and de-identifies legacy electrodiagnostic reports (DOC/DOCX), extracts motor, sensory, and F-wave measurements, applies deterministic z-score rules based on ESTEEM-style criteria, and returns nerve-level and patient-level patterns together with the evidence behind each output.

No statistical model is trained and no machine-learning component is involved: given identical measurements, demographic inputs, reference settings, and software version, the rule engine returns the same output.

> **Research use only.** NeuroScan is intended for standardized audit and decision support under institutional governance. It is not an autonomous diagnostic tool and does not replace clinical judgment. It targets large-fiber electrodiagnostic patterns and does not assess small-fiber neuropathy.

## What it does

1. **Conversion and de-identification.** Legacy `.doc` files are converted to `.docx`; direct identifiers are redacted; each report receives a pseudonymous case identifier (for example `NS00001`); a post-save scan checks for residual identifiers.
2. **Table parsing.** Motor, sensory, and F-wave tables are extracted from the DOCX file, together with age and height when present.
3. **Nerve-level classification.** Each measurement is standardized as z = (x − μ) / σ against programmed, nerve-specific adult reference values. Each nerve receives one label: Normal, Axonal loss, Neuropathic, Probable demyelination, or Definite demyelination.
4. **Patient-level aggregation.** Nerve-level labels are combined into Normal, Axonal, Demyelinating, Mixed, Unclassified, or N/A (Insufficient Data). The system abstains (Unclassified or N/A) rather than force a subtype when the evidence requirements are not met.
5. **Outputs.** CSV tables, an SQLite database, quality-control reports, and, in the desktop interface, tables, diagnostic plots, and a printable report.

## Classification rules in brief

Thresholds are z scores. The complete rule set is in the Supplementary Information of the accompanying paper (Table S1), and the decision functions are in `analysis_logic.py`.

| Component | Normal | Axonal loss | Probable demyelination | Definite demyelination |
|---|---|---|---|---|
| Motor CV + CMAP | zCV > −2 and zAmp > −2 | zAmp ≤ −2.5 and zCV ≥ −2.5 | −5.5 < zCV ≤ −4.5, zAmp > −5 | zCV ≤ −5.5, zAmp > −5 |
| Motor DML + CMAP | zDML < 2 and zAmp > −2 | zAmp ≤ −2.5 and zDML ≤ 2.5 | 6 ≤ zDML < 8, zAmp > −5 | zDML ≥ 8, zAmp > −5 |
| Sensory CV + SNAP | zCV > −2 and zAmp > −2 | zAmp ≤ −2.5 and zCV ≥ −2.5 | −5.5 < zCV ≤ −4.5 | zCV ≤ −5.5 |
| F-wave | zFmin < 2 and persistence ≥ LLN | not assigned | zFmin ≥ 7, persistence ≥ 10% | zFmin ≥ 8, persistence ≥ 10% |

Remaining abnormal combinations are labeled Neuropathic. Patient-level criteria:

- **Demyelinating:** at least 2 nerves with definite demyelination, or 1 definite plus at least 2 probable, or at least 4 probable.
- **Axonal:** axonal loss in at least 2 sensory nerves, or at least 2 motor nerves, or at least 1 sensory plus 1 motor nerve.
- **Mixed:** both sets of criteria met in non-identical sets of nerves.
- **Normal:** no abnormal nerve-level result. **Unclassified:** abnormal findings present but no criterion met. **N/A:** no valid nerve-level result.

Behaviors that affect the output (missing values, zero values, discordant CV/DML labels, default age and height, nerves without a programmed reference entry) are described in the paper and visible in the source code.

## Installation

Requires Python 3. Install the dependencies:

```bash
pip install -r requirements.txt
```

| Package | Used for |
|---|---|
| `python-docx` | reading and writing DOCX files (parser, de-identification, batch builder) |
| `PyQt6` | desktop interface only; the rule engine and the batch builder run without it |
| `pywin32` (optional, Windows) | Microsoft Word automation as a fallback `.doc` converter |

Legacy `.doc` files need either LibreOffice (`soffice` in the `PATH`, tried first) or Microsoft Word on Windows. Python cannot parse the binary `.doc` format directly.

## Usage

**Desktop interface (single report):**

```bash
python run_neuroscan.py
```

The interface writes `neuroscan_settings.json` in the working directory. The parser writes a log file, `debug_log.txt`, in the working directory in both the desktop and the batch modes; set the environment variable `NEUROSCAN_QUIET=1` to silence its console output.

**Batch dataset builder (folder of reports):**

```bash
python phase2_dataset.py --input "path/to/original_reports" --output "path/to/output"
```

| Option | Default | Meaning |
|---|---|---|
| `--age-default` | 40 | age used when the report has no age |
| `--height-default` | 170 | height in cm used when the report has no height |
| `--doc-converter` | `auto` | `auto` (LibreOffice first, then Word), `libreoffice`, or `word` |
| `--conversion-timeout` | 60 | per-file conversion timeout in seconds |
| `--no-anonymize` | off | skip de-identification; for controlled debugging only |

The output folder contains:

- `anonymized_docx/`: pseudonymous DOCX reports
- `reports/case_index.csv`, `nerve_measurements.csv`, `neuroscan_predictions.csv`, `parsing_report.csv`, `anonymization_report.csv`, `expert_labels_template.csv`
- `neuroscan_validation.sqlite`: the same tables in one database
- `private_mapping_STORE_SEPARATELY/`: the filename-to-case-identifier mapping and the converted intermediate files

**Agreement with expert labels:** after filling `expert_labels_template.csv` (`expert_1_label`, `expert_2_label`, `consensus_label`):

```bash
python phase2_validation.py --predictions reports/neuroscan_predictions.csv --expert-labels reports/expert_labels_template.csv --output validation_metrics
```

This reports accuracy, balanced accuracy, macro-F1, Cohen's kappa, per-class metrics, and a confusion matrix, treating every software output as a class. It does not compute coverage, confidence intervals, or the binary polyneuropathy-versus-Normal analysis.

## Example

`examples/synthetic_report.docx` is a synthetic report in the layout described below. Its values are invented for demonstration and do not belong to any patient. To process it with the batch builder:

```bash
python phase2_dataset.py --input examples --output example_output
```

The report contains no age or height, so the defaults (40 years, 170 cm) are used. In `example_output/reports/neuroscan_predictions.csv` the patient-level pattern is **Axonal** (axonal loss in both sural nerves; all other nerves are Normal). The same file can be loaded in the desktop interface.

## Input format

The parser reads body-level tables of DOCX reports with motor, sensory, and F-wave sections (for example, tables titled `Motor Nerves`, `Sensory Nerves`, and `F-Wave Nerves`) in which each nerve occupies one row whose name combines the nerve and the side. Values of several stimulation sites listed in one cell are reduced to the first numeric value. Other report layouts may need changes to `file_processor.py`.

## Privacy and data

- This repository contains code and one synthetic example report. No patient data or real reports are included.
- Reports must be handled under the governance of the institution that holds them. The de-identification module is a technical aid, not a legal guarantee of anonymization, and does not replace institutional privacy review or manual sampling.
- The module redacts report fields and text. It does not modify document properties (such as author fields) of the DOCX file.
- The private mapping folder and the converted intermediate files still contain original identifiers and must never be shared or committed.

## Known limitations

- Reference values are adult values; pediatric reference handling is not validated. Height defaults to 170 cm and age to 40 years when absent from the report.
- The parser and the rules were developed and evaluated on one report family from a single center.
- The rule set abstains in many cases and has limited subtype discrimination; see the accompanying paper for the retrospective evaluation.
- Not tested for use outside research and audit.

## Repository structure

| Path | Content |
|---|---|
| `run_neuroscan.py`, `gui.py` | desktop interface |
| `file_processor.py`, `parser_utils.py`, `word_com_convert.py` | DOC conversion and table parsing |
| `reference_database.py` | programmed reference values and examination-completeness check |
| `analysis_logic.py` | nerve-level and patient-level classification |
| `reporting.py` | text and HTML reports |
| `phase2_dataset.py`, `phase2_validation.py` | batch builder, de-identification, agreement metrics |
| `examples/synthetic_report.docx` | synthetic example report (invented values) |
| `requirements.txt` | Python dependencies |
| `LICENSE` | MIT License |

## Citation

If you find ImagiChem useful in your own research please cite:

**NeuroScan for Standardized Electrodiagnostic Classification of Polyneuropathy: Development and Retrospective Validation of a Rule-Based Clinical Decision-Support System in 746 Examinations**\
Rocco Buccheri, Maria Proietto, Michele Vecchio, and Antonio Rescifina\
Journal Year, DOI

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
