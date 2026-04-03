package generation

import (
	"archive/zip"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"
)

const (
	pythonEmbedURL = "https://www.python.org/ftp/python/3.11.8/python-3.11.8-embed-amd64.zip"
	getPipURL      = "https://bootstrap.pypa.io/get-pip.py"
)

type setupState struct {
	mu       sync.RWMutex
	running  bool
	ready    bool
	stage    string
	errorMsg string
	updated  float64
	python   string
}

func newSetupState() *setupState {
	return &setupState{stage: "idle", updated: float64(time.Now().Unix())}
}

func (s *setupState) set(stage string, running bool, ready bool, errMsg string, py string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.stage = stage
	s.running = running
	s.ready = ready
	s.errorMsg = errMsg
	if py != "" {
		s.python = py
	}
	s.updated = float64(time.Now().Unix())
}

func (s *setupState) snapshot() map[string]any {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return map[string]any{
		"running":      s.running,
		"ready":        s.ready,
		"stage":        s.stage,
		"error":        s.errorMsg,
		"last_update":  s.updated,
		"python_path":  s.python,
		"runtime_path": runtimeRoot(),
	}
}

func runtimeRoot() string {
	appData := os.Getenv("APPDATA")
	if appData == "" {
		wd, _ := os.Getwd()
		return filepath.Join(wd, "runtime")
	}
	return filepath.Join(appData, "TrueVoice", "runtime")
}

func runtimePythonExe() string {
	if runtime.GOOS == "windows" {
		return filepath.Join(runtimeRoot(), "python", "python.exe")
	}
	return filepath.Join(runtimeRoot(), "python", "bin", "python3")
}

func runtimeReadyFile() string {
	return filepath.Join(runtimeRoot(), ".ready")
}

func runtimeManifestFile() string {
	return filepath.Join(runtimeRoot(), "manifest.json")
}

func (m *Manager) ensureRuntimeReady() (string, error) {
	m.bootMu.Lock()
	defer m.bootMu.Unlock()

	if py := runtimePythonExe(); fileExists(py) && fileExists(runtimeReadyFile()) {
		m.setup.set("ready", false, true, "", py)
		return py, nil
	}

	m.setup.set("checking", true, false, "", "")

	if err := os.MkdirAll(runtimeRoot(), 0755); err != nil {
		m.setup.set("failed", false, false, err.Error(), "")
		return "", err
	}

	py := runtimePythonExe()
	if !fileExists(py) {
		if runtime.GOOS != "windows" {
			sys := findSystemPython()
			if sys == "" {
				err := errors.New("no Python runtime found (system python not available)")
				m.setup.set("failed", false, false, err.Error(), "")
				return "", err
			}
			py = sys
		} else {
			m.setup.set("downloading_python", true, false, "", "")
			if err := m.installEmbeddedPython(); err != nil {
				m.setup.set("failed", false, false, err.Error(), "")
				return "", err
			}
		}
	}

	m.setup.set("installing_dependencies", true, false, "", py)
	if err := m.installPythonDependencies(py); err != nil {
		m.setup.set("failed", false, false, err.Error(), py)
		return "", err
	}

	modelID := strings.TrimSpace(m.cfg.GetString("selected_model"))
	if modelID == "" {
		modelID = "microsoft/VibeVoice-1.5b"
	}

	m.setup.set("downloading_model", true, false, "", py)
	if err := m.prefetchModel(py, modelID); err != nil {
		m.setup.set("failed", false, false, err.Error(), py)
		return "", err
	}

	manifest := map[string]any{
		"updated":               time.Now().UTC().Format(time.RFC3339),
		"python":                py,
		"vibevoice_model":       "microsoft/VibeVoice-1.5b",
		"bootstrap_complete":    true,
		"bootstrap_description": "runtime python + deps installed",
		"prefetched_model":      modelID,
	}
	_ = writeJSONFile(runtimeManifestFile(), manifest)
	_ = os.WriteFile(runtimeReadyFile(), []byte("ok"), 0644)

	m.setup.set("ready", false, true, "", py)
	return py, nil
}

