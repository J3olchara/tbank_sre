"""Record a real X11 desktop: xterm with kubectl, then Chromium with UI CRUD.

Prerequisites: Xvfb, xterm, ffmpeg/ffprobe, xdotool, Node, Playwright Chromium.
Cluster/image must exist; namespace must be absent. No resources are deleted here.
"""
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parents[1]
os.chdir(root)
profile = os.environ.get("PROFILE", "tbank-sre-hw02")
result = subprocess.run(["kubectl", "--context", profile, "get", "namespace", "taskboard-lab", "--ignore-not-found", "-o", "name"], check=True, capture_output=True, text=True)
if result.stdout.strip():
    raise SystemExit("Use a fresh taskboard-lab namespace for the recording; existing data is not removed automatically")
with socket.socket() as listener:
    try:
        listener.bind(("127.0.0.1", 18080))
    except OSError:
        raise SystemExit("Port 18080 is busy; stop the previous port-forward before recording")
output = root / "artifacts" / "homework-02-demo.mp4"
output.parent.mkdir(exist_ok=True)
capture = output.with_name("homework-02-demo.partial.mp4")
display = os.environ.get("RECORDING_DISPLAY", ":97")
env = dict(os.environ, DISPLAY=display)
with tempfile.TemporaryDirectory(prefix="taskboard-recording-") as directory:
    state = Path(directory)
    env["RECORDING_STATE_DIR"] = directory
    processes = []
    recorder = None
    try:
        xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", "1440x900x24", "-nolisten", "tcp"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(xvfb)
        time.sleep(2)
        if xvfb.poll() is not None:
            raise RuntimeError("Xvfb failed; choose an unused RECORDING_DISPLAY")
        with (state / "ffmpeg.log").open("w") as log:
            recorder = subprocess.Popen(["ffmpeg", "-y", "-f", "x11grab", "-draw_mouse", "1", "-framerate", "20", "-video_size", "1440x900", "-i", display, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(capture)], stdout=log, stderr=subprocess.STDOUT)
            terminal = subprocess.Popen(["xterm", "-u8", "-geometry", "110x32+0+0", "-fa", "DejaVu Sans Mono", "-fs", "16", "-bg", "#111827", "-fg", "#e5e7eb", "-e", "python3", "scripts/demo_terminal.py"], env=env)
            processes.append(terminal)
            deadline = time.monotonic() + 300
            while not (state / "terminal.done").exists():
                if terminal.poll() is not None:
                    raise RuntimeError("Terminal demonstration failed")
                if time.monotonic() > deadline:
                    raise RuntimeError("Terminal demonstration exceeded five minutes")
                time.sleep(1)
            subprocess.run(["node", "scripts/demo_ui.cjs"], env=env, check=True, timeout=100)
            recorder.send_signal(signal.SIGINT)
            recorder.wait(timeout=30)
            if recorder.returncode not in (0, 255):
                raise RuntimeError((state / "ffmpeg.log").read_text()[-2000:])
            screenshot = state / "ui-complete.png"
            if screenshot.exists():
                (output.parent / "homework-02-ui.png").write_bytes(screenshot.read_bytes())
    finally:
        if recorder and recorder.poll() is None:
            recorder.send_signal(signal.SIGINT)
            recorder.wait(timeout=30)
        pidfile = state / "forward.pid"
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGTERM)
            except ProcessLookupError:
                pass
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
seconds = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(capture)], text=True))
if not 0 < seconds <= 420:
    raise SystemExit(f"Invalid screencast duration: {seconds:.1f}s")
capture.replace(output)
print(f"Recorded {seconds:.1f}s: {output}")
