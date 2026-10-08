"""Receipt and handwritten-list photo reading for ``POST /parse-image`` (issues #61, #68).

| Module | Job |
|---|---|
| ``image.py`` | magic-byte sniffing, size limits, Pillow decode, EXIF rotation, downscale; all in memory |
| ``providers.py`` | the ``Provider`` protocol and the fake, Tesseract and Claude vision providers |
| ``pricing.py`` | the synchronous price table and the per-image cost estimate |
| ``config.py`` | the ``OCR_*`` environment variables |
| ``usage.py`` | the monthly cap on images and estimated dollars (table ``ocr_usage``, no user id) |
| ``rows.py`` | OCR lines to resolved ``ParsedRow`` s and ``unresolved`` lines, never a guess |

The image and the raw OCR text are never written anywhere (decision D11); see docs/ocr.md.
"""
