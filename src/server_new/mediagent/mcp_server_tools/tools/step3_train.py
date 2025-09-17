#!/usr/bin/env python3
import sys, time, json, random, argparse
from pathlib import Path

def log(o): print(json.dumps(o, ensure_ascii=False), flush=True)
def ensure_line_buffer():
    try: sys.stdout.reconfigure(line_buffering=True)
    except Exception: pass

def main():
    ensure_line_buffer()
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True, help="上一步产物目录（含 clean/clean.txt）")
    ap.add_argument("--out-dir", required=True, help="本步骤产物目录（含 model/）")
    ap.add_argument("--epochs", type=int, default=5)
    args = ap.parse_args()

    IN_DIR = Path(args.in_dir).expanduser().resolve()
    OUT_DIR = Path(args.out_dir).expanduser().resolve()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    clean_path = IN_DIR / "clean" / "clean.txt"
    model_dir = OUT_DIR / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "model.bin"

    print("[train] start", flush=True)
    if not clean_path.exists():
        log({"event":"error","msg":f"clean/clean.txt not found in {IN_DIR}"})
        sys.exit(2)

    loss = 1.0
    for epoch in range(1, args.epochs+1):
        time.sleep(0.16)
        loss *= random.uniform(0.7, 0.95)
        log({"event":"epoch","epoch":epoch,"loss":round(loss,4)})

    model_path.write_bytes(b"\x00\x01\x02")
    log({"event":"artifact","path":str(model_path)})
    log({"event":"train_done","ok":True,"final_loss":round(loss,4),"out_dir":str(OUT_DIR)})

if __name__ == "__main__":
    main()
