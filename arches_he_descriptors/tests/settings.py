import os
import sys
from pathlib import Path

from arches_he_descriptors.settings import *

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "arches"))

DATABASES = {
    **DATABASES,
    "default": {
        **DATABASES["default"],
        "HOST": os.environ.get("PGHOST", DATABASES["default"]["HOST"]),
    },
}
SILENCED_SYSTEM_CHECKS = list(SILENCED_SYSTEM_CHECKS) + [
    "arches.E001",
    "arches.W001",
]
