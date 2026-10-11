---
name: anansi
description: Fetch YouTube transcripts, metadata, video and audio. Use whenever the user shares a YouTube link (youtube.com, youtu.be, shorts, live) or asks to summarize, quote, analyze, compare, take notes on, or answer questions about a YouTube video; to find videos on a topic; or to download a video or its audio. Also use when pasted text contains YouTube links the user wants processed.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/anansi.py:*), Read
---

# Anansi — YouTube transcripts, search and downloads

Anansi is a standard-library Python CLI over yt-dlp. You never need to watch a video: fetch its transcript document and read it.

Run it as:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/anansi.py" <command> ...
```

**Always quote each URL** (`"https://www.youtube.com/watch?v=..."`): unquoted, the `?` is a shell wildcard and zsh aborts with "no matches found". For many links or pasted text, write them to a file and use `--file`, or pipe the text in on stdin.

The first run downloads yt-dlp into `~/.cache/anansi/bin` (a few seconds). Transcripts are cached for 7 days, so refetching is free.

## Commands

| Need | Command |
|---|---|
| Transcripts for links | `fetch <urls or any text containing them>` |
| Transcripts from a file of links | `fetch --file links.txt` |
| Save them as named files for the user | `fetch <urls> --out <folder>` |
| Put everything on the user's clipboard | `fetch <urls> --clipboard` |
| Find videos on a topic | `search "<query>" -n 5` |
| Download video (mp4) | `download <urls> [--out <folder>]` (default `~/Downloads`) |
| Download audio only (m4a) | `download <urls> --audio` |
| Browser UI for the user | `web` (http://localhost:8765) |
| Something failing / missing tools | `doctor` |

## How to work with transcripts

1. Run `fetch` with the links. It prints one block per video: title, channel, duration, and the **path** of its transcript document (or `✗` with a reason).
2. **Read the document at that path** with the Read tool. Don't use `--stdout` for long videos; a one-hour talk is ~10k words, and reading the file lets you page through it.
3. Each document starts with a header (TITLE, CHANNEL, DATE, DURATION, VIEWS, URL, TAGS, CHAPTERS, DESCRIPTION), then the transcript in paragraphs prefixed with `[m:ss]` timestamps. Cite timestamps when you quote or summarize, and link them as `https://www.youtube.com/watch?v=<id>&t=<seconds>s` when useful.
4. A document ending in `(no transcript available)` has metadata only: tell the user the video has no English captions rather than guessing at its content.

For several videos, fetch them all in one call; they download in parallel.

## Errors

- `rate-limited by YouTube (429)` or `sign-in check (bot detection)`: YouTube is throttling this network. Tell the user; suggest waiting or another network. Don't retry in a loop.
- `video unavailable`: private, removed, members-only or region-locked.
- `video needs ffmpeg`: suggest `brew install ffmpeg` (macOS) / their package manager; audio downloads work without it.
- Anything else: run `doctor` and report what it shows.

## Boundaries

Download video or audio only when the user asks for the files. For "what does this video say", a transcript fetch is enough. Respect that downloaded content belongs to its creators.
