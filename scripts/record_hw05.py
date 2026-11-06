"""Record real xterm + headed Chromium from X11, without time compression."""
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen

root = Path(__file__).resolve().parents[1]
os.chdir(root)
env = dict(os.environ)
env['VM_URL'] = 'http://127.0.0.1:18429'
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 18429))
output = root / 'artifacts/homework-05-demo.mp4'
partial = output.with_name('homework-05-demo.partial.mp4')
processes = []
recorder = None
try:
    subprocess.run(['python3', 'scripts/slo_queries.py'], check=True)
    subprocess.run(['make', 'slo-mode', 'MODE=healthy'], check=True)
    subprocess.run(['make', 'slo-load-start'], check=True)
    forward = subprocess.Popen(['kubectl', '--context', env.get('PROFILE', 'tbank-sre-hw02'), '-n', 'monitoring', 'port-forward', 'svc/vm-single', '18429:8428', '--address=127.0.0.1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    processes.append(forward)
    for _ in range(30):
        try:
            with urlopen(env['VM_URL'] + '/health', timeout=2):
                break
        except OSError:
            time.sleep(1)
    subprocess.run(['python3', 'scripts/check_slo.py', '--phase', 'healthy', '--timeout', '150'], env=env, check=True)
    with tempfile.TemporaryDirectory(prefix='hw05-recording-') as directory:
        env['RECORDING_STATE_DIR'] = directory
        env['DISPLAY'] = env.get('RECORDING_DISPLAY', ':96')
        xvfb = subprocess.Popen(['Xvfb', env['DISPLAY'], '-screen', '0', '1920x1200x24', '-nolisten', 'tcp'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(xvfb)
        time.sleep(2)
        if xvfb.poll() is not None:
            raise RuntimeError('Xvfb failed; select an unused RECORDING_DISPLAY')
        with (Path(directory)/'ffmpeg.log').open('w') as log:
            recorder = subprocess.Popen(['ffmpeg','-y','-f','x11grab','-draw_mouse','1','-framerate','15','-video_size','1920x1200','-i',env['DISPLAY'],'-c:v','libx264','-preset','veryfast','-crf','24','-pix_fmt','yuv420p','-movflags','+faststart',str(partial)],stdout=log,stderr=subprocess.STDOUT)
            terminal = subprocess.Popen(['xterm','-u8','-title','HW05 Control','-geometry','145x42+0+0','-fa','DejaVu Sans Mono','-fs','18','-bg','#111827','-fg','#e5e7eb','-e','python3','scripts/demo_slo_terminal.py'],env=env)
            processes.append(terminal)
            time.sleep(1)
            subprocess.run(['node','scripts/demo_slo.cjs'],env=env,check=True,timeout=410)
            recorder.send_signal(signal.SIGINT)
            recorder.wait(timeout=30)
            if recorder.returncode not in (0,255):
                raise RuntimeError((Path(directory)/'ffmpeg.log').read_text()[-2000:])
    seconds = float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(partial)],text=True))
    if not 0 < seconds <= 420:
        raise RuntimeError(f'Recording must be <=7 minutes, got {seconds:.1f}s')
    partial.replace(output)
    print(f'Recorded real SLI/SLO/SLA demonstration: {seconds:.1f}s, {output}')
finally:
    if recorder and recorder.poll() is None:
        recorder.send_signal(signal.SIGINT)
        recorder.wait(timeout=30)
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
    # Restore app behavior before stopping traffic so generated tasks can be cleaned.
    subprocess.run(['make','slo-mode','MODE=healthy'],check=False)
    subprocess.run(['make','slo-load-stop'],check=False)
