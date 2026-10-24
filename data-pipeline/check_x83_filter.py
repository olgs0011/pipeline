# check_x83_filter.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pipeline.sources.fedstat import FedstatClient
from pipeline.logging import setup_logging

setup_logging()

with FedstatClient() as client:
    meta = client.fetch_indicator_meta(59205)
    for oid, filt in meta.filters.items():
        print(f"[{oid}] title={filt.title!r}")
        for v in filt.values[:15]:
            print(f"    {v.id}: {v.title!r}")