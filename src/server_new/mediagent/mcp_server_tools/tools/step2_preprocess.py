#!/usr/bin/env python3
import sys, time, json, argparse
from pathlib import Path

def log(o): print(json.dumps(o, ensure_ascii=False), flush=True)
def ensure_line_buffer():
    try: sys.stdout.reconfigure(line_buffering=True)
    except Exception: pass

def main():
    ensure_line_buffer()
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True, help="上一步产物目录（含 raw/）")
    ap.add_argument("--out-dir", required=True, help="本步骤产物目录（含 clean/）")
    args = ap.parse_args()

    IN_DIR = Path(args.in_dir).expanduser().resolve()
    OUT_DIR = Path(args.out_dir).expanduser().resolve()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    raw_dir = IN_DIR / "raw"
    clean_dir = OUT_DIR / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    out_path = clean_dir / "clean.txt"

    print("[preprocess] start", flush=True)
    if not raw_dir.exists():
        log({"event":"error","msg":f"raw/ not found in {IN_DIR}"})
        sys.exit(2)

    texts = []
    for p in raw_dir.rglob("*.txt"):
        texts.append(p.read_text(encoding="utf-8"))
    if not texts:
        texts = ["no raw .txt found, continue.\n"]

    content = "\n".join(texts).upper().strip() + "\n"
    for i in range(1, 6):
        time.sleep(0.12)
        log({"event":"progress","stage":"preprocess","pct":i*20})

    out_path.write_text(content, encoding="utf-8")
    log({"event":"artifact","path":str(out_path)})
    log({"event":"preprocess_done","ok":True,"out_dir":str(OUT_DIR)})

if __name__ == "__main__":
    main()