func (m *Manager) prefetchModel(py, modelID string) error {
	cacheRoot := filepath.Join(runtimeRoot(), "models", "huggingface")
	if err := os.MkdirAll(cacheRoot, 0755); err != nil {
		return fmt.Errorf("create model cache dir failed: %w", err)
	}

	code := fmt.Sprintf(`from huggingface_hub import snapshot_download
snapshot_download(repo_id=%q, cache_dir=%q, resume_download=True)
print("model_ready")
`, modelID, cacheRoot)

	cmd := exec.Command(py, "-c", code)
	cmd.Env = append(os.Environ(),
		"PYTHONUTF8=1",
		fmt.Sprintf("HF_HOME=%s", cacheRoot),
		fmt.Sprintf("TRANSFORMERS_CACHE=%s", filepath.Join(cacheRoot, "transformers")),
	)

	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("prefetch model %s failed: %v: %s", modelID, err, string(out))
	}

	return nil
}

func (m *Manager) installEmbeddedPython() error {
	root := runtimeRoot()
	downloads := filepath.Join(root, "downloads")
	pythonDir := filepath.Join(root, "python")
	if err := os.MkdirAll(downloads, 0755); err != nil {
		return err
	}
	if err := os.MkdirAll(pythonDir, 0755); err != nil {
		return err
	}

	zipPath := filepath.Join(downloads, "python-embed.zip")
	if !fileExists(zipPath) {
		if err := downloadFile(pythonEmbedURL, zipPath); err != nil {
			return fmt.Errorf("download python embed: %w", err)
		}
	}

	if err := unzip(zipPath, pythonDir); err != nil {
		return fmt.Errorf("extract python embed: %w", err)
	}

	if err := enableSitePackages(pythonDir); err != nil {
		return fmt.Errorf("patch embedded python site-packages: %w", err)
	}

	py := runtimePythonExe()
	if !fileExists(py) {
		return fmt.Errorf("embedded python executable not found at %s", py)
	}

	getPipPath := filepath.Join(downloads, "get-pip.py")
	if !fileExists(getPipPath) {
		if err := downloadFile(getPipURL, getPipPath); err != nil {
			return fmt.Errorf("download get-pip: %w", err)
		}
	}

	cmd := exec.Command(py, getPipPath, "--disable-pip-version-check")
	cmd.Env = append(os.Environ(), "PYTHONUTF8=1")
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("install pip failed: %v: %s", err, string(out))
	}
	return nil
}

func (m *Manager) installPythonDependencies(py string) error {
	wd := projectRoot()

	if err := ensurePipInstalled(py); err != nil {
		return err
	}

	pipInstall := func(args ...string) error {
		cmd := exec.Command(py, append([]string{"-m", "pip", "install", "--disable-pip-version-check"}, args...)...)
		cmd.Env = append(os.Environ(),
			"PYTHONUTF8=1",
			fmt.Sprintf("HF_HOME=%s", filepath.Join(runtimeRoot(), "models", "huggingface")),
		)
		cmd.Dir = wd
		out, err := cmd.CombinedOutput()
		if err != nil {
			return fmt.Errorf("pip install %v failed: %v: %s", args, err, string(out))
		}
		return nil
	}

	if err := pipInstall("--upgrade", "pip", "setuptools", "wheel"); err != nil {
		return err
	}

	if err := pipInstall("numpy<2"); err != nil {
		return err
	}

	if err := pipInstall("torch==2.0.1", "torchaudio==2.0.2", "--index-url", "https://download.pytorch.org/whl/cpu"); err != nil {
		return err
	}

	if err := pipInstall(
		"transformers==4.51.3",
		"accelerate==1.6.0",
		"huggingface_hub>=0.19.0",
		"soundfile>=0.12.0",
		"scipy>=1.10.0",
		"datasets==3.5.0",
		"diffusers",
		"peft",
		"numba>=0.57.0",
		"llvmlite>=0.40.0",
		"librosa",
		"absl-py",
		"ml-collections",
		"av",
	); err != nil {
		return err
	}

	vibeVoicePath := filepath.Join(wd, "VibeVoice")
	if fileExists(filepath.Join(vibeVoicePath, "pyproject.toml")) {
		if err := pipInstall("-e", vibeVoicePath); err != nil {
			return err
		}
	}

	return nil
}

