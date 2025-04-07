# Video Downloader by true_lock

A PyQt5-based UI video downloader that leverages [yt-dlp](https://github.com/yt-dlp/yt-dlp) for video extraction and downloading. The application provides an easy to use graphical user interface with usefull Costumization Settings 

## Features

- **Video Downloading:** You can Download Videos and Audio from most Websites.
- **Video Metadata Extraction:** Automatically retrieves video title, thumbnail, and file size.
- **Download Options:** Choose from multiple formats including mp4 (with/without audio), mp3, avi, and mkv.
- **Quality Settings:** Customize video quality and audio bitrate.
- **Progress Tracking:** Monitor individual download progress as well as overall progress.
- **Multi Threading:** Download as much at the same time as you want.
- **Download Control:** Pause, cancel and resume downloads.
- **Config Management:** Automatically adjusts download settings based on network speed.
- **Dark Mode UI:** A modern, dark-themed interface built with PyQt5.

## Prerequisites

- Python 3.6 or higher.
- [ffmpeg](https://ffmpeg.org/) is required for merging files. The application checks for ffmpeg and offers to install it via `winget` if it's not found.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/truelockmc/video-downloader.git
   cd video-downloader-main
   ```

2. **Install the required packages:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the main Python script:
```bash
python downloader.py
```
Upon launching, the UI will allow you to input a video URL, choose a download folder, select a file format, and configure quality settings. The downloader will then extract metadata, display a preview, and manage the download process.

## Help

If you have any questions or Encounter Problems feel free to contact me per E-mail (anonyson@proton.me) or [Discord](https://discord.com/invite/wDESTYeZy9).
You can also create an Github [Issue](https://github.com/truelockmc/video-downloader/issues/new).

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## Made by [me](https://github.com/truelockmc) : )

## Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for its powerful video downloading capabilities.
- The PyQt5 community for providing excellent tools to build the GUI.
