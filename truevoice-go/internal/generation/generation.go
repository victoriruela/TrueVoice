package generation

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"truevoice/internal/config"
	"truevoice/internal/voices"
)

var (
	reProgressStart = regexp.MustCompile(`PROGRESS_START:(\d+)`)
	reProgressStep  = regexp.MustCompile(`PROGRESS_STEP:(\d+)`)
)

// ── Progress tracking ──────────────────────────────────────────────

type ProgressEntry struct {
	Total      int     `json:"total"`
	Current    int     `json:"current"`
	Status     string  `json:"status"`
	Error      string  `json:"error,omitempty"`
	StartTime  float64 `json:"start_time"`
	LastUpdate float64 `json:"last_update"`
}

// ── Active process tracking ────────────────────────────────────────

type activeProcess struct {
	cmd    *exec.Cmd
	cancel context.CancelFunc
}

// ── Manager ────────────────────────────────────────────────────────

type Manager struct {
	cfg      *config.Store
	voices   *voices.Manager
	progress sync.Map // map[string]*ProgressEntry
	procs    sync.Map // map[string]*activeProcess
	preferredFilenames sync.Map // map[audioID]string
	setup    *setupState
	bootMu   sync.Mutex
}

func NewManager(cfg *config.Store) *Manager {
	return &Manager{
		cfg:    cfg,
		voices: voices.NewManager(cfg),
		setup:  newSetupState(),
	}
}

func (m *Manager) CancelAll() {
	m.procs.Range(func(key, val any) bool {
		if ap, ok := val.(*activeProcess); ok {
			ap.cancel()
		}
		return true
	})
}

// BootstrapRuntime ensures the embedded/system Python runtime and dependencies
// are installed before serving generation requests.
func (m *Manager) BootstrapRuntime() error {
	_, err := m.ensureRuntimeReady()
	return err
}

// ── Directories ────────────────────────────────────────────────────

func tempDir() string {
	dir := projectRoot()
	d := filepath.Join(dir, "temp_outputs")
	os.MkdirAll(d, 0755)
	return d
}

func outputsDir() string {
	dir := projectRoot()
	d := filepath.Join(dir, "api_outputs")
	os.MkdirAll(d, 0755)
	return d
}

func uniqueOutputPath(dir, filename string) (string, string) {
	ext := filepath.Ext(filename)
	base := strings.TrimSuffix(filename, ext)
	candidate := filepath.Join(dir, filename)

	if _, err := os.Stat(candidate); os.IsNotExist(err) {
		return candidate, filename
	}

	for i := 1; ; i++ {
		nextName := fmt.Sprintf("%s (%d)%s", base, i, ext)
		nextPath := filepath.Join(dir, nextName)
		if _, err := os.Stat(nextPath); os.IsNotExist(err) {
			return nextPath, nextName
		}
	}
}

func projectRoot() string {
	// Try to get the executable path and work backwards
	if exePath, err := os.Executable(); err == nil {
		// Navigate up from exe location looking for vibevoice_app.py
		current := filepath.Dir(exePath)
		for i := 0; i < 5; i++ { // Check up to 5 levels up
			if fileExists(filepath.Join(current, "vibevoice_app.py")) {
				return current
			}
			parent := filepath.Dir(current)
			if parent == current { // Reached root
				break
			}
			current = parent
		}
	}

	// Fallback to working directory approach
	wd, _ := os.Getwd()
	candidates := []string{wd, filepath.Dir(wd), filepath.Dir(filepath.Dir(wd))}
	for _, c := range candidates {
		if fileExists(filepath.Join(c, "vibevoice_app.py")) {
			return c
		}
	}
	return wd
}

// ── Generate ───────────────────────────────────────────────────────

type GenerateRequest struct {
	Text             string  `json:"text"`
	VoiceName        string  `json:"voice_name"`
	CustomOutputName string  `json:"custom_output_name"`
	OutputDirectory  string  `json:"output_directory"`
	AudioIDHint      string  `json:"audio_id_hint"`
	Model            string  `json:"model"`
	OutputFormat     string  `json:"output_format"`
	CfgScale         float64 `json:"cfg_scale"`
	DdpmSteps        int     `json:"ddpm_steps"`
	DisablePrefill   bool    `json:"disable_prefill"`
}

type GenerateResponse struct {
	Success  bool    `json:"success"`
	Message  string  `json:"message"`
	AudioID  *string `json:"audio_id"`
	Filename *string `json:"filename"`
	IsTemp   bool    `json:"is_temp"`
}

