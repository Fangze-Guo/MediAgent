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
    ap.add_argument("--in-dir", required=True, help="上一步产物目录（含 model/model.bin）")
    ap.add_argument("--out-dir", required=True, help="本步骤产物目录（写 report.json）")
    args = ap.parse_args()

    IN_DIR = Path(args.in_dir).expanduser().resolve()
    OUT_DIR = Path(args.out_dir).expanduser().resolve()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    model_path = IN_DIR / "model" / "model.bin"
    report_path = OUT_DIR / "report.json"

    print("[evaluate] start", flush=True)
    if not model_path.exists():
        log({"event":"error","msg":f"model/model.bin not found in {IN_DIR}"})
        sys.exit(2)

    for i in range(1, 6):
        time.sleep(0.12)
        log({"event":"progress","stage":"evaluate","pct":i*20})

    metrics = {
        "accuracy": round(random.uniform(0.80, 0.95), 4),
        "f1": round(random.uniform(0.75, 0.92), 4),
    }
    report_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    log({"event":"artifact","path":str(report_path)})
    log({"event":"evaluate_done","ok":True,"metrics":metrics,"out_dir":str(OUT_DIR)})

if __name__ == "__main__":
    main()
