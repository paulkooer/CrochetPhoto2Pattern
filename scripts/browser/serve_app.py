"""Start an isolated browser test server with upload-content acknowledgements.

Usage: .venv/bin/python scripts/browser/serve_app.py app/main.py [Streamlit flags]
"""
from __future__ import annotations

import sys

from streamlit.web import cli
from upload_ack import install_upload_ack

if __name__ == "__main__":
    install_upload_ack()
    sys.argv = ["streamlit", "run", *sys.argv[1:]]
    cli.main()