func (m *Manager) GenerateHandler(w http.ResponseWriter, r *http.Request) {
	var req GenerateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.Text == "" {
		writeError(w, http.StatusBadRequest, "text is required")
		return
	}

	// Defaults
	if req.VoiceName == "" {
		req.VoiceName = "Alice"
	}
	if req.Model == "" {
		req.Model = "microsoft/VibeVoice-1.5b"
	}
	if req.OutputFormat == "" {
		req.OutputFormat = "wav"
	}
	if req.CfgScale == 0 {
		req.CfgScale = 2.0
	}
	if req.DdpmSteps == 0 {
		req.DdpmSteps = 30
	}

	// Resolve voice
	voicePath := m.voices.ResolveVoice(req.VoiceName)

	// Audio ID
	audioID := req.AudioIDHint
	if audioID == "" {
		if req.CustomOutputName != "" {
			audioID = req.CustomOutputName
		} else {
			audioID = fmt.Sprintf("tv_%d", time.Now().UnixMilli())
		}
	}

	preferredBase := strings.TrimSpace(req.CustomOutputName)
	preferredBase = strings.TrimSuffix(preferredBase, filepath.Ext(preferredBase))
	preferredBase = strings.TrimSpace(filepath.Base(preferredBase))
	if preferredBase == "" {
		preferredBase = audioID
	}
	preferredFilename := preferredBase + "." + req.OutputFormat
	m.preferredFilenames.Store(audioID, preferredFilename)

	filename := audioID + "." + req.OutputFormat
	outputPath := filepath.Join(tempDir(), filename)

	// Init progress
	now := float64(time.Now().Unix())
	m.progress.Store(audioID, &ProgressEntry{
		Total: req.DdpmSteps, Current: 0, Status: "starting", Error: "",
		StartTime: now, LastUpdate: now,
	})

	// Build subprocess command
	wd := projectRoot()
	pythonExe, err := m.ensureRuntimeReady()
	if err != nil {
		writeError(w, http.StatusServiceUnavailable, fmt.Sprintf("Python sidecar setup failed: %v", err))
		return
	}
	scriptPath := filepath.Join(wd, "vibevoice_app.py")
	if !fileExists(scriptPath) {
		writeError(w, http.StatusInternalServerError, fmt.Sprintf("vibevoice_app.py not found at %s", scriptPath))
		return
	}

	args := []string{
		"-u",
		scriptPath,
		"--text", req.Text,
		"--voice-name", voicePath,
		"--model", req.Model,
		"--output", outputPath,
		"--cfg-scale", fmt.Sprintf("%.2f", req.CfgScale),
		"--ddpm-steps", strconv.Itoa(req.DdpmSteps),
	}
	if req.DisablePrefill {
		args = append(args, "--disable-prefill")
	}

	ctx, cancel := context.WithCancel(context.Background())
	cmd := exec.CommandContext(ctx, pythonExe, args...)
	cmd.Dir = wd

	pyPath := wd
	if existing := os.Getenv("PYTHONPATH"); existing != "" {
		pyPath = wd + string(os.PathListSeparator) + existing
	}
	hfHome := filepath.Join(runtimeRoot(), "models", "huggingface")
	cmd.Env = append(os.Environ(),
		"PYTHONPATH="+pyPath,
		"PYTHONUNBUFFERED=1",
		"HF_HOME="+hfHome,
		"TRANSFORMERS_CACHE="+filepath.Join(hfHome, "transformers"),
	)

	stdout, _ := cmd.StdoutPipe()
	stderr, _ := cmd.StderrPipe()

	m.procs.Store(audioID, &activeProcess{cmd: cmd, cancel: cancel})

	// Launch subprocess in background
	go func() {
		defer func() {
			m.procs.Delete(audioID)
			cancel()
		}()

		errCh := make(chan string, 1)
		go func() {
			b, _ := io.ReadAll(stderr)
			s := strings.TrimSpace(string(b))
			if len(s) > 4000 {
				s = s[len(s)-4000:]
			}
			errCh <- s
		}()

		if err := cmd.Start(); err != nil {
			m.setProgressError(audioID, "error", -1, err.Error())
			return
		}

		m.setProgressError(audioID, "running", 0, "")

		// Parse progress from stdout
		go m.parseProgress(audioID, stdout)

		err := cmd.Wait()
		stderrText := ""
		select {
		case stderrText = <-errCh:
		case <-time.After(2 * time.Second):
		}
		if err != nil {
			if stderrText == "" {
				stderrText = err.Error()
			}
			m.setProgressError(audioID, "error", -1, stderrText)
		} else {
			m.setProgressError(audioID, "done", -1, "")
		}
	}()

	writeJSON(w, http.StatusOK, GenerateResponse{
		Success:  true,
		Message:  "Generation started",
		AudioID:  &audioID,
		Filename: &filename,
		IsTemp:   true,
	})
}

