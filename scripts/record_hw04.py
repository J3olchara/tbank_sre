"""Record a real X11 screen with kubectl, curl and TSDB verification."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parents[1]
os.chdir(root)
for port in (18428, 18082, 19092):
    with socket.socket() as listener:
        try:
            listener.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'Port {port} is busy; stop the previous demo port-forward')
output = root / 'artifacts' / 'homework-04-demo.mp4'
output.parent.mkdir(exist_ok=True)
capture = output.with_name('homework-04-demo.partial.mp4')
display = os.environ.get('RECORDING_DISPLAY', ':98')
env = dict(os.environ, DISPLAY=display)
recorder = None
terminal = None
xvfb = None
with tempfile.TemporaryDirectory(prefix='taskboard-monitoring-recording-') as directory:
    env['RECORDING_STATE_DIR'] = directory
    try:
        xvfb = subprocess.Popen(['Xvfb', display, '-screen', '0', '1440x900x24', '-nolisten', 'tcp'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        if xvfb.poll() is not None:
            raise RuntimeError('Xvfb failed; choose an unused RECORDING_DISPLAY')
        with (Path(directory) / 'ffmpeg.log').open('w') as log:
            recorder = subprocess.Popen(['ffmpeg', '-y', '-f', 'x11grab', '-draw_mouse', '1', '-framerate', '20', '-video_size', '1440x900', '-i', display, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(capture)], stdout=log, stderr=subprocess.STDOUT)
            terminal = subprocess.Popen(['xterm', '-u8', '-geometry', '110x32+0+0', '-fa', 'DejaVu Sans Mono', '-fs', '16', '-bg', '#111827', '-fg', '#e5e7eb', '-e', 'python3', 'scripts/demo_monitoring.py'], env=env)
            if terminal.wait(timeout=360) != 0:
                raise RuntimeError('Recorded commands failed; incomplete video will not be packaged')
            recorder.send_signal(signal.SIGINT)
            recorder.wait(timeout=30)
            if recorder.returncode not in (0, 255):
                raise RuntimeError((Path(directory) / 'ffmpeg.log').read_text()[-2000:])
    finally:
        if terminal and terminal.poll() is None:
            terminal.terminate()
            terminal.wait(timeout=15)
        if recorder and recorder.poll() is None:
            recorder.send_signal(signal.SIGINT)
            recorder.wait(timeout=30)
        if xvfb and xvfb.poll() is None:
            xvfb.terminate()
            xvfb.wait(timeout=15)
seconds = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(capture)], text=True))
if not 0 < seconds <= 420:
    raise SystemExit(f'Invalid screencast duration: {seconds:.1f}s')
capture.replace(output)
print(f'Recorded {seconds:.1f}s: {output}')
