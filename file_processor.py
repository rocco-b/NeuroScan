# file_processor.py
"""Robust Word (.doc/.docx) parser for NeuroScan.

The parser is intentionally conservative: it extracts the first numeric token
from relevant cells, preserves nerve names, logs parsing decisions, and keeps
legacy .doc conversion optional because it depends on Microsoft Word/COM.
"""
import datetime
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from parser_utils import normalise_header, first_numeric_token

try:
    import win32com.client as win32  # type: ignore
except Exception:  # pywin32 is available only on Windows with COM support
    win32 = None

from docx import Document

try:
    from PyQt6.QtCore import QObject, pyqtSignal, QRunnable
except Exception:  # Allows headless batch extraction without PyQt6 installed.
    class QObject:  # type: ignore
        pass

    class _DummySignal:
        def __init__(self, *args, **kwargs):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def emit(self, *args, **kwargs):
            for callback in list(self._callbacks):
                callback(*args, **kwargs)

    def pyqtSignal(*args, **kwargs):  # type: ignore
        return _DummySignal(*args, **kwargs)

    class QRunnable:  # type: ignore
        pass

LOG_FILE = "debug_log.txt"
try:
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
except Exception:
    pass


def write_log(message):
    """Write parser diagnostics both to a file and stdout."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')}: {message}\n")
        if os.environ.get("NEUROSCAN_QUIET", "").strip().lower() not in {"1", "true", "yes"}:
            print(f"LOG: {message}")
            sys.stdout.flush()
    except Exception as e:
        print(f"IMPOSSIBILE SCRIVERE NEL LOG: {e}")


class WorkerSignals(QObject):
    """Signals emitted by the file worker thread."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)


class FileProcessor(QRunnable):
    """Worker thread for processing .doc/.docx neurophysiology reports."""

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.signals = WorkerSignals()
        self.last_diagnostics = {
            "tables_seen": 0,
            "motor_sections": 0,
            "sensory_sections": 0,
            "fwave_sections": 0,
            "motor_rows": 0,
            "sensory_rows": 0,
            "fwave_rows": 0,
            "parser_errors": [],
        }

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_header(text: str) -> str:
        return normalise_header(text)

    @staticmethod
    def _first_numeric_token(text: str, allow_percent: bool = False) -> str:
        """Return the first numeric token, preserving --/NC when no number exists."""
        return first_numeric_token(text, allow_percent=allow_percent)

    @classmethod
    def _find_col(cls, headers: List[str], *patterns: str) -> Optional[int]:
        norm_headers = [cls._normalise_header(h) for h in headers]
        for pat in patterns:
            pat_norm = cls._normalise_header(pat)
            for idx, header in enumerate(norm_headers):
                if pat_norm in header:
                    return idx
        return None

    @staticmethod
    def _is_notes_or_empty(cells: List[str]) -> bool:
        if not cells or not any(cells):
            return True
        first = (cells[0] or "").strip().lower()
        return first.startswith("notes:") or first == "notes"

    # ------------------------------------------------------------------
    # Worker execution
    # ------------------------------------------------------------------
    def run(self):
        try:
            path_to_analyze = self.filepath
            if self.filepath.lower().endswith(".doc"):
                path_to_analyze = self._convert_doc_to_docx(self.filepath)

            data = self._extract_data(path_to_analyze)
            self.signals.finished.emit(data)
        except Exception as e:
            write_log(f"ERRORE CRITICO in FileProcessor.run: {e}")
            self.signals.error.emit(str(e))

    def _convert_doc_to_docx(self, doc_path, output_dir=None, converter="auto", timeout=60):
        """Convert a legacy binary .doc report to .docx without blocking the batch.

        The default order is LibreOffice first, then Microsoft Word/COM in a
        separate subprocess.  Word/COM is deliberately isolated because, on some
        Windows installations, ``DispatchEx("Word.Application")`` may hang or
        fail with "server execution failed" and would otherwise freeze the whole
        dataset build.

        Parameters
        ----------
        doc_path:
            Source legacy .doc file.
        output_dir:
            Folder where the converted .docx will be written.
        converter:
            "auto", "libreoffice", or "word".  "auto" means LibreOffice first,
            then Word/COM fallback.
        timeout:
            Per-converter timeout in seconds.
        """
        doc_abs_path = os.path.abspath(str(doc_path))
        base_name = os.path.splitext(os.path.basename(doc_abs_path))[0] + ".docx"
        if output_dir is None:
            output_dir = os.path.dirname(doc_abs_path)
        output_dir = os.path.abspath(str(output_dir))
        os.makedirs(output_dir, exist_ok=True)
        docx_abs_path = os.path.join(output_dir, base_name)
        if os.path.exists(docx_abs_path):
            return docx_abs_path

        converter = (converter or "auto").strip().lower()
        if converter not in {"auto", "libreoffice", "word"}:
            raise ValueError("converter must be one of: auto, libreoffice, word")

        errors = []

        def _try_libreoffice():
            soffice_candidates = [
                shutil.which("soffice"),
                shutil.which("libreoffice"),
                r"C:\Program Files\LibreOffice\program\soffice.exe",
                r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            ]
            tried = False
            for soffice in [c for c in soffice_candidates if c and os.path.exists(c)]:
                tried = True
                try:
                    write_log(f"DOC conversion: trying LibreOffice: {soffice}")
                    completed = subprocess.run(
                        [
                            soffice,
                            "--headless",
                            "--convert-to", "docx",
                            "--outdir", output_dir,
                            doc_abs_path,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        check=False,
                    )
                    if os.path.exists(docx_abs_path):
                        return docx_abs_path
                    errors.append(
                        "LibreOffice conversion did not create the expected .docx file "
                        f"(returncode={completed.returncode}, stdout={completed.stdout.strip()}, stderr={completed.stderr.strip()})"
                    )
                except subprocess.TimeoutExpired:
                    errors.append(f"LibreOffice conversion timed out after {timeout} seconds")
                except Exception as exc:
                    errors.append(f"LibreOffice conversion failed: {exc}")
            if not tried:
                errors.append("LibreOffice/soffice was not found in PATH or standard install folders")
            return None

        def _try_word_subprocess():
            helper = Path(__file__).with_name("word_com_convert.py")
            if not helper.exists():
                errors.append("word_com_convert.py helper is missing")
                return None
            try:
                write_log("DOC conversion: trying Microsoft Word/COM in isolated subprocess")
                completed = subprocess.run(
                    [sys.executable, str(helper), doc_abs_path, docx_abs_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                if os.path.exists(docx_abs_path):
                    return docx_abs_path
                errors.append(
                    "Microsoft Word/COM conversion did not create the expected .docx file "
                    f"(returncode={completed.returncode}, stdout={completed.stdout.strip()}, stderr={completed.stderr.strip()})"
                )
            except subprocess.TimeoutExpired:
                errors.append(
                    f"Microsoft Word/COM conversion timed out after {timeout} seconds. "
                    "This usually indicates a broken or blocked Office COM server."
                )
            except Exception as exc:
                errors.append(f"Microsoft Word/COM conversion failed before completion: {exc}")
            return None

        if converter in {"auto", "libreoffice"}:
            converted = _try_libreoffice()
            if converted:
                return converted

        if converter in {"auto", "word"}:
            converted = _try_word_subprocess()
            if converted:
                return converted

        raise RuntimeError(
            "Unable to convert legacy .doc report to .docx. Recommended fix on Windows: install LibreOffice "
            "and ensure soffice.exe is in PATH, or rerun with --doc-converter word only if Microsoft Word COM is stable. "
            "Details: " + " | ".join(errors)
        )

    def _extract_data(self, docx_path):
        """Extract all supported NCS tables from a DOCX report.

        Multiple tables of the same modality are appended.  Generic DY11
        tables lacking an explicit ``Motor/Sensory Nerves`` title and page-
        continuation tables are also supported.
        """
        document = Document(docx_path)
        extracted_data: Dict[str, List[dict]] = {"motor": [], "sensory": [], "fwave": []}
        diagnostics = {
            "tables_seen": len(document.tables),
            "motor_sections": 0,
            "sensory_sections": 0,
            "fwave_sections": 0,
            "motor_rows": 0,
            "sensory_rows": 0,
            "fwave_rows": 0,
            "continuation_tables": 0,
            "parser_errors": [],
        }
        last_modality = None
        last_headers = None
        last_col_count = None

        for table_idx, table in enumerate(document.tables):
            if not table.rows:
                continue
            raw_header = [cell.text.strip().replace("\n", " ") for cell in table.rows[0].cells]
            header_cells = []
            for row in table.rows[:2]:
                header_cells.extend(cell.text for cell in row.cells)
            header_text = " ".join(header_cells).lower()
            header_norm = self._normalise_header(header_text)
            first_row_text = " ".join(raw_header).strip()
            write_log(f"Table {table_idx}: header={header_text}")

            modality = None
            # F-wave must be checked first because it also contains mV and ms.
            if "f-wavenerves" in header_norm or "fwavenerves" in header_norm or "fmin" in header_norm:
                modality = "fwave"
            elif "motornerves" in header_norm or ("motor" in header_norm and "amp" in header_norm):
                modality = "motor"
            elif "sensorynerves" in header_norm or ("sensory" in header_norm and "amp" in header_norm):
                modality = "sensory"
            # Generic tables generated by some DY11 report layouts.
            elif "nerve" in header_norm and "cv[m/s]" in header_norm and (
                "amplitude[mv]" in header_norm or "amp[mv]" in header_norm
            ):
                modality = "motor"
            elif "nerve" in header_norm and "cv[m/s]" in header_norm and (
                "amplitude[v]" in header_norm or "amplitude[uv]" in header_norm
                or "amp[v]" in header_norm or "amp[uv]" in header_norm
            ):
                modality = "sensory"

            if modality is not None:
                diagnostics[f"{modality}_sections"] += 1
                parser = getattr(self, f"_parse_{modality}_table")
                rows = parser(table)
                extracted_data[modality].extend(rows)
                last_modality = modality
                last_headers = raw_header
                last_col_count = len(table.rows[0].cells)
                continue

            # Continuation pages may contain only data rows and no repeated
            # header.  Reuse the preceding table schema conservatively.
            cells0 = [c.text.strip() for c in table.rows[0].cells]
            numeric_cells = sum(bool(self._first_numeric_token(x) != "--") for x in cells0[1:])
            first_cell = cells0[0].strip().lower() if cells0 else ""
            continuation_ok = (
                last_modality is not None
                and last_headers is not None
                and last_col_count == len(cells0)
                and first_cell
                and not first_cell.startswith(("notes", "muscle", "patient", "emg examination", "date of"))
                and numeric_cells >= 2
            )
            if continuation_ok:
                diagnostics["continuation_tables"] += 1
                parser = getattr(self, f"_parse_{last_modality}_table")
                rows = parser(table, inherited_headers=last_headers, start_row=0)
                extracted_data[last_modality].extend(rows)

        for modality in ("motor", "sensory", "fwave"):
            diagnostics[f"{modality}_rows"] = len(extracted_data[modality])
            if diagnostics[f"{modality}_sections"] > 0 and not extracted_data[modality]:
                diagnostics["parser_errors"].append(
                    f"{modality.upper()} section present but zero rows were extracted"
                )

        self.last_diagnostics = diagnostics
        return extracted_data

    # ------------------------------------------------------------------
    # Table parsers
    # ------------------------------------------------------------------
    def _parse_motor_table(self, table, inherited_headers=None, start_row=1):
        write_log("--- Avvio parsing _parse_motor_table ---")
        data = []
        raw_header = inherited_headers or [cell.text.strip().replace("\n", " ") for cell in table.rows[0].cells]
        write_log(f"Headers Grezzi Motor: {raw_header}")

        name_idx = self._find_col(raw_header, "motor nerves", "nerve") or 0
        amp_idx = self._find_col(raw_header, "amp[mv]", "amplitude[mv]", "cmap")
        cv_idx = self._find_col(raw_header, "cv[m/s]", "velocity", "conduction")
        dml_idx = self._find_col(raw_header, "dml[ms]", "lat[ms]", "latency[ms]")

        write_log(f"Colonne Motor: name={name_idx}, amp={amp_idx}, cv={cv_idx}, dml={dml_idx}")
        if amp_idx is None or cv_idx is None or dml_idx is None:
            write_log("ERRORE: colonne motorie essenziali mancanti (Nerve, Amp, CV, DML/Lat).")
            return []

        logical_rows_data = []
        current_row_group = None
        for row in table.rows[start_row:]:
            cells_text = [c.text.strip() for c in row.cells]
            if self._is_notes_or_empty(cells_text):
                continue
            if cells_text[name_idx]:
                if current_row_group:
                    logical_rows_data.append(current_row_group)
                current_row_group = [[] for _ in range(len(cells_text))]
            if current_row_group:
                for i, cell_text in enumerate(cells_text):
                    if cell_text:
                        current_row_group[i].append(cell_text)
        if current_row_group:
            logical_rows_data.append(current_row_group)

        for group in logical_rows_data:
            try:
                nerve_name = " ".join(group[name_idx]).strip()
                if not nerve_name:
                    continue
                amp_text = "\n".join(group[amp_idx]) if amp_idx < len(group) else "--"
                cv_text = "\n".join(group[cv_idx]) if cv_idx < len(group) else "--"
                dml_text = "\n".join(group[dml_idx]) if dml_idx < len(group) else "--"
                data.append({
                    "Nerve": nerve_name,
                    "Amp": self._first_numeric_token(amp_text),
                    "CV": self._first_numeric_token(cv_text),
                    "DML": self._first_numeric_token(dml_text),
                })
            except Exception as exc:
                write_log(f"Saltata riga motoria malformata: {exc}")
                continue

        write_log(f"Estrazione Motor completata. {len(data)} righe trovate.")
        return data

    def _parse_sensory_table(self, table, inherited_headers=None, start_row=1):
        write_log("--- Avvio parsing _parse_sensory_table ---")
        data = []
        raw_header = inherited_headers or [cell.text.strip().replace("\n", " ") for cell in table.rows[0].cells]
        write_log(f"Headers Grezzi Sensory: {raw_header}")

        name_idx = self._find_col(raw_header, "sensory nerves", "nerve") or 0
        # LibreOffice conversion of legacy DY11 reports frequently loses the
        # micro sign and renders the sensory amplitude header as ``Amp [V]``.
        # This is a header-encoding artefact; the numerical values remain µV.
        amp_idx = self._find_col(
            raw_header,
            "amp[uv]", "amp[µv]", "amp[μv]", "amp[v]",
            "snap", "amplitude"
        )
        cv_idx = self._find_col(raw_header, "cv[m/s]", "velocity", "conduction")
        dml_idx = self._find_col(raw_header, "dml[ms]", "lat[ms]", "latency[ms]")

        write_log(f"Colonne Sensory: name={name_idx}, amp={amp_idx}, cv={cv_idx}, dml={dml_idx}")
        if amp_idx is None or cv_idx is None:
            write_log("ERRORE: colonne sensory essenziali mancanti (Nerve, Amp, CV).")
            return []

        for row_idx, row in enumerate(table.rows[start_row:], start=start_row):
            cells = [c.text.strip() for c in row.cells]
            if self._is_notes_or_empty(cells):
                continue
            try:
                nerve_name = cells[name_idx].strip()
                if not nerve_name:
                    continue
                data.append({
                    "Nerve": nerve_name,
                    "Amp": self._first_numeric_token(cells[amp_idx] if amp_idx < len(cells) else "--"),
                    "CV": self._first_numeric_token(cells[cv_idx] if cv_idx < len(cells) else "--"),
                    "DML": self._first_numeric_token(cells[dml_idx] if dml_idx is not None and dml_idx < len(cells) else "--"),
                })
            except Exception as exc:
                write_log(f"Saltata riga sensory {row_idx} malformata: {exc}")
                continue

        write_log(f"Estrazione Sensory completata. {len(data)} righe trovate.")
        return data

    def _parse_fwave_table(self, table, inherited_headers=None, start_row=1):
        write_log("--- Avvio parsing _parse_fwave_table ---")
        data = []
        raw_header = inherited_headers or [cell.text.strip().replace("\n", " ") for cell in table.rows[0].cells]
        write_log(f"Headers Grezzi F-Wave: {raw_header}")

        name_idx = self._find_col(raw_header, "f-wave nerves", "fwave nerves", "nerve") or 0
        mamp_idx = self._find_col(raw_header, "m-amplitude[mv]", "m amp", "m-amplitude", "mamp")
        fmin_idx = self._find_col(raw_header, "fmin[ms]", "f-min[ms]", "f min", "minimum")
        persist_idx = self._find_col(raw_header, "f/m[%]", "persist[%]", "persistence", "f/m")

        write_log(f"Colonne F-Wave: name={name_idx}, mamp={mamp_idx}, fmin={fmin_idx}, persist={persist_idx}")
        if fmin_idx is None or persist_idx is None:
            write_log("ERRORE: colonne F-Wave essenziali mancanti (Fmin, F/M or Persist).")
            return []

        for row_idx, row in enumerate(table.rows[start_row:], start=start_row):
            cells = [c.text.strip() for c in row.cells]
            if self._is_notes_or_empty(cells):
                continue
            try:
                nerve_name = cells[name_idx].strip()
                if not nerve_name:
                    continue
                data.append({
                    "Nerve": nerve_name,
                    "M-Amp": self._first_numeric_token(cells[mamp_idx] if mamp_idx is not None and mamp_idx < len(cells) else "--"),
                    "Fmin": self._first_numeric_token(cells[fmin_idx] if fmin_idx < len(cells) else "--"),
                    "Persist": self._first_numeric_token(cells[persist_idx] if persist_idx < len(cells) else "--", allow_percent=True),
                })
            except Exception as exc:
                write_log(f"Saltata riga F-Wave {row_idx} malformata: {exc}")
                continue

        write_log(f"Estrazione F-Wave completata. {len(data)} righe trovate.")
        return data
