import os
import sys
import subprocess
import urllib.request
import zipfile
from pathlib import Path

def get_data_file(filename):
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / filename
    return Path(filename)

def download(url, path):
    print(f"Descargando {url}...")
    urllib.request.urlretrieve(url, path)
    print(f"Descargado a {path}")

def extract_zip(zip_path, extract_to):
    print(f"Extrayendo {zip_path} a {extract_to}...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_to)

def create_shortcut(target, args='', start_in='', desc='', desktop_shortcut='Desktop\\TrueVoice.lnk'):
    ps_script = f'''
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut_path = $desktop \\ "{desktop_shortcut}"
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcut_path)
$Shortcut.TargetPath = "{target}"
$Shortcut.Arguments = "{args}"
$Shortcut.WorkingDirectory = "{start_in}"
$Shortcut.Description = "{desc}"
$Shortcut.Save()
Write-Output "Shortcut creado en $shortcut_path"
'''
    result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        print(f"Error creando shortcut: {result.stderr}")

def main():
    home = Path.home()
    install_dir = home / "TrueVoice"
    install_dir.mkdir(exist_ok=True)
    print(f"Instalando TrueVoice en: {install_dir}")

    py_dir = install_dir / "python"
    app_dir = install_dir / "app"
    ffmpeg_dir = install_dir / "ffmpeg"

    # 1. Instalar Python embed
    py_exe = py_dir / "python.exe"
    if not py_exe.exists():
        py_zip = install_dir / "python.zip"
        url_py = "https://www.python.org/ftp/python/3.12.3/python-3.12.3-embed-amd64.zip"
        download(url_py, py_zip)
        extract_zip(py_zip, install_dir)
        py_zip.unlink()
        print("Actualizando pip...")
        subprocess.run([str(py_exe), "-m", "pip", "install", "--upgrade", "pip"], check=True, capture_output=True)
    else:
        print("Python ya instalado.")

    # 2. Extraer proyecto
    project_zip = get_data_file("project.zip")
    if not app_dir.exists():
        extract_zip(project_zip, install_dir)
    else:
        print("Proyecto ya extraído.")

    # 3. Instalar dependencias
    reqs = app_dir / "requirements.txt"
    print("Instalando dependencias (esto puede tardar... torch/transformers son grandes)")
    subprocess.run([str(py_exe), "-m", "pip", "install", "-r", str(reqs)], cwd=str(app_dir), check=True)
    print("Dependencias instaladas.")

    # 4. FFmpeg portable
    ffmpeg_bin = ffmpeg_dir / "bin" / "ffmpeg.exe"
    if not ffmpeg_bin.exists():
        ffmpeg_zip = install_dir / "ffmpeg.zip"
        url_ffmpeg = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        download(url_ffmpeg, ffmpeg_zip)
        extract_zip(ffmpeg_zip, install_dir)
        ffmpeg_zip.unlink()
        print("FFmpeg instalado.")
    else:
        print("FFmpeg ya instalado.")

    # 5. Crear run.bat
    run_bat = install_dir / "TrueVoice.bat"
    bat_content = r'''@echo off
rem TrueVoice Portable Launcher
setlocal
set ROOT=%~dp0
set PATH=%ROOT%ffmpeg\bin;%ROOT%python;%PATH%

echo Iniciando TrueVoice...
echo API en http://localhost:8000
echo Frontend en http://localhost:8501

start "TrueVoice API" /D "%ROOT%" "%ROOT%python\python.exe" -m uvicorn app\api_server:app --host 127.0.0.1 --port 8000 --workers 1 --log-level error

timeout /t 5 /nobreak >nul

start "" "http://localhost:8501"

start "TrueVoice Frontend" /D "%ROOT%" "%ROOT%python\python.exe" -m streamlit run app\frontend.py --server.port 8501 --server.headless true --server.address 127.0.0.1

echo.
echo Presiona cualquier tecla para salir cuando termines.
pause >nul
endlocal
'''
    run_bat.write_text(bat_content, encoding='utf-8')
    print("run.bat creado.")

    # 6. Shortcut en escritorio
    desktop_shortcut = str(home / "Desktop" / "TrueVoice.lnk")
    create_shortcut(str(run_bat), '', str(install_dir), 'Lanza TrueVoice (API + Frontend)', desktop_shortcut)

    print("\\n" + "="*60)
    print("¡INSTALACIÓN COMPLETA!")
    print(f"Ejecuta: {run_bat}")
    print("O usa el shortcut en el escritorio.")
    print("Primera ejecución descargará el modelo (~6GB). Necesitas internet.")
    print("="*60)
    input("Presiona Enter para salir...")

if __name__ == "__main__":
    main()