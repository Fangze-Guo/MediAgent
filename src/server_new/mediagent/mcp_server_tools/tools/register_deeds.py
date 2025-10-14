#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
register_deeds.py —— 使用 linearBCV + deedsBCV 将每个病人目录中的 C2.nii.gz 配准到 C0.nii.gz。
输入 (--in-dir)：可以是含多个病人目录的根目录，也可以是单个病人目录。
输出 (--out-dir)：与输入结构相同，每个病人下生成配准结果。

结构示例：
  输入：
    ├─ Patient001
    │   ├─ C0.nii.gz
    │   └─ C2.nii.gz
  输出：
    ├─ Patient001
        ├─ C0.nii.gz (copy)
        ├─ C2.nii.gz (已配准)

二进制文件 linearBCV / deedsBCV 放在脚本同级目录的 ./bin/ 文件夹。
- 若为 Windows 可执行（PE），直接本地运行；
- 若为 Linux 可执行（ELF），在 Windows 上将自动通过 WSL 运行（并自动转换路径）。
"""

import os
import sys
import json
import shutil
import stat
import time
import subprocess
from pathlib import Path
from typing import Callable, List, Tuple, Dict

# -------------------- 日志/基础 --------------------

def ensure_line_buffer():
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

def jlog(obj: dict):
    """以 JSON 行输出日志，任何异常都不阻塞"""
    try:
        print(json.dumps(obj, ensure_ascii=False), flush=True)
    except Exception as e:
        # 兜底：尽量不让日志丢失
        try:
            print(json.dumps({"event": "log_error", "fallback": str(obj), "err": str(e)}, ensure_ascii=False),
                  flush=True)
        except Exception:
            pass

def sane(p: str | Path) -> Path:
    return Path(str(p)).expanduser().resolve()

# -------------------- 可执行/平台探测 --------------------

def _read_magic(p: Path, n: int = 4) -> bytes:
    try:
        with open(p, "rb") as f:
            return f.read(n)
    except Exception:
        return b""

def is_pe_windows_exe(p: Path) -> bool:
    return _read_magic(p, 2) == b"MZ"

def is_elf(p: Path) -> bool:
    return _read_magic(p, 4) == b"\x7fELF"

def is_executable_bit_set(p: Path) -> bool:
    try:
        if os.name == "nt":
            return p.exists()
        mode = p.stat().st_mode
        return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
    except Exception:
        return False

def resolve_tool(bin_dir: Path, base: str) -> Path:
    candidates = [
        bin_dir / base,
        bin_dir / f"{base}.exe",
        bin_dir / f"{base}.cmd",
        bin_dir / f"{base}.bat",
    ]
    try:
        for f in bin_dir.iterdir():
            if f.is_file() and f.stem.lower() == base.lower():
                candidates.append(f)
    except FileNotFoundError:
        pass

    seen: set[str] = set()
    for c in candidates:
        key = str(c.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        if c.exists() and is_executable_bit_set(c):
            return c

    raise FileNotFoundError(
        f"Cannot find executable for '{base}' under {bin_dir}. "
        f"Tried: " + ", ".join(str(x) for x in candidates)
    )

# -------------------- WSL 适配 --------------------

def win_path_to_wsl(p: Path) -> str:
    s = str(p)
    if len(s) >= 2 and s[1] == ":":
        drive = s[0].lower()
        rest = s[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return s.replace("\\", "/")

def has_wsl() -> bool:
    if os.name != "nt":
        return False
    try:
        # 执行一个极快的 no-op
        rc = subprocess.call(["wsl", "true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return rc == 0
    except FileNotFoundError:
        return False

def build_cmd_with_runner(
    runner: str,  # "direct" or "wsl"
    exe: Path,
    args: List[str],
    path_map: Callable[[str], str]
) -> List[str]:
    if runner == "wsl":
        exe_wsl = win_path_to_wsl(exe)
        args_wsl = [path_map(a) for a in args]
        return ["wsl", exe_wsl, *args_wsl]
    else:
        return [str(exe), *args]

# -------------------- 子进程执行（带诊断） --------------------

def explain_windows_rc(rc: int) -> str | None:
    """常见 Windows 异常码提示"""
    if rc == 3221225781:  # 0xC0000135
        return "缺少依赖 DLL（STATUS_DLL_NOT_FOUND）"
    if rc == 3221225501:  # 0xC000001D
        return "非法指令（CPU 不支持当前指令集，尝试用 make SLOW=1 重编译）"
    return None

def run_and_stream(cmd: List[str]):
    jlog({"event": "exec", "cmd": " ".join(cmd)})
    try:
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
            assert proc.stdout
            for line in proc.stdout:
                # 直接透传 BCV 输出，便于定位
                print(line.rstrip(), flush=True)
            rc = proc.wait()
    except FileNotFoundError as e:
        raise RuntimeError(f"可执行文件不存在：{cmd[0]} ({e})")
    except OSError as e:
        raise RuntimeError(f"无法启动进程：{cmd[0]} ({e})")

    if rc != 0:
        more = explain_windows_rc(rc) if os.name == "nt" else None
        raise RuntimeError(f"Command failed (rc={rc}): {' '.join(cmd)}" + (f" —— {more}" if more else ""))

# -------------------- 业务逻辑 --------------------

def is_patient_dir(p: Path) -> bool:
    return (p / "C0.nii.gz").is_file() and (p / "C2.nii.gz").is_file()

def try_probe_version(exe_path: Path, runner: str) -> str:
    """尝试执行 `-h` 抓首行，失败不致命"""
    try:
        if runner == "wsl":
            cmd = ["wsl", win_path_to_wsl(exe_path), "-h"]
        else:
            cmd = [str(exe_path), "-h"]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=3)
        line1 = (out.splitlines() or [""])[0][:200]
        return line1
    except Exception as e:
        return f"probe_failed: {type(e).__name__}"

def preflight(in_dir: Path, out_dir: Path, linearBCV: Path, deedsBCV: Path, runner: str):
    # 目录
    if not in_dir.exists():
        raise FileNotFoundError(f"in-dir 不存在：{in_dir}")
    if not out_dir.exists():
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"无法创建 out-dir：{out_dir} ({e})")

    # 可执行
    for p in (linearBCV, deedsBCV):
        if not p.exists():
            raise FileNotFoundError(f"可执行不存在：{p}")
        if os.name == "nt":
            if not (is_pe_windows_exe(p) or is_elf(p)):
                jlog({"event": "warn", "msg": f"{p.name} 既不是 PE 也不是 ELF，可能不是可执行"})
        else:
            if not is_executable_bit_set(p):
                raise PermissionError(f"{p} 没有可执行权限（chmod +x）")

    # WSL
    if runner == "wsl" and not has_wsl():
        raise RuntimeError("检测到 ELF 可执行，但系统未检测到 WSL。请安装启用 WSL 或使用 Windows 版本可执行。")

    # 试探版本（不致命，纯信息）
    jlog({
        "event": "preflight",
        "linearBCV_probe": try_probe_version(linearBCV, runner),
        "deedsBCV_probe": try_probe_version(deedsBCV, runner),
    })

def run_registration(
    runner: str,
    linearBCV: Path,
    deedsBCV: Path,
    fixed_nii_path: Path,
    moving_nii_path: Path,
    dst_nii_path: Path
):
    dst_nii_path.parent.mkdir(parents=True, exist_ok=True)

    if runner == "wsl":
        path_map = lambda s: win_path_to_wsl(Path(s))
    else:
        path_map = lambda s: str(s)

    affine_matrix_path = str(dst_nii_path)
    new_affine_matrix_path = affine_matrix_path + "_matrix.txt"
    try:
        if Path(new_affine_matrix_path).exists():
            os.remove(new_affine_matrix_path)
    except FileNotFoundError:
        pass

    t0 = time.time()
    # Step 1: 线性
    cmd1 = build_cmd_with_runner(
        runner,
        linearBCV,
        ["-F", str(fixed_nii_path), "-M", str(moving_nii_path), "-O", affine_matrix_path],
        path_map
    )
    run_and_stream(cmd1)
    if not Path(new_affine_matrix_path).exists():
        raise RuntimeError(f"Affine matrix not produced: {new_affine_matrix_path}")

    # Step 2: 非线性
    cmd2 = build_cmd_with_runner(
        runner,
        deedsBCV,
        ["-F", str(fixed_nii_path), "-M", str(moving_nii_path), "-O", str(dst_nii_path), "-A", str(new_affine_matrix_path)],
        path_map
    )
    run_and_stream(cmd2)

    new_dst_path = dst_nii_path.parent / (dst_nii_path.name + "_deformed.nii.gz")
    if not new_dst_path.exists():
        raise RuntimeError(f"deedsBCV did not produce {new_dst_path}")
    if new_dst_path.stat().st_size == 0:
        raise RuntimeError(f"deedsBCV 输出空文件：{new_dst_path}")

    shutil.move(new_dst_path, dst_nii_path)

    # 清理
    for p in [
        Path(new_affine_matrix_path),
        dst_nii_path.parent / (dst_nii_path.name + "_displacements.dat"),
    ]:
        if p.exists():
            with contextlib_suppress(Exception):
                os.remove(p)

    jlog({"event": "converted", "dst": str(dst_nii_path), "secs": round(time.time() - t0, 2)})

# 小工具：安全 suppress
class contextlib_suppress:
    def __init__(self, *exceptions):
        self.exceptions = exceptions
    def __enter__(self): return None
    def __exit__(self, exc_type, exc, tb): return exc_type and issubclass(exc_type, self.exceptions or (Exception,))

# -------------------- 主入口 --------------------

def main():
    ensure_line_buffer()
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True, help="输入 NIfTI 根目录或单病人目录")
    ap.add_argument("--out-dir", required=True, help="输出目录")
    args = ap.parse_args()

    in_dir  = sane(args.in_dir)
    out_dir = sane(args.out_dir)
    bin_dir = Path(__file__).resolve().parent / "bin"

    linearBCV_p = resolve_tool(bin_dir, "linearBCV")
    deedsBCV_p  = resolve_tool(bin_dir, "deedsBCV")

    # Windows + ELF → WSL，其余 direct
    runner = "wsl" if (os.name == "nt" and (is_elf(linearBCV_p) or is_elf(deedsBCV_p))) else "direct"

    jlog({
        "event": "env",
        "bin_dir": str(bin_dir),
        "linearBCV": str(linearBCV_p),
        "deedsBCV": str(deedsBCV_p),
        "runner": runner
    })

    # 体检
    preflight(in_dir, out_dir, linearBCV_p, deedsBCV_p, runner)

    out_dir.mkdir(parents=True, exist_ok=True)
    jlog({"event": "start", "in_dir": str(in_dir), "out_dir": str(out_dir)})

    # 病人列表
    if is_patient_dir(in_dir):
        patients = [in_dir]
    else:
        patients = [p for p in in_dir.iterdir() if p.is_dir() and is_patient_dir(p)]

    total = len(patients)
    done = 0
    failed: List[Tuple[str, str]] = []
    jlog({"event": "scan", "patients": total})

    for pdir in patients:
        pid = pdir.name
        c0 = pdir / "C0.nii.gz"
        c2 = pdir / "C2.nii.gz"

        dst_p = out_dir / pid
        dst_p.mkdir(parents=True, exist_ok=True)
        dst_c0 = dst_p / "C0.nii.gz"
        dst_c2 = dst_p / "C2.nii.gz"

        if not dst_c0.exists():
            shutil.copy2(c0, dst_c0)

        jlog({"event": "process", "patient": pid})
        try:
            if not dst_c2.exists():
                run_registration(
                    runner=runner,
                    linearBCV=linearBCV_p,
                    deedsBCV=deedsBCV_p,
                    fixed_nii_path=dst_c0,
                    moving_nii_path=c2,
                    dst_nii_path=dst_c2
                )
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            failed.append((pid, msg))
            jlog({"event": "error_patient", "patient": pid, "msg": msg})
        finally:
            done += 1
            jlog({"event": "progress", "done": done, "total": total, "pct": int(done / total * 100)})

    ok = len(failed) == 0
    jlog({"event": "summary", "ok": ok, "failed": [{"patient": p, "msg": m} for p, m in failed]})
    jlog({"event": "done", "ok": ok, "out_dir": str(out_dir)})

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        jlog({"event": "error", "msg": "用户中断 (KeyboardInterrupt)"})
        sys.exit(130)
    except Exception as e:
        jlog({"event": "error", "msg": f"{type(e).__name__}: {e}"})
        sys.exit(2)
