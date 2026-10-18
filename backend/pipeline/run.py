"""The nightly collect run, as the systemd unit starts it: python -m pipeline.run"""

from __future__ import annotations

import sys

from app.features.collect.service import run_nightly

if __name__ == "__main__":
    sys.exit(run_nightly())
