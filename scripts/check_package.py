"""Check the tracked archive used by HACS contains the complete runtime card."""

import json
import subprocess
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[1]
archive = subprocess.check_output(["git", "archive", "--format=zip", "HEAD"], cwd=root)
with ZipFile(BytesIO(archive)) as bundle:
    prefix = "custom_components/t2c_clermontferrand/"
    for name in ("manifest.json", "frontend.py", "www/t2c_clermont-ferrand_card.js"):
        assert prefix + name in bundle.namelist(), name
    card = bundle.read(prefix + "www/t2c_clermont-ferrand_card.js")
    assert card == bundle.read("frontend/src/t2c_clermont-ferrand_card.js")
    assert b"t2c-clermontferrand-card-editor" in card
    assert json.loads(bundle.read("hacs.json")).get("zip_release", False) is False
print("HACS source archive contains integration and self-contained card")
