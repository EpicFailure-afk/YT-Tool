"""Download engine. Its JSON event stream keeps network work outside the GUI."""
import json
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse


def validate_url(value):
    value = value.strip()
    parsed = urlparse(value)
    host = (parsed.hostname or '').lower()
    if parsed.scheme not in ('https', 'http') or not (
        host in ('youtu.be', 'youtube.com', 'youtube-nocookie.com')
        or host.endswith('.youtube.com')
        or host.endswith('.youtube-nocookie.com')
    ):
        raise ValueError('Please enter a full YouTube video URL (https://...).')
    if not parsed.path or parsed.path == '/' or parsed.path.startswith('/playlist'):
        raise ValueError('Please enter a video URL, rather than a channel or playlist.')
    return value


def available_heights(info):
    return sorted({int(f['height']) for f in info.get('formats', [])
                   if f.get('height') and f.get('vcodec') not in (None, 'none')
                   and not f.get('has_drm')}, reverse=True)


def format_selector(height=None):
    # Enforce the chosen height even in the fallback to combined video/audio.
    limit = f'[height<={int(height)}]' if height else ''
    return f'bv*{limit}+ba/b{limit}'


def emit(kind, **data):
    print(json.dumps({'event': kind, **data}), flush=True)


class Logger:
    def debug(self, message):
        pass

    def warning(self, message):
        emit('warning', message=message)

    def error(self, message):
        pass  # The worker reports the final exception once.


def run(request):
    from yt_dlp import YoutubeDL
    import imageio_ffmpeg

    url = validate_url(request['url'])
    runtimes = {}
    for name in ('deno', 'node'):
        if executable := shutil.which(name):
            runtimes[name] = {'path': executable}
    if not runtimes:
        raise RuntimeError('Install Node.js (version 22 or newer) or Deno, then restart the app.')
    options = {
        'quiet': True, 'no_warnings': False, 'logger': Logger(),
        'noplaylist': True, 'socket_timeout': 25, 'retries': 3,
        'js_runtimes': runtimes,
        'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
    }
    if request['action'] == 'inspect':
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        if info.get('is_live'):
            raise ValueError('This video is currently live. Try again after the stream ends.')
        heights = available_heights(info)
        if not heights:
            raise ValueError('No downloadable video qualities were found for this URL.')
        emit('info', title=info.get('title', 'YouTube video'),
             duration=info.get('duration'), heights=heights)
        return

    folder = Path(request['destination']).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)

    def progress(data):
        if data['status'] == 'downloading':
            total = data.get('total_bytes') or data.get('total_bytes_estimate')
            done = data.get('downloaded_bytes', 0)
            emit('progress', percent=min(100, done * 100 / total) if total else None,
                 downloaded=done, total=total, speed=data.get('speed'), eta=data.get('eta'))
        elif data['status'] == 'finished':
            emit('status', message='Stream downloaded. Preparing video and audio…')

    def postprocess(data):
        emit('status', message='Merging video and audio… Please wait.')

    options.update({
        'format': format_selector(request.get('height')),
        'paths': {'home': str(folder)},
        'outtmpl': {'default': '%(title).160B [%(id)s].%(ext)s'},
        'windowsfilenames': True, 'continuedl': True, 'overwrites': False,
        'merge_output_format': 'mkv',
        'progress_hooks': [progress], 'postprocessor_hooks': [postprocess],
    })
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = info.get('filepath') or info.get('_filename') or ydl.prepare_filename(info)
        # yt-dlp may change the extension when merging streams.
        merged = Path(filename).with_suffix('.mkv')
        if merged.exists():
            filename = str(merged)
    emit('complete', filename=filename)


if __name__ == '__main__':
    try:
        run(json.loads(sys.stdin.readline()))
    except Exception as exc:
        emit('error', message=str(exc))
        sys.exit(1)
