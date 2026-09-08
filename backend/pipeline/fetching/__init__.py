"""Shared transport for the source adapters: HTTP, search, and text extraction.

Not a source. Every adapter in ``pipeline.sources`` reaches for the same pooled
client, the same browser headers and the same proxy retry, so they live here
rather than inside one adapter that the others import from sideways.
"""

from __future__ import annotations
