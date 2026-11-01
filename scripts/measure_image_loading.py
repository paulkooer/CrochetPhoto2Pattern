"""Measure one bounded image decode in a fresh macOS/Linux process."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image",type=Path)
    parser.add_argument("--mode",choices=("file","bytes"),default="bytes")
    parser.add_argument("--source-root",type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    if sys.platform not in ("darwin","linux"):
        parser.error("RSS measurement supports macOS/Linux only")
    import resource

    sys.path.insert(0,str(args.source_root.resolve()))
    from app.utils import images

    started=time.perf_counter()
    if args.mode=="file":
        result=images.load_image_file(args.image)
    else:
        with args.image.open("rb") as handle:
            data=handle.read(images.MAX_UPLOAD_MB*1024*1024+1)
        result=images.load_image_bytes(data)
    if result is None:
        parser.error("image failed the application's decode guards")
    digest=hashlib.sha256(result.tobytes()).hexdigest()
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(json.dumps({"mode":args.mode,"platform":sys.platform,"python":platform.python_version(),
        "size":result.size,"output_sha256":digest,
        "loader_sha256":hashlib.sha256(Path(images.__file__).read_bytes()).hexdigest(),
        "peak_rss_bytes":peak if sys.platform=="darwin" else peak*1024,
        "elapsed_s":round(time.perf_counter()-started,3)}))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
