#!/usr/bin/env python3
"""anansi — YouTube links in, transcripts, video and audio out.

Standard library only. Every YouTube call goes through yt-dlp, which is
downloaded into ~/.cache/anansi/bin on first use (a yt-dlp on PATH wins).

  anansi fetch <links or any text containing them>   transcript documents
  anansi search "<query>" [-n 5]                     find videos
  anansi download <links> [--audio] [--out DIR]      mp4 / m4a files
  anansi web [--port N] [--no-open]                  local browser UI
  anansi web install | uninstall                     macOS: run the UI at login
  anansi doctor                                      check dependencies
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as core  # noqa: E402

LABEL = "com.anansi.web"


def err(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def ytdlp() -> str:
    path = core.ensure_ytdlp(log=err)
    threading.Thread(target=core.maybe_self_update, args=(path,), daemon=True).start()
    return path


# ─── Input & output helpers ─────────────────────────────────────────────────

def gather_text(args: list[str], file: str | None) -> str:
    """Links come from arguments, a file, or piped stdin, in that order."""
    parts = list(args)
    if file:
        parts.append(Path(file).read_text(encoding="utf-8", errors="replace"))
    if not parts and not sys.stdin.isatty():
        parts.append(sys.stdin.read())
    return "\n".join(parts)


def safe_filename(name: str, limit: int = 150) -> str:
    name = re.sub(r'[\x00-\x1f/\\:*?"<>|]', "_", name).strip(" .")
    return (name[:limit].rstrip(" .") or "untitled")


def clipboard_cmd() -> list[str] | None:
    if sys.platform == "darwin":
        return ["pbcopy"]
    if sys.platform.startswith("win"):
        return ["clip"]
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
        if shutil.which(cmd[0]):
            return cmd
    return None


def copy_to_clipboard(text: str) -> bool:
    cmd = clipboard_cmd()
    if not cmd:
        return False
    try:
        return subprocess.run(cmd, input=text, text=True, encoding="utf-8").returncode == 0
    except OSError:
        return False


def parse_search_json(doc: dict) -> list[dict]:
    """yt-dlp `-J --flat-playlist ytsearchN:` output -> plain result rows."""
    rows = []
    for e in doc.get("entries") or []:
        if not isinstance(e, dict) or not core.VALID_ID.match(str(e.get("id", ""))):
            continue
        dur = e.get("duration")
        views = e.get("view_count")
        rows.append({
            "id": e["id"],
            "url": f"https://www.youtube.com/watch?v={e['id']}",
            "title": e.get("title") or "",
            "channel": e.get("channel") or e.get("uploader") or "",
            "duration": core.format_duration(int(dur)) if isinstance(dur, (int, float)) else "",
            "views": int(views) if isinstance(views, (int, float)) else None,
        })
    return rows


# ─── fetch ──────────────────────────────────────────────────────────────────

def fetch_one(yt: str, vid: str, refresh: bool) -> dict:
    doc = None if refresh else core.cache_read_doc(vid)
    cached = doc is not None
    if doc is None:
        try:
            doc = core.fetch_document(yt, vid)
        except Exception as e:  # noqa: BLE001 — reported per video
            return {"id": vid, "status": "error", "error": str(e)}
        core.cache_write_doc(vid, doc)
    return {"id": vid, "status": "ok", "cached": cached, "document": doc,
            "path": str(core.cache_dir() / f"{vid}.txt"), **core.parse_header(doc)}


def cmd_fetch(a) -> int:
    ids = core.extract_video_ids(gather_text(a.links, a.file))
    if not ids:
        err("no YouTube links found (pass URLs, --file FILE, or pipe text in)")
        return 2
    yt = ytdlp()
    err(f"anansi: fetching {len(ids)} video(s)…")
    with ThreadPoolExecutor(core.WORKERS) as pool:
        results = list(pool.map(lambda v: fetch_one(yt, v, a.refresh), ids))

    ok = [r for r in results if r["status"] == "ok"]
    if a.out:
        out = Path(a.out).expanduser()
        out.mkdir(parents=True, exist_ok=True)
        for r in ok:
            p = out / f"{safe_filename(r['title'] or r['id'])} [{r['id']}].txt"
            p.write_text(r["document"], encoding="utf-8")
            r["path"] = str(p)
    merged = "\n".join(r["document"] for r in ok)
    if a.clipboard and ok:
        if not copy_to_clipboard(merged):
            err("clipboard unavailable — skipped")

    if a.json:
        print(json.dumps([{k: v for k, v in r.items() if k != "document"} for r in results], indent=2))
    elif a.stdout:
        print(merged, end="")
        for r in results:
            if r["status"] != "ok":
                err(f"✗ {r['id']}: {r['error']}")
    else:
        for r in results:
            if r["status"] == "ok":
                note = "" if r["has_transcript"] else "  (no transcript — metadata only)"
                print(f"✓ {r['title']} — {r['channel']} [{r['duration']}]{note}\n  {r['path']}")
            else:
                print(f"✗ https://www.youtube.com/watch?v={r['id']}: {r['error']}")
    err(f"anansi: {len(ok)}/{len(results)} fetched")
    return 0 if ok else 1


# ─── search ─────────────────────────────────────────────────────────────────

def cmd_search(a) -> int:
    yt = ytdlp()
    r = subprocess.run([yt, f"ytsearch{a.n}:{a.query}", "-J", "--flat-playlist", "--no-warnings"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        err(core.classify_stderr(r.stderr))
        return 1
    try:
        rows = parse_search_json(json.loads(r.stdout or "{}"))
    except ValueError:
        rows = []
    if not rows:
        err(f"no results for {a.query!r} (YouTube returned nothing — try other words)")
        return 1
    if a.json:
        print(json.dumps(rows, indent=2))
    else:
        for i, row in enumerate(rows, 1):
            views = f" · {row['views']:,} views" if row["views"] is not None else ""
            dur = f" · {row['duration']}" if row["duration"] else ""
            print(f"{i}. {row['title']} — {row['channel']}{dur}{views}\n   {row['url']}")
    return 0 if rows else 1


# ─── download ───────────────────────────────────────────────────────────────

def cmd_download(a) -> int:
    ids = core.extract_video_ids(gather_text(a.links, a.file))
    if not ids:
        err("no YouTube links found")
        return 2
    yt = ytdlp()
    kind = "audio" if a.audio else "video"
    out = Path(a.out).expanduser()
    if kind == "video" and not shutil.which("ffmpeg"):
        err("note: ffmpeg not found — falling back to a single-file mp4 (lower quality, may fail). "
            "macOS: brew install ffmpeg")
    failures = 0
    for vid in ids:
        last = [-10.0]

        def progress(pct: float, stage: str) -> None:
            if pct - last[0] >= 10 or pct >= 100:
                last[0] = pct
                err(f"  {vid} {stage} {pct:.0f}%")
        try:
            path = core.download_media(yt, vid, kind, out, on_progress=progress)
            print(path)
        except RuntimeError as e:
            failures += 1
            print(f"✗ https://www.youtube.com/watch?v={vid}: {e}")
    return 1 if failures == len(ids) else 0


# ─── web ────────────────────────────────────────────────────────────────────

def cmd_web(a) -> int:
    if a.action is None:
        return core.serve(a.port, not a.no_open)
    if sys.platform != "darwin":
        err("web install/uninstall is macOS-only")
        return 2
    plist = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)
    if a.action == "uninstall":
        plist.unlink(missing_ok=True)
        print("LaunchAgent removed.")
        return 0
    log = Path.home() / "Library" / "Logs" / "anansi-web.log"
    plist.parent.mkdir(parents=True, exist_ok=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    with plist.open("wb") as f:
        plistlib.dump({
            "Label": LABEL,
            "ProgramArguments": [sys.executable, "-u", str(Path(core.__file__).resolve()),
                                 "--no-open", "--port", str(a.port)],
            # launchd starts with a bare PATH; include Homebrew so ffmpeg/yt-dlp are found.
            "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
            "RunAtLoad": True,
            # Restart on crash only: a clean exit (e.g. "port busy") must not respawn-loop.
            "KeepAlive": {"SuccessfulExit": False},
            "StandardOutPath": str(log),
            "StandardErrorPath": str(log),
        }, f)
    r = subprocess.run(["launchctl", "bootstrap", domain, str(plist)], capture_output=True, text=True)
    if r.returncode != 0:
        err(f"launchctl bootstrap failed: {r.stderr.strip()}")
        return 1
    print(f"anansi web now runs at login → http://localhost:{a.port}  (log: {log})")
    return 0


# ─── doctor ─────────────────────────────────────────────────────────────────

def cmd_doctor(a) -> int:
    local = core.cache_dir() / "bin" / ("yt-dlp.exe" if sys.platform.startswith("win") else "yt-dlp")
    yt = shutil.which("yt-dlp") or (str(local) if local.is_file() else None)
    checks = [
        ("python", sys.version.split()[0], True),
        ("yt-dlp", yt or "not yet downloaded (fetched automatically on first use)", True),
        ("ffmpeg", shutil.which("ffmpeg") or "MISSING — needed for full-quality video (macOS: brew install ffmpeg)",
         bool(shutil.which("ffmpeg"))),
        ("deno", shutil.which("deno") or "missing — optional; lets yt-dlp see every format (brew install deno)",
         bool(shutil.which("deno"))),
        ("clipboard", " ".join(clipboard_cmd() or ["unavailable"]), clipboard_cmd() is not None),
        ("cache", str(core.cache_dir()), True),
    ]
    for name, value, good in checks:
        print(f"{'✓' if good else '!'} {name:<9} {value}")
    return 0


# ─── main ───────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="anansi", description="YouTube links in, transcripts, video and audio out.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="fetch transcript documents (metadata header + timestamped transcript)")
    f.add_argument("links", nargs="*", help="URLs or any text containing YouTube links")
    f.add_argument("--file", help="read links from a file")
    f.add_argument("--out", help="also write '<title> [id].txt' files into this folder")
    f.add_argument("--stdout", action="store_true", help="print the full documents instead of a summary")
    f.add_argument("--json", action="store_true", help="print a JSON summary (paths, titles, status)")
    f.add_argument("--clipboard", action="store_true", help="copy all documents, merged, to the clipboard")
    f.add_argument("--refresh", action="store_true", help="ignore the 7-day cache")
    f.set_defaults(func=cmd_fetch)

    s = sub.add_parser("search", help="search YouTube")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=5, help="number of results (default 5)")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_search)

    d = sub.add_parser("download", help="download video (mp4) or audio (m4a)")
    d.add_argument("links", nargs="*")
    d.add_argument("--file", help="read links from a file")
    d.add_argument("--audio", action="store_true", help="audio only (m4a, no ffmpeg needed)")
    d.add_argument("--out", default=str(Path.home() / "Downloads"), help="folder (default ~/Downloads)")
    d.set_defaults(func=cmd_download)

    w = sub.add_parser("web", help="start the local browser UI")
    w.add_argument("action", nargs="?", choices=["install", "uninstall"], help="macOS: run at login")
    w.add_argument("--port", type=int, default=core.default_port())
    w.add_argument("--no-open", action="store_true", help="don't open the browser")
    w.set_defaults(func=cmd_web)

    sub.add_parser("doctor", help="check dependencies").set_defaults(func=cmd_doctor)
    return ap


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # titles with emoji on Windows consoles
        sys.stderr.reconfigure(encoding="utf-8")
    a = build_parser().parse_args(argv)
    try:
        return a.func(a)
    except RuntimeError as e:  # e.g. yt-dlp bootstrap failed
        err(f"error: {e}")
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
