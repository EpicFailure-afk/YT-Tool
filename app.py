"""YT Tool — a small Windows desktop YouTube downloader."""
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from downloader import validate_url

APP_DIR = Path(__file__).resolve().parent
SETTINGS = APP_DIR / 'settings.json'


def human_bytes(value):
    value = float(value or 0)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            return f'{value:.1f} {unit}'
        value /= 1024


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('YT Tool · YouTube Downloader')
        self.geometry('760x580')
        self.minsize(660, 550)
        self.configure(bg='#f3f5fa')
        self.process = None
        self.events = queue.Queue()
        self.loaded_url = None
        self.cancelled = False
        self.terminal_event = False
        self.closing = False
        self.heights = {}
        self.url = tk.StringVar()
        self.destination = tk.StringVar(value=str(Path.home() / 'Downloads'))
        try:
            saved = json.loads(SETTINGS.read_text(encoding='utf-8'))
            self.destination.set(saved.get('destination', self.destination.get()))
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        self.quality = tk.StringVar(value='Load a video first')
        self.status = tk.StringVar(value='Paste a video link to get started.')
        self.video_title = tk.StringVar(value='No video loaded')
        self.details = tk.StringVar(value='')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background='#f3f5fa')
        style.configure('TButton', padding=(14, 9))
        style.configure('Accent.TButton', background='#305cde', foreground='white')
        style.configure('TEntry', padding=9, fieldbackground='white')
        style.configure('TCombobox', padding=8)
        style.configure('Title.TLabel', font=('Segoe UI Semibold', 24), foreground='#172444')
        style.configure('Muted.TLabel', foreground='#596579')
        panel = ttk.Frame(self, padding=28)
        panel.pack(fill='both', expand=True)
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text='YT Tool', style='Title.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(panel, text='Your video. Your quality. Your folder.', style='Muted.TLabel').grid(row=1, column=0, sticky='w', pady=(2, 22))
        ttk.Label(panel, text='YouTube video URL').grid(row=2, column=0, sticky='w')
        line = ttk.Frame(panel)
        line.grid(row=3, column=0, sticky='ew', pady=(6, 14))
        line.columnconfigure(0, weight=1)
        self.url_entry = ttk.Entry(line, textvariable=self.url)
        self.url_entry.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        self.load_button = ttk.Button(line, text='Load video', command=self.load)
        self.load_button.grid(row=0, column=1)
        ttk.Label(panel, textvariable=self.video_title, wraplength=680, font=('Segoe UI Semibold', 11)).grid(row=4, column=0, sticky='w', pady=(0, 14))
        ttk.Label(panel, text='Video quality').grid(row=5, column=0, sticky='w')
        self.quality_box = ttk.Combobox(panel, textvariable=self.quality, state='disabled')
        self.quality_box.grid(row=6, column=0, sticky='ew', pady=(6, 14))
        ttk.Label(panel, text='Save to').grid(row=7, column=0, sticky='w')
        dest = ttk.Frame(panel)
        dest.grid(row=8, column=0, sticky='ew', pady=(6, 16))
        dest.columnconfigure(0, weight=1)
        self.dest_entry = ttk.Entry(dest, textvariable=self.destination)
        self.dest_entry.grid(row=0, column=0, sticky='ew', padx=(0, 10))
        self.browse_button = ttk.Button(dest, text='Browse…', command=self.browse)
        self.browse_button.grid(row=0, column=1)
        actions = ttk.Frame(panel)
        actions.grid(row=9, column=0, sticky='ew')
        self.download_button = ttk.Button(actions, text='Download video', style='Accent.TButton', command=self.download, state='disabled')
        self.download_button.pack(side='left')
        self.cancel_button = ttk.Button(actions, text='Cancel', command=self.cancel, state='disabled')
        self.cancel_button.pack(side='left', padx=10)
        ttk.Button(actions, text='Open folder', command=self.open_folder).pack(side='right')
        self.progress = ttk.Progressbar(panel, mode='determinate', maximum=100)
        self.progress.grid(row=10, column=0, sticky='ew', pady=(22, 8))
        ttk.Label(panel, textvariable=self.status, wraplength=680).grid(row=11, column=0, sticky='w')
        ttk.Label(panel, textvariable=self.details, style='Muted.TLabel').grid(row=12, column=0, sticky='w', pady=(4, 0))
        self.url.trace_add('write', self.url_changed)
        self.bind('<Return>', lambda _: self.load() if self.process is None else None)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.poll)
        self.url_entry.focus_set()

    def url_changed(self, *_):
        if self.url.get().strip() != self.loaded_url:
            self.loaded_url = None
            self.quality_box.configure(state='disabled')
            self.download_button.configure(state='disabled')
            self.video_title.set('No video loaded')

    def browse(self):
        folder = filedialog.askdirectory(initialdir=self.destination.get(), title='Choose download folder')
        if folder:
            self.destination.set(folder)

    def open_folder(self):
        folder = Path(self.destination.get()).expanduser()
        if folder.is_dir():
            os.startfile(str(folder))
        else:
            messagebox.showinfo('Folder', 'Choose an existing folder, or download a video to create it.')

    def set_busy(self, busy):
        state = 'disabled' if busy else 'normal'
        for widget in (self.url_entry, self.dest_entry, self.browse_button, self.load_button):
            widget.configure(state=state)
        self.quality_box.configure(state='readonly' if not busy and self.loaded_url else 'disabled')
        self.download_button.configure(state='normal' if not busy and self.loaded_url else 'disabled')
        self.cancel_button.configure(state='normal' if busy else 'disabled')

    def start(self, request):
        if self.process is not None:
            return
        self.cancelled = False
        self.terminal_event = False
        self.details.set('')
        self.progress['value'] = 0
        try:
            self.process = subprocess.Popen(
                [sys.executable, '-u', str(APP_DIR / 'downloader.py')],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                encoding='utf-8', errors='replace',
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            self.process.stdin.write(json.dumps(request) + '\n')
            self.process.stdin.close()
        except OSError as exc:
            self.process = None
            messagebox.showerror('Could not start', str(exc))
            return
        process = self.process
        self.set_busy(True)
        self.progress.configure(mode='indeterminate')
        self.progress.start(12)

        def read():
            # Drain stderr concurrently so a dependency cannot block the worker.
            errors = []
            def drain_errors():
                for line in process.stderr:
                    errors.append(line)
                    if len(errors) > 30:
                        errors.pop(0)
            stderr_reader = threading.Thread(target=drain_errors, daemon=True)
            stderr_reader.start()
            for line in process.stdout:
                try:
                    self.events.put(json.loads(line))
                except ValueError:
                    pass
            code = process.wait()
            stderr_reader.join(timeout=2)
            self.events.put({'event': 'exit', 'code': code, 'error': ''.join(errors)[-1800:]})
        threading.Thread(target=read, daemon=True).start()

    def load(self):
        try:
            url = validate_url(self.url.get())
        except ValueError as exc:
            messagebox.showerror('Video URL', str(exc))
            return
        self.loaded_url = None
        self.video_title.set('Loading video…')
        self.status.set('Finding available qualities…')
        self.start({'action': 'inspect', 'url': url})

    def download(self):
        if not self.loaded_url or self.url.get().strip() != self.loaded_url:
            self.load()
            return
        if not self.destination.get().strip():
            messagebox.showerror('Destination', 'Choose a folder to save the video.')
            return
        try:
            SETTINGS.write_text(json.dumps({'destination': self.destination.get()}), encoding='utf-8')
        except OSError:
            pass
        self.status.set('Starting download…')
        self.start({'action': 'download', 'url': self.loaded_url,
                    'height': self.heights[self.quality.get()],
                    'destination': self.destination.get()})

    def cancel(self):
        if self.process is None or self.process.poll() is not None:
            return
        self.cancelled = True
        self.cancel_button.configure(state='disabled')
        self.status.set('Cancelling…')
        process = self.process
        def stop():
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                process.terminate()
        threading.Thread(target=stop, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                kind = event['event']
                if kind == 'exit':
                    self.progress.stop()
                    self.progress.configure(mode='determinate')
                    self.process = None
                    if self.closing:
                        self.destroy()
                        return
                    self.set_busy(False)
                    if self.cancelled:
                        self.status.set('Cancelled. Partial downloads can resume when you try again.')
                    elif not self.terminal_event:
                        self.status.set('The download process stopped unexpectedly.')
                        messagebox.showerror('Worker stopped', event.get('error') or 'Run Setup.cmd to check the dependencies.')
                    continue
                if self.cancelled:
                    continue
                if kind in ('info', 'complete', 'error'):
                    self.terminal_event = True
                    self.progress.stop()
                    self.progress.configure(mode='determinate')
                if kind == 'info':
                    self.loaded_url = self.url.get().strip()
                    self.video_title.set(event['title'])
                    self.heights = {'Best available': None}
                    self.heights.update({f'{h}p': h for h in event['heights']})
                    self.quality_box.configure(values=list(self.heights))
                    self.quality.set('Best available')
                    self.status.set('Ready. Choose quality and destination, then download.')
                elif kind == 'progress':
                    percent = event.get('percent')
                    if percent is not None:
                        self.progress.stop()
                        self.progress.configure(mode='determinate')
                        self.progress['value'] = percent
                    self.status.set(f'Downloading stream… {percent:.1f}%' if percent is not None else 'Downloading stream…')
                    parts = [human_bytes(event.get('downloaded'))]
                    if event.get('total'):
                        parts[0] += ' / ' + human_bytes(event['total'])
                    if event.get('speed'):
                        parts.append(human_bytes(event['speed']) + '/s')
                    if event.get('eta') is not None:
                        parts.append(f"{int(event['eta'])}s remaining")
                    self.details.set('   ·   '.join(parts))
                elif kind == 'status':
                    self.status.set(event['message'])
                    self.progress.configure(mode='indeterminate')
                    self.progress.start(12)
                elif kind == 'warning':
                    self.details.set(event['message'][:180])
                elif kind == 'complete':
                    self.progress['value'] = 100
                    self.status.set('Download complete. Your video is ready.')
                    self.details.set(Path(event['filename']).name)
                elif kind == 'error':
                    self.status.set('Could not complete this request. You can try again.')
                    messagebox.showerror('YT Tool', event['message'] + '\n\nIf YouTube changed recently, run Setup.cmd to update the downloader.')
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def close(self):
        if self.process is not None and self.process.poll() is None:
            if not messagebox.askyesno('Close YT Tool', 'Cancel the current operation and close?'):
                return
            self.closing = True
            self.cancel()
            return
        self.destroy()


if __name__ == '__main__':
    App().mainloop()
