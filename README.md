# YT Tool

A Python desktop app for downloading a YouTube video with its audio.

## Start

Double-click **Start YT Tool.cmd**. Paste the full video URL and click **Load video**.
Choose an available resolution (or **Best available**), select a destination using
**Browse**, then click **Download video**. **Open folder** opens the destination.

The selected resolution is a maximum: the downloader selects the best video up to
that height and combines it with audio. Merged videos use MKV to preserve quality
without re-encoding; already combined streams may retain MP4 or WebM. Progress is
shown per stream, so it can restart when the audio download begins. The app remains
responsive during downloads and merging. Cancel stops the download and FFmpeg;
partial files remain so a later attempt can resume. Existing completed files are
not overwritten. The destination is remembered next time you open the app.

## Setup / update

Requires Windows, Python 3.10+ with Tk and pip, and Node.js 22+ or Deno on PATH.
Run **Setup.cmd** to create the local `.venv` and install/update the dependencies.
FFmpeg is supplied by the `imageio-ffmpeg` package; no system installation is needed.
The JavaScript challenge solver is included through `yt-dlp[default]`.

If YouTube changes and downloads stop working, run **Setup.cmd** again. Some
private, age restricted, members only, region restricted, or otherwise unavailable
videos cannot be downloaded. Live streams are not supported. Playlists are not
downloaded; a video URL containing a playlist parameter downloads only that video.
Download only videos you own or have permission to save.

## Development

`app.py` is the Tkinter interface. `downloader.py` runs in a separate process and
sends JSON events to the interface. All Tk updates happen on the main thread.

Run checks with `.venv\Scripts\python.exe -m unittest discover -s tests -v`.

References: [yt-dlp](https://github.com/yt-dlp/yt-dlp),
[YouTube JavaScript support](https://github.com/yt-dlp/yt-dlp/wiki/EJS),
[imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg).