func (m *Manager) parseProgress(audioID string, r io.Reader) {
	scanner := bufio.NewScanner(r)
	for scanner.Scan() {
		line := scanner.Text()
		if match := reProgressStart.FindStringSubmatch(line); len(match) == 2 {
			total, _ := strconv.Atoi(match[1])
			if entry, ok := m.progress.Load(audioID); ok {
				p := entry.(*ProgressEntry)
				p.Total = total
				p.Status = "generating"
				p.Error = ""
				p.LastUpdate = float64(time.Now().Unix())
			}
		} else if match := reProgressStep.FindStringSubmatch(line); len(match) == 2 {
			current, _ := strconv.Atoi(match[1])
			if entry, ok := m.progress.Load(audioID); ok {
				p := entry.(*ProgressEntry)
				p.Current = current
				p.LastUpdate = float64(time.Now().Unix())
			}
		}
	}
}

func (m *Manager) setProgress(audioID, status string, current int) {
	m.setProgressError(audioID, status, current, "")
}

func (m *Manager) setProgressError(audioID, status string, current int, errMsg string) {
	if entry, ok := m.progress.Load(audioID); ok {
		p := entry.(*ProgressEntry)
		p.Status = status
		p.Error = errMsg
		p.LastUpdate = float64(time.Now().Unix())
		if current >= 0 {
			p.Current = current
		}
	}
}

// ── Progress ───────────────────────────────────────────────────────

func (m *Manager) ProgressHandler(w http.ResponseWriter, r *http.Request) {
	id := filepath.Base(r.URL.Path)
	entry, ok := m.progress.Load(id)
	if !ok {
		writeJSON(w, http.StatusOK, ProgressEntry{Status: "unknown"})
		return
	}
	writeJSON(w, http.StatusOK, entry)
}

// ── Cancel ─────────────────────────────────────────────────────────

func (m *Manager) CancelHandler(w http.ResponseWriter, r *http.Request) {
	id := filepath.Base(r.URL.Path)
	if proc, ok := m.procs.Load(id); ok {
		ap := proc.(*activeProcess)
		ap.cancel()
		m.setProgress(id, "cancelled", -1)
		writeJSON(w, http.StatusOK, map[string]string{"status": "cancelled"})
		return
	}
	writeError(w, http.StatusNotFound, "No active generation with that ID")
}

func (m *Manager) CancelAllHandler(w http.ResponseWriter, r *http.Request) {
	cancelled := 0
	m.procs.Range(func(key, val any) bool {
		ap, ok := val.(*activeProcess)
		if !ok {
			return true
		}

		ap.cancel()
		if id, ok := key.(string); ok {
			m.setProgress(id, "cancelled", -1)
		}
		cancelled++
		return true
	})

	writeJSON(w, http.StatusOK, map[string]int{"cancelled": cancelled})
}

// ── Audio download ─────────────────────────────────────────────────

func (m *Manager) AudioHandler(w http.ResponseWriter, r *http.Request) {
	id := filepath.Base(r.URL.Path)
	dir := r.URL.Query().Get("directory")

	// Search order: custom dir, temp, outputs
	searchDirs := []string{tempDir(), outputsDir()}
	if dir != "" {
		searchDirs = append([]string{dir}, searchDirs...)
	}

	for _, d := range searchDirs {
		entries, err := os.ReadDir(d)
		if err != nil {
			continue
		}
		for _, e := range entries {
			stem := strings.TrimSuffix(e.Name(), filepath.Ext(e.Name()))
			if stem == id || e.Name() == id {
				http.ServeFile(w, r, filepath.Join(d, e.Name()))
				return
			}
		}
	}
	writeError(w, http.StatusNotFound, "Audio file not found")
}

// ── Confirm Save ───────────────────────────────────────────────────

