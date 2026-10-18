"""The daily mail, as the systemd unit starts it: python -m app.entry.cli.report"""

from __future__ import annotations

import sys

from app.features.collect.service import send_report

if __name__ == "__main__":
    sys.exit(send_report())