func ensurePipInstalled(py string) error {
	if err := exec.Command(py, "-m", "pip", "--version").Run(); err == nil {
		return nil
	}

	if err := enableSitePackages(filepath.Dir(py)); err != nil {
		return fmt.Errorf("enable site-packages failed: %w", err)
	}

	if err := exec.Command(py, "-m", "pip", "--version").Run(); err == nil {
		return nil
	}

	downloads := filepath.Join(runtimeRoot(), "downloads")
	if err := os.MkdirAll(downloads, 0755); err != nil {
		return err
	}
	getPipPath := filepath.Join(downloads, "get-pip.py")
	if !fileExists(getPipPath) {
		if err := downloadFile(getPipURL, getPipPath); err != nil {
			return fmt.Errorf("download get-pip: %w", err)
		}
	}

	cmd := exec.Command(py, getPipPath, "--disable-pip-version-check")
	cmd.Env = append(os.Environ(), "PYTHONUTF8=1")
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("install pip failed: %v: %s", err, string(out))
	}

	if err := exec.Command(py, "-m", "pip", "--version").Run(); err != nil {
		return fmt.Errorf("pip still unavailable after bootstrap")
	}

	return nil
}

func findSystemPython() string {
	if path, err := exec.LookPath("python"); err == nil {
		return path
	}
	if path, err := exec.LookPath("python3"); err == nil {
		return path
	}
	return ""
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func writeJSONFile(path string, data any) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, raw, 0644)
}

func downloadFile(srcURL, dst string) error {
	resp, err := http.Get(srcURL)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return fmt.Errorf("download failed with status %d", resp.StatusCode)
	}

	if err := os.MkdirAll(filepath.Dir(dst), 0755); err != nil {
		return err
	}
	f, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = io.Copy(f, resp.Body)
	return err
}

func unzip(zipPath, dstDir string) error {
	zr, err := zip.OpenReader(zipPath)
	if err != nil {
		return err
	}
	defer zr.Close()

	for _, f := range zr.File {
		target := filepath.Join(dstDir, f.Name)
		if !strings.HasPrefix(filepath.Clean(target), filepath.Clean(dstDir)) {
			return fmt.Errorf("invalid zip entry path: %s", f.Name)
		}
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0755); err != nil {
				return err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
			return err
		}

		rc, err := f.Open()
		if err != nil {
			return err
		}
		out, err := os.Create(target)
		if err != nil {
			rc.Close()
			return err
		}
		_, err = io.Copy(out, rc)
		_ = out.Close()
		_ = rc.Close()
		if err != nil {
			return err
		}
	}
	return nil
}

func enableSitePackages(pyDir string) error {
	entries, err := os.ReadDir(pyDir)
	if err != nil {
		return err
	}
	for _, e := range entries {
		name := strings.ToLower(e.Name())
		if strings.HasPrefix(name, "python") && strings.HasSuffix(name, "._pth") {
			pthPath := filepath.Join(pyDir, e.Name())
			raw, err := os.ReadFile(pthPath)
			if err != nil {
				return err
			}
			content := string(raw)
			if strings.Contains(content, "\nimport site\n") || strings.HasSuffix(content, "\nimport site") {
				return nil
			}
			if strings.Contains(content, "#import site") {
				content = strings.Replace(content, "#import site", "import site", 1)
			} else {
				content = strings.TrimRight(content, "\r\n") + "\nimport site\n"
			}
			return os.WriteFile(pthPath, []byte(content), 0644)
		}
	}
	return nil
}
