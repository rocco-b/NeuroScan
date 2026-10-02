"""Isolated Microsoft Word/COM converter for legacy .doc files.

This helper is executed in a separate subprocess by file_processor.py. Keeping
Word automation out of the main process prevents a broken Office COM server from
freezing a full batch conversion.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        print("Usage: python word_com_convert.py input.doc output.docx", file=sys.stderr)
        return 2

    input_doc = str(Path(argv[0]).resolve())
    output_docx = str(Path(argv[1]).resolve())
    Path(output_docx).parent.mkdir(parents=True, exist_ok=True)

    word = None
    document = None
    try:
        import pythoncom  # type: ignore
        import win32com.client as win32  # type: ignore

        pythoncom.CoInitialize()
        word = win32.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        try:
            # Disable macros when available. Some Word versions may not expose this property.
            word.AutomationSecurity = 3
        except Exception:
            pass

        document = word.Documents.Open(
            input_doc,
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            Visible=False,
        )
        # 12 = wdFormatXMLDocument (.docx)
        try:
            document.SaveAs2(output_docx, FileFormat=12)
        except Exception:
            document.SaveAs(output_docx, FileFormat=12)
        document.Close(False)
        document = None
        if not os.path.exists(output_docx):
            print("Output file was not created", file=sys.stderr)
            return 1
        print(output_docx)
        return 0
    except Exception as exc:
        print(f"Word COM conversion failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            if document is not None:
                document.Close(False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass
        try:
            import pythoncom  # type: ignore
            pythoncom.CoUninitialize()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
