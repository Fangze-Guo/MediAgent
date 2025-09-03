# scripts/resize_image.py
import sys, os
from PIL import Image, ImageOps

def main():
    print("[resize] start", flush=True)
    if len(sys.argv) < 5:
        print("[ERROR] usage: resize_image.py <input> <output> <width> <height>", flush=True)
        sys.exit(2)

    inp, outp, w, h = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])

    if not os.path.exists(inp):
        print(f"[ERROR] input not found: {inp}", flush=True)
        sys.exit(2)

    # 可读性预检（避免某些云盘占位/权限问题卡住）
    try:
        with open(inp, "rb") as f:
            f.read(1)
    except Exception as e:
        print(f"[ERROR] cannot read file: {e!r}", flush=True)
        sys.exit(2)

    try:
        with Image.open(inp) as im:
            im = ImageOps.exif_transpose(im)  # 处理EXIF方向
            im = im.resize((w, h))
            out_dir = os.path.dirname(outp)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            im.save(outp)
        print(f"saved: {outp}", flush=True)
    except Exception as e:
        print(f"[ERROR] {e!r}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
