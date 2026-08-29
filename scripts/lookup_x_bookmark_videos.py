#!/usr/bin/env python3
"""X 收藏短视频查找 — 主脚本（可移植版）。

用法:
  python3 lookup_x_bookmark_videos.py                # 全流程: 扫描JSON→bird取时长→输出短视频清单
  python3 lookup_x_bookmark_videos.py --minutes 10    # 自定义阈值（默认 10 分钟）
  python3 lookup_x_bookmark_videos.py --bookmarks-dir /path/to/x-bookmarks

依赖: bird CLI（可执行文件需在 PATH 或 /usr/local/bin/bird）、python3 ≥ 3.8（纯 stdlib）。
换机: 见 skill references/porting.md（装 bird + 认证 + 路径适配）。
输出: stdout 短视频清单；JSON 全量结果存 /tmp/x_bookmark_videos.json。
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

DEFAULT_DIR = "/root/obsidianHermes/01_raw/notes/x-bookmarks"
CANDIDATE_DIRS = [
    "/root/obsidianHermes/01_raw/notes/x-bookmarks",
    os.path.expanduser("~/obsidianHermes/01_raw/notes/x-bookmarks"),
    os.path.expanduser("~/vault/01_raw/notes/x-bookmarks"),
    os.path.expanduser("~/Obsidian/01_raw/notes/x-bookmarks"),
]
BIRD_CANDIDATES = ["bird", "/usr/local/bin/bird", "/usr/bin/bird"]


def find_bird():
    """定位 bird 可执行文件；找不到返回 None。"""
    for cand in BIRD_CANDIDATES:
        p = shutil.which(cand) or (cand if os.path.isfile(cand) else None)
        if p:
            return p
    return None


def find_bookmarks_dir(explicit=None):
    """定位 bookmarks 目录：显式参数 > 默认 > 候选路径探测。"""
    if explicit:
        if os.path.isdir(explicit):
            return explicit
        print(f"[warn] --bookmarks-dir 不存在: {explicit}", file=sys.stderr)
    for d in [DEFAULT_DIR] + CANDIDATE_DIRS:
        if os.path.isdir(d) and glob.glob(os.path.join(d, "*-smaug-bookmarks-batch-prepared.json")):
            return d
    return None


def scan_bookmarks(bookmarks_dir):
    """扫描所有批次 prepared JSON，返回: records(list), vid_ids(set), ext_urls(set)."""
    records = []
    vid_ids = set()
    ext_urls = set()
    for f in sorted(glob.glob(os.path.join(bookmarks_dir, "*-smaug-bookmarks-batch-prepared.json"))):
        date = os.path.basename(f).split("-smaug")[0]
        with open(f) as fh:
            data = json.load(fh)
        for bm in data.get("bookmarks", []):
            for link in (bm.get("links") or []):
                if not isinstance(link, dict):
                    continue
                ltype = link.get("type", "")
                url = (link.get("url") or link.get("expanded") or link.get("original") or "")
                rec = {"date": date, "author": bm.get("author"), "bm_id": bm.get("id")}
                if "/video/" in url:
                    m = re.search(r"/status/(\d+)/video", url)
                    if m:
                        rec["kind"] = "x_video"
                        rec["vid_id"] = m.group(1)
                        rec["url"] = url
                        records.append(rec)
                        vid_ids.add(m.group(1))
                elif ltype == "video" and url:
                    rec["kind"] = "ext_video"
                    rec["vid_id"] = None
                    rec["url"] = url
                    records.append(rec)
                    ext_urls.add(url)
    return records, vid_ids, ext_urls


def fetch_duration(bird, tid, timeout=40):
    """bird read 单条推文，返回 durationMs 或 None（已删/无视频）。"""
    try:
        r = subprocess.run([bird, "read", tid, "--json"],
                           capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip()
        if not out:
            return None
        d = json.loads(out)
        for m in (d.get("media") or []):
            if m.get("durationMs") is not None:
                return m["durationMs"]
        return None
    except Exception:
        return None


def batch_fetch(bird, vid_ids, sleep=0.8):
    """批量取时长，返回 {tid: durationMs}。"""
    results = {}
    for i, tid in enumerate(sorted(vid_ids)):
        results[tid] = fetch_duration(bird, tid)
        if (i + 1) % 10 == 0:
            print(f"  progress {i+1}/{len(vid_ids)}", file=sys.stderr, flush=True)
        time.sleep(sleep)
    return results


def fmt(ms):
    if ms is None:
        return "N/A"
    s = ms // 1000
    return f"{s//60}m{s%60:02d}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=10)
    ap.add_argument("--bookmarks-dir", default=None)
    args = ap.parse_args()
    threshold_ms = args.minutes * 60000

    # 1. 依赖检测（可移植性核心）
    bird = find_bird()
    if not bird:
        print("[ERROR] 找不到 bird CLI。请先安装并认证：", file=sys.stderr)
        print("  1) npm install -g bird-cli（或按 skill references/porting.md）", file=sys.stderr)
        print("  2) 配置 X 登录 cookie（--auth-token + --ct0 或浏览器 profile）", file=sys.stderr)
        sys.exit(1)

    # 2. 数据源定位
    bm_dir = find_bookmarks_dir(args.bookmarks_dir)
    if not bm_dir:
        print("[ERROR] 找不到 bookmarks 数据目录。用 --bookmarks-dir 显式指定。", file=sys.stderr)
        sys.exit(1)

    records, vid_ids, ext_urls = scan_bookmarks(bm_dir)
    print(f"扫描 {bm_dir}: {len(records)} 条视频记录, "
          f"{len(vid_ids)} 个唯一 X 视频推文, {len(ext_urls)} 个外部链接", file=sys.stderr)

    # 3. 批量取时长
    durations = batch_fetch(bird, vid_ids)

    # 4. 汇总（按视频推文 id 去重）
    vid_map = {}
    for rec in records:
        if rec["kind"] != "x_video":
            continue
        tid = rec["vid_id"]
        v = vid_map.setdefault(tid, {"durationMs": durations.get(tid), "refs": []})
        v["refs"].append(f"{rec['date']}@{rec['author']}")

    short = {k: v for k, v in vid_map.items()
             if v["durationMs"] is not None and v["durationMs"] <= threshold_ms}
    long = {k: v for k, v in vid_map.items()
            if v["durationMs"] is not None and v["durationMs"] > threshold_ms}
    none = {k: v for k, v in vid_map.items() if v["durationMs"] is None}

    print(f"\n=== 短视频 (≤{args.minutes}min): {len(short)} 个唯一视频 ===")
    for tid in sorted(short, key=lambda t: short[t]["durationMs"]):
        v = short[tid]
        print(f"  {fmt(v['durationMs'])} | https://x.com/i/status/{tid} | refs: {', '.join(v['refs'])}")

    print(f"\n=== 长视频 (> {args.minutes}min): {len(long)} ===")
    for tid in sorted(long, key=lambda t: long[t]["durationMs"]):
        v = long[tid]
        print(f"  {fmt(v['durationMs'])} | https://x.com/i/status/{tid} | refs: {', '.join(v['refs'])}")

    print(f"\n=== 已删/无法读取: {len(none)} ===")
    for tid, v in none.items():
        print(f"  https://x.com/i/status/{tid} | refs: {', '.join(v['refs'])}")

    print(f"\n=== 外部视频链接: {len(ext_urls)}（多为 YouTube 频道/长节目，需单独验证） ===")
    for u in sorted(ext_urls):
        print(f"  {u}")

    with open("/tmp/x_bookmark_videos.json", "w") as fh:
        json.dump({"short": short, "long": long, "none": none, "ext": sorted(ext_urls)},
                  fh, ensure_ascii=False, indent=1)
    print("\nfull results: /tmp/x_bookmark_videos.json")


if __name__ == "__main__":
    main()
