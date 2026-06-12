"""Download the Hanoi EPW weather file for real EnergyPlus runs.

Usage: python scripts/download_epw.py
Saves to storage/raw/weather/hanoi.epw (the WEATHER_EPW default).
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "storage" / "raw" / "weather" / "hanoi.epw"

# climate.onebuilding.org — Hanoi Noi Bai Intl AP (matches the IDF Site:Location)
URLS = [
    "https://climate.onebuilding.org/WMO_Region_2_Asia/VNM_Vietnam/"
    "HN_Ha-Noi/VNM_HN_Hanoi-Noi.Bai.Intl.AP.488200_TMYx.zip",
]


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists():
        print(f"EPW already present: {DEST}")
        return
    import io
    import zipfile
    from urllib.request import urlopen

    for url in URLS:
        try:
            print(f"Downloading {url} ...")
            data = urlopen(url, timeout=120).read()
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                epw_names = [n for n in zf.namelist() if n.lower().endswith(".epw")]
                if not epw_names:
                    continue
                DEST.write_bytes(zf.read(epw_names[0]))
            print(f"Saved {DEST} ({DEST.stat().st_size // 1024} KB)")
            return
        except Exception as exc:
            print(f"  failed: {exc}")
    print("Could not download an EPW automatically. Get one from "
          "https://climate.onebuilding.org and save it as storage/raw/weather/hanoi.epw",
          file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
