#!/usr/bin/env python3
"""Deprecated wrapper. Polona retired GET /api/entities/ (404).

Use harvest_gazeta.py, which talks to /api/search-service and downloads
OCR text (not 10MB image PDFs) for Gazeta Śledcza issues that mention Kowel.
"""

from harvest_gazeta import main

if __name__ == "__main__":
    raise SystemExit(main())