func (m *Manager) ConfirmSaveHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		AudioID         string `json:"audio_id"`
		OutputDirectory string `json:"output_directory"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	// Find file in temp_outputs
	tmpDir := tempDir()
	outDir := outputsDir()
	if req.OutputDirectory != "" {
		outDir = req.OutputDirectory
		os.MkdirAll(outDir, 0755)
	}

	entries, _ := os.ReadDir(tmpDir)
	for _, e := range entries {
		stem := strings.TrimSuffix(e.Name(), filepath.Ext(e.Name()))
		if stem == req.AudioID || e.Name() == req.AudioID {
			src := filepath.Join(tmpDir, e.Name())
			targetFilename := e.Name()
			if preferred, ok := m.preferredFilenames.Load(req.AudioID); ok {
				if name, ok := preferred.(string); ok && strings.TrimSpace(name) != "" {
					targetFilename = name
				}
			}
			dst, savedFilename := uniqueOutputPath(outDir, targetFilename)
			if err := os.Rename(src, dst); err != nil {
				// Cross-device: copy then delete
				if err := copyFile(src, dst); err != nil {
					writeError(w, http.StatusInternalServerError, err.Error())
					return
				}
				os.Remove(src)
			}
			m.preferredFilenames.Delete(req.AudioID)
			savedStem := strings.TrimSuffix(savedFilename, filepath.Ext(savedFilename))
			writeJSON(w, http.StatusOK, map[string]string{
				"status":   "saved",
				"path":     dst,
				"audio_id": savedStem,
				"filename": savedFilename,
			})
			return
		}
	}
	writeError(w, http.StatusNotFound, "Temp file not found")
}

// ── List Outputs ───────────────────────────────────────────────────

type OutputFileInfo struct {
	ID       string  `json:"id"`
	Filename string  `json:"filename"`
	Path     string  `json:"path"`
	Size     int64   `json:"size"`
	Created  float64 `json:"created"`
}

func (m *Manager) ListOutputsHandler(w http.ResponseWriter, r *http.Request) {
	dir := r.URL.Query().Get("directory")
	if dir == "" {
		dir = outputsDir()
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		writeJSON(w, http.StatusOK, []OutputFileInfo{})
		return
	}

	files := make([]OutputFileInfo, 0)
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		stem := strings.TrimSuffix(e.Name(), filepath.Ext(e.Name()))
		files = append(files, OutputFileInfo{
			ID:       stem,
			Filename: e.Name(),
			Path:     filepath.Join(dir, e.Name()),
			Size:     info.Size(),
			Created:  float64(info.ModTime().Unix()),
		})
	}
	writeJSON(w, http.StatusOK, files)
}

// ── Delete Outputs ─────────────────────────────────────────────────

func (m *Manager) DeleteOutputsHandler(w http.ResponseWriter, r *http.Request) {
	dir := r.URL.Query().Get("directory")
	if dir == "" {
		dir = outputsDir()
	}

	var body struct {
		Filenames []string `json:"filenames"`
	}
	json.NewDecoder(r.Body).Decode(&body)

	// Also check query params
	if len(body.Filenames) == 0 {
		for _, f := range r.URL.Query()["filenames"] {
			body.Filenames = append(body.Filenames, f)
		}
	}

	deleted := 0
	for _, fn := range body.Filenames {
		// Security: prevent path traversal
		base := filepath.Base(fn)
		target := filepath.Join(dir, base)
		if err := os.Remove(target); err == nil {
			deleted++
		}
	}

	writeJSON(w, http.StatusOK, map[string]int{"deleted": deleted})
}

// ── Cleanup Temp ───────────────────────────────────────────────────

func (m *Manager) CleanupTempHandler(w http.ResponseWriter, r *http.Request) {
	dir := tempDir()
	entries, _ := os.ReadDir(dir)
	cutoff := time.Now().Add(-1 * time.Hour)
	deleted := 0

	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		if info.ModTime().Before(cutoff) {
			os.Remove(filepath.Join(dir, e.Name()))
			deleted++
		}
	}

	writeJSON(w, http.StatusOK, map[string]int{"deleted": deleted})
}

// ── Setup Status ───────────────────────────────────────────────────

func (m *Manager) SetupStatusHandler(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, m.setup.snapshot())
}

func (m *Manager) SetupBootstrapHandler(w http.ResponseWriter, r *http.Request) {
	snap := m.setup.snapshot()
	if running, _ := snap["running"].(bool); running {
		writeJSON(w, http.StatusAccepted, map[string]any{
			"status":       "running",
			"python_path":  snap["python_path"],
			"runtime_path": snap["runtime_path"],
		})
		return
	}

	go func() {
		_, _ = m.ensureRuntimeReady()
	}()

	writeJSON(w, http.StatusAccepted, map[string]any{
		"status":       "started",
		"python_path":  "",
		"runtime_path": runtimeRoot(),
	})
}

// ── Helpers ────────────────────────────────────────────────────────

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()

	_, err = io.Copy(out, in)
	return err
}

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"detail": msg})
}
