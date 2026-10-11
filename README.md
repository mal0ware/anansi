# anansi

> In West African folklore, all the world's stories belonged to the sky god, until Anansi the spider won them and carried them back to the people.

**anansi** is a Claude Code plugin that does the same for YouTube. Share a link and Claude spins out, brings back the full transcript with its title, channel, chapters and description, and works with what was actually said. It can also search YouTube and download video or audio.

No API keys, no pip installs, no compiler. Just Python 3 and [yt-dlp](https://github.com/yt-dlp/yt-dlp), which anansi downloads by itself on first use.

## Install

In Claude Code:

```text
/plugin marketplace add mal0ware/anansi
/plugin install anansi@anansi
```

Or from a terminal:

```bash
claude plugin marketplace add mal0ware/anansi
claude plugin install anansi@anansi
```

Restart Claude Code (or run `/reload-plugins`).

**Recommended:** `brew install ffmpeg deno` (macOS). ffmpeg joins YouTube's separate video and audio streams for full-quality mp4s, and deno lets yt-dlp see every format. Transcripts and audio work without them.

## Use it

Just talk to Claude. The skill triggers whenever a YouTube link shows up or you ask about a video:

- *"Summarize this: https://youtu.be/…"*
- *"What does she say about pricing in these three talks?"* (paste links)
- *"Find me the best videos on the Rust borrow checker and tell me which one to watch."*
- *"Pull the transcripts for every link in links.txt into ./notes."*
- *"Download the audio of this one."*

Or call it directly:

| Command | What it does |
|---|---|
| `/anansi <links>` | Fetch transcripts and summarize each video with timestamps |
| `/anansi search <query>` | Search YouTube |
| `/anansi download <links> [--audio]` | Save mp4 (or m4a) to ~/Downloads |
| `/anansi web` | Open the browser UI at http://localhost:8765 |

## What a transcript looks like

```
================================================================================
TITLE:    Me at the zoo
CHANNEL:  jawed
DATE:     2005-04-24
DURATION: 0:19
URL:      https://www.youtube.com/watch?v=jNQXAC9IVRw
CHAPTERS: [0:00] Intro | [0:05] The cool thing | [0:17] End
...
================================================================================

[0:01] All right, so here we are, in front of the elephants

[0:05] the cool thing about these guys is that they have really... really really long trunks ...
```

Paragraphs break at chapters and every ~45 seconds, each prefixed with a timestamp, so Claude can cite exactly where something was said. Documents are cached in `~/.cache/anansi` for 7 days.

## Without Claude

The engine is a normal CLI too:

```bash
git clone https://github.com/mal0ware/anansi.git && cd anansi
./anansi fetch "https://youtu.be/jNQXAC9IVRw" --clipboard   # transcripts → clipboard
./anansi fetch --file links.txt --out transcripts/
./anansi search "rust borrow checker" -n 5
./anansi download "https://youtu.be/jNQXAC9IVRw" --audio
./anansi web                 # browser UI; `./anansi web install` runs it at login (macOS)
./anansi doctor              # check python / yt-dlp / ffmpeg
```

Quote URLs in zsh: the `?` in `watch?v=` is a wildcard there.

## How it works

```
skills/anansi/SKILL.md         tells Claude when and how to use anansi
skills/anansi/scripts/
  anansi.py                    the CLI (fetch / search / download / web / doctor)
  server.py                    engine: yt-dlp driver, transcript formatting, cache, web server
  index.html                   the browser UI
commands/anansi.md             the /anansi slash command
.claude-plugin/                plugin + marketplace manifests
```

All YouTube access goes through yt-dlp (kept in `~/.cache/anansi/bin`, self-updating daily; a yt-dlp on your PATH wins), so anansi inherits its resilience to YouTube changes. The web UI binds to 127.0.0.1 only and rejects foreign Host/Origin headers.

## Development

```bash
python3 -m unittest discover -s tests
claude plugin validate .
claude --plugin-dir .        # try local changes without reinstalling
```

anansi grew out of [ytmerge](https://github.com/mal0ware/ytmerge), a C++20 CLI for the same job.

## License

MIT. Downloaded content belongs to its creators; respect YouTube's terms and copyright.
