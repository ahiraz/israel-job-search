#!/usr/bin/env python3
"""Entry point the skills run: python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py" <command> ..."""
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("israel-job-search needs Python 3.10 or newer")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from jobsearch.cli import main  # noqa: E402

sys.exit(main())
