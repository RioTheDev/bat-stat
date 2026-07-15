from __future__ import annotations

import sys
from pathlib import Path

from constants import TEMPLATE_NAME


def default_template_path() -> Path:
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates = [
            Path(bundle_dir) / TEMPLATE_NAME,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

    installed_template = Path(sys.prefix) / TEMPLATE_NAME
    if installed_template.exists():
        return installed_template

    return Path(__file__).with_name(TEMPLATE_NAME)
