# Command-line Interface (CLI) — Video Downloader

This document describes the command-line interface (CLI) of the Video Downloader project. The CLI is a lightweight, interactive (or scriptable) frontend that re-uses the same download logic and network-tuned options as the GUI download worker, so downloads started from the CLI behave the same way as those from the GUI.

> Launch the CLI through the repository entrypoint (main.py). The CLI is activated when you run `main.py` with `--cli` (or `-c`).

## Quick start

Interactive mode:
```bash
python main.py --cli
# or short:
python main.py -c
```

Non-interactive (single-command) example:
```bash
python main.py --cli "https://www.youtube.com/watch?v=... " -f "mp4 (with Audio)" -r 720 -b 192 -n "my_video_name" -d "/path/to/download" -a "--no-playlist -o '%(title)s.%(ext)s'"
```

## Summary of behavior

- The CLI uses the same download options builder and logger as the GUI's `DownloadWorker`, so:
  - `concurrent_fragment_downloads` and `http_chunk_size` are derived from the project's config (download_config.ini) and tuned by a small network speed check.
  - The CLI uses the same merge/postprocessor options (e.g. MP3 extraction) and the same progress logging.
- If `--folder`/`-d` is not provided, the download folder from the config file (created by the app if missing) is used — the CLI will not interactively ask for a folder.
- If `--filename`/`-n` is not provided, the CLI will NOT ask for a filename. The downloader will use the title-based `'%(title)s.%(ext)s'` template (same as the GUI).
- The CLI supports interactive selection for format, resolution and bitrate when those options are not provided on the command line.

## Command-line options

- --cli, -c
  - Start CLI mode. (main.py will hand control to the CLI implementation when this flag is present.)
- url (positional)
  - Optional: video URL. If not provided, the CLI will prompt `Video URL:` interactively.
- --format, -f
  - Output format. Allowed values (examples): `mp4 (with Audio)`, `mp4 (without Audio)`, `mp3`, `avi`, `mkv`.
  - If not provided, the CLI shows a numbered list to choose from.
- --resolution, -r
  - Video max height (e.g. `best`, `1080`, `720`, `480`, `360`).
  - Only meaningful for video formats. If not provided and a video format is chosen, the CLI asks for it interactively.
- --bitrate, -b
  - Audio bitrate in kbps (e.g. `320`, `256`, `192`, `128`).
  - Asked interactively for formats that contain audio (MP3, `mp4 (with Audio)`, `avi`, `mkv`) unless provided.
- --filename, -n
  - Optional forced filename (without extension). If provided it will be uniquified in the target folder (appends ` (1)`, ` (2)`, ... when needed).
  - If not provided, the CLI does NOT ask for a filename and the downloader will use the title-based template.
- --folder, -d
  - Download folder. If not provided, the folder from the config file (`download_config.ini`) is used. The CLI will not ask for it.
- --ytdlp-args, -a
  - Raw passthrough arguments for yt-dlp. Accepts either multiple arguments or a single quoted string (the CLI tries to shlex-split single strings).
  - Minimal parsing: `-o` / `--output` is recognized and applied to the `outtmpl` option. Other args are available to advanced users but not exhaustively parsed.

## Interactive prompts

When the CLI needs to ask the user for some options, it presents a numbered menu. Example:

```
Select output format:
  1) mp4 (with Audio)
  2) mp4 (without Audio)
  3) mp3
  4) avi
  5) mkv
  Enter = skip (None)
Choice (number):
```

- Press Enter to skip and leave the value as `None` (the downloader will fall back to defaults or metadata-based choices).
- The CLI never prompts for `folder` or `filename` if those were not provided; it uses config / title-based template instead.

## Behavior details

- Config integration
  - The CLI calls `load_or_create_config()` from the project utils. If no config exists, a configuration file is created with tuned defaults depending on a quick network-speed test (this sets `concurrent_fragment_downloads` and `http_chunk_size`).
  - The default download folder used when `--folder` is not provided is read from this config
- Progress and logging
  - The CLI uses the same YTDLP logger used by the GUI worker. Progress lines are printed using carriage returns so the terminal output is compact (no long list of lines for progress).
- Retry behavior
  - If extraction or downloading fails with `403`/`forbidden`, the CLI retries once using special Videasy headers (same as GUI).
- Partial downloads
  - If a download fails or is cancelled, partially downloaded files (e.g. `.part`) are cleaned up where applicable by the downloader logic.

## Examples

Interactive flow (prompts):
```bash
python main.py --cli
# Video URL: https://www.youtube.com/watch?v=...
# choose format/resolution/bitrate when prompted
```

Fully non-interactive:
```bash
python main.py --cli "https://www.youtube.com/watch?v=..." \
  -f "mp4 (with Audio)" -r 720 -b 192 -n "my_video" -d "/tmp/downloads"
```

Using raw yt-dlp options:
```bash
python main.py --cli "https://..." -a "--no-playlist -o '%(title)s.%(ext)s'"
# or
python main.py --cli "https://..." -a --no-playlist -a -o '%(title)s.%(ext)s'
```

Note: passing `-o`/`--output` via `--ytdlp-args` will set the downloader's `outtmpl`. If you also pass `--filename`, `--filename` will override the template and be uniquified.

## Requirements

- Python dependencies: see `requirements.txt`. For CLI downloads you need:
  - `yt-dlp` (used to fetch and download formats)
  - `ffmpeg` is required for format conversion / audio extraction if you use formats that require ffmpeg (the CLI will behave similarly to GUI regarding ffmpeg).
- The CLI does not load the PyQt GUI components unless the GUI mode is started.

## Troubleshooting

- If progress is printed as many lines instead of updating in-place, make sure your terminal supports carriage returns and that `yt-dlp` output is operating normally. The CLI uses the same logger implementation as the GUI worker to print progress compactly.
- If you see many "only audio" formats or the chosen resolution yields no video, the downloader falls back to combined formats or `best` as needed. You can inspect available formats by running a quick info extraction with yt-dlp or consult the debug output printed by the tool.
- For sites that block programmatic access, the downloader will retry once with special headers (Videasy). If extraction still fails, try adding appropriate `--ytdlp-args` like `--no-check-certificate` or site-specific headers; use advanced yt-dlp flags as needed.

## Contributing / Extending

- The CLI uses the same options-builder as the GUI worker — changing the format/merge/postprocessor mapping in the worker will also change CLI behavior.
- If you want more advanced passthrough of yt-dlp flags (proxies, cookies, headers), extend the CLI's `--ytdlp-args` parsing or pass them directly through `--ytdlp-args` (note: the current implementation only does limited parsing for `-o` / `--output`).

---

If you want, I can:
- add this file to the repository at `docs/CLI.md` and create a pull request,
- or trim/expand sections, add screenshots or example terminal logs. Which would you prefer?
