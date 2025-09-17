#!/usr/bin/env python3
import sys, time, json, shutil, argparse, os
from pathlib import Path
from urllib.parse import urlparse
try:
    import requests
except Exception:
    requests = None

def log(o): print(json.dumps(o, ensure_ascii=False), flush=True)
def ensure_line_buffer():
    try: sys.stdout.reconfigure(line_buffering=True)
    except Exception: pass

def copy_tree(src: Path, dst: Path):
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(src, dst)

def ingest_from_local(path_str: str, raw_dir: Path):
    p = Path(path_str).expanduser().resolve()
    if p.is_dir():
        copy_tree(p, raw_dir)
        return [{"event":"artifact","path":str(raw_dir)}]
    elif p.is_file():
        raw_dir.mkdir(parents=True, exist_ok=True)
        dst = raw_dir / p.name
        shutil.copy2(p, dst)
        return [{"event":"artifact","path":str(dst)}]
    else:
        raise FileNotFoundError(f"本地路径不存在: {p}")

def ingest_from_http(url: str, raw_dir: Path):
    if requests is None:
        raise RuntimeError("需要 requests (pip install requests)")
    raw_dir.mkdir(parents=True, exist_ok=True)
    name = Path(urlparse(url).path).name or "downloaded.bin"
    dst = raw_dir / name
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk: f.write(chunk)
    return [{"event":"artifact","path":str(dst)}]

def ingest_from_dummy(raw_dir: Path):
    raw_dir.mkdir(parents=True, exist_ok=True)
    dst = raw_dir / "raw.txt"
    dst.write_text("hello, this is raw data.\n", encoding="utf-8")
    return [{"event":"artifact","path":str(dst)}]

def main():
    ensure_line_buffer()
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="file/dir/http(s)/dummy/s3(预留)")
    ap.add_argument("--out-dir", required=True, help="本步骤产物目录（由上层任务管理器决定）")
    args = ap.parse_args()

    OUT_DIR = Path(args.out_dir).expanduser().resolve()
    raw_dir = OUT_DIR / "raw"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    log({"event":"ingest_start","source":args.source,"out_dir":str(OUT_DIR)})

    url = urlparse(args.source)
    artifacts = []
    try:
        if url.scheme in ("http","https"):
            artifacts = ingest_from_http(args.source, raw_dir)
        elif url.scheme in ("file",""):
            path_like = url.path if url.scheme == "file" else args.source
            artifacts = ingest_from_local(path_like, raw_dir)
        elif url.scheme == "dir":
            artifacts = ingest_from_local(url.path, raw_dir)
        elif url.scheme == "dummy":
            artifacts = ingest_from_dummy(raw_dir)
        elif url.scheme == "s3":
            raise NotImplementedError("s3:// 暂未实现")
        else:
            artifacts = ingest_from_local(args.source, raw_dir)

        for i in range(1, 6):
            time.sleep(0.12)
            log({"event":"progress","stage":"ingest","pct":i*20})

        for a in artifacts: log(a)
        log({"event":"ingest_done","ok":True,"out_dir":str(OUT_DIR)})
    except Exception as e:
        log({"event":"error","msg":str(e)})
        sys.exit(2)

if __name__ == "__main__":
    main()
