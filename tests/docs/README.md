# ATBOffice Test Documents & Corpora

This directory contains real-world office production test documents used for format compatibility, parser verification, headless loss audit, and visual rendering checks.

## Structure

```text
tests/docs/
├── word/                     # Microsoft Word documents (Curated, committed)
│   ├── docx/                 # OOXML WordprocessingML (.docx, .docm)
│   └── doc/                  # Binary Word 97-2003 OLE2 (.doc)
├── excel/                    # Microsoft Excel spreadsheets (Curated, committed)
│   ├── xlsx/                 # OOXML SpreadsheetML (.xlsx, .xlsm)
│   └── xls/                  # Binary Excel 97-2003 BIFF8 (.xls)
├── powerpoint/               # Microsoft PowerPoint presentations (Curated, committed)
│   ├── pptx/                 # OOXML PresentationML (.pptx, .pptm)
│   └── ppt/                  # Binary PowerPoint 97-2003 (.ppt)
└── full_corpus/              # [GITIGNORED] Complete 6,200+ external files
    ├── manifest.json         # SHA-256 and metadata manifest
    ├── word/
    ├── excel/
    └── powerpoint/
```

## Curated In-Tree Fixtures

The repository includes a bounded, curated collection of 150 real production files (~5.6 MB total) across all 6 key formats:
- **Word:** 25 `.docx` files + 25 `.doc` files (tables, fields, revisions, fonts, shapes).
- **Excel:** 25 `.xlsx` files + 25 `.xls` files (formulas, charts, pivot caches, conditional styles).
- **PowerPoint:** 25 `.pptx` files + 25 `.ppt` files (layouts, slide masters, textboxes, transitions).

These files run instantly in local `pytest` and offline CI without requiring external network access.

## Full Corpora (6,200+ Files)

The full corpus is pulled from pinned public open-source QA suites:
1. **LibreOffice Core QA** (`sw/qa`, `sc/qa`, `sd/qa`, `oox/qa`) - Real-world bug report attachments accumulated over 20+ years.
2. **Apache POI** (`test-data`) - Extensive collection of edge cases across OLE2 binary and OOXML formats.
3. **Microsoft Open-XML-SDK** (`test`) - Official conformance test files.

To download or refresh the complete 6,200+ test corpus locally into `tests/docs/full_corpus/`:

```bash
python scripts/fetch_corpora.py --dest tests/docs/full_corpus --curate
```
