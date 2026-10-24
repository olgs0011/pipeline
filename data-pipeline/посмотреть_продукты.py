# посмотреть_продукты.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pipeline.sources.fedstat import FedstatClient
from pipeline.logging import setup_logging

setup_logging()

with FedstatClient() as client:
    meta = client.fetch_indicator_meta(43226)
    for oid, filt in meta.filters.items():
        if "продукт" in filt.title.lower():
            print(f"\n[{oid}] {filt.title}")
            for v in filt.values:
                print(f"  {v.id}: {v.title!r}")