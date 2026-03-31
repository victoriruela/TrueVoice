import os
import sys
import subprocess
import time
import atexit
import webbrowser
import signal
from pathlib import Path
import requests

def setup_paths():
    """Configura paths para standalone."""
    if getattr(sys, 'frozen', False):
        base_path = Path(sys.executable).parent
        # Para onefile, usar _MEIPASS para data
        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
        os.chdir(base_path)
        project_root = base_path
    else:
        project_root = Path(__file__).parent.resolve()
    return project_root

def setup_ffmpeg(project_root):
    """Configura FFmpeg para standalone."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        ffmpeg_dir = Path(sys._MEIPASS) / 'bin'
        ffmpeg_exe = ffmpeg_dir / 'ffmpeg.exe'
        if ffmpeg_exe.exists():
            os.environ['PATH'] = str(ffmpeg_dir) + os.pathsep + os.environ.get('PATH', '')
            print("[Launcher] FFmpeg bundled configurado.")
            return True
    # Fallback: asumir instalado
    return True

def start_api(project_root):
    api_cmd = [
        sys.executable,
        "-m", "uvicorn",
        "api_server:app",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--workers", "1",
        "--log-level", "error"
    ]
    api_proc = subprocess.Popen(api_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(project_root))
    return api_proc

def wait_api_ready():
    for _ in range(30):
        try:
            r = requests.get("http://localhost:8000/", timeout=1)
            if r.status_code == 200:
                return True
        except:
            time.sleep(1)
    return False

def main():
    project_root = setup_paths()
    print(f"[Launcher] Project root: {project_root}")

    if not setup_ffmpeg(project_root):
        print("FFmpeg no disponible. Instálalo manualmente.")
        return

    api_proc = start_api(project_root)
    print("[Launcher] API iniciada, esperando...")

    if not wait_api_ready():
        print("[Launcher] API no respondió. Abortando.")
        api_proc.kill()
        return

    print("[Launcher] API lista!")

    st_cmd = [
        sys.executable,
        "-m", "streamlit",
        "run",
        "frontend.py",
        "--server.port", "8501",
        "--server.headless", "true",
        "--server.address", "127.0.0.1",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false"
    ]
    st_proc = subprocess.Popen(st_cmd, cwd=str(project_root))

    webbrowser.open("http://localhost:8501")

    def cleanup():
        print("[Launcher] Cerrando...")
        try:
            api_proc.terminate()
            st_proc.terminate()
            api_proc.wait(timeout=5)
            st_proc.wait(timeout=5)
        except:
            api_proc.kill()
            st_proc.kill()

    atexit.register(cleanup)

    # Windows SIGINT
    def signal_handler(sig, frame):
        cleanup()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        st_proc.wait()
    except KeyboardInterrupt:
        cleanup()

if __name__ == "__main__":
    main()