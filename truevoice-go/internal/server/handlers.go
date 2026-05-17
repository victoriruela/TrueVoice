package server

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"sync"
	"time"

	"truevoice/internal/config"
)

// ── Model download jobs ────────────────────────────────────────────

type modelDownloadJob struct {
	status  string // "downloading", "done", "error"
	message string
}

var globalModelDownloadJobs sync.Map // map[string]*modelDownloadJob

func serverHFHome() string {
	if configured := strings.TrimSpace(os.Getenv("TRUEVOICE_RUNTIME_DIR")); configured != "" {
		return filepath.Join(filepath.Clean(configured), "models", "huggingface")
	}
	if localAppData := strings.TrimSpace(os.Getenv("LOCALAPPDATA")); localAppData != "" {
		return filepath.Join(localAppData, "TrueVoice", "runtime", "models", "huggingface")
	}
	if appData := strings.TrimSpace(os.Getenv("APPDATA")); appData != "" {
		return filepath.Join(appData, "TrueVoice", "runtime", "models", "huggingface")
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".cache", "huggingface")
}

func isModelDownloaded(modelID string) bool {
	// Local path: check if directory exists
	if filepath.IsAbs(modelID) {
		info, err := os.Stat(modelID)
		return err == nil && info.IsDir()
	}
	// HF cache: models--org--name/snapshots/ must exist and be non-empty
	parts := strings.SplitN(modelID, "/", 2)
	if len(parts) != 2 {
		return false
	}
	hfHome := serverHFHome()
	cachePath := filepath.Join(hfHome, "hub",
		fmt.Sprintf("models--%s--%s", parts[0], parts[1]),
		"snapshots",
	)
	entries, err := os.ReadDir(cachePath)
	downloaded := err == nil && len(entries) > 0
	// Debug logging
	fmt.Printf("[model-check] %s → path=%s, exists=%v, entries=%d\n",
		modelID, cachePath, downloaded, len(entries))
	return downloaded
}

func (s *Server) checkModelStatus(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	if strings.TrimSpace(id) == "" {
		writeError(w, http.StatusBadRequest, "id required")
		return
	}
	writeJSON(w, http.StatusOK, map[string]bool{"downloaded": isModelDownloaded(id)})
}

func (s *Server) startModelDownload(w http.ResponseWriter, r *http.Request) {
	var req struct {
		ID string `json:"id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || strings.TrimSpace(req.ID) == "" {
		writeError(w, http.StatusBadRequest, "id required")
		return
	}
	modelID := strings.TrimSpace(req.ID)

	// Check if already downloaded before starting
	if isModelDownloaded(modelID) {
		fmt.Printf("[model-download] %s already downloaded, skipping\n", modelID)
		writeJSON(w, http.StatusOK, map[string]string{
			"download_id": modelID,
			"status":      "already_downloaded",
		})
		return
	}

	// If already in progress, return status immediately
	if existing, ok := globalModelDownloadJobs.Load(modelID); ok {
		job := existing.(*modelDownloadJob)
		if job.status == "downloading" {
			writeJSON(w, http.StatusOK, map[string]string{
				"download_id": modelID,
				"status":      "already_downloading",
			})
			return
		}
	}

	pythonPath := s.gen.GetPythonPath()
	if pythonPath == "" {
		writeError(w, http.StatusServiceUnavailable,
			"Python runtime not ready. Run bootstrap first from Setup.")
		return
	}

	fmt.Printf("[model-download] Starting download for %s\n", modelID)
	job := &modelDownloadJob{status: "downloading"}
	globalModelDownloadJobs.Store(modelID, job)

	go func() {
		script := fmt.Sprintf(
			"from huggingface_hub import snapshot_download; snapshot_download(%q)",
			modelID,
		)
		ctx, cancel := context.WithTimeout(context.Background(), 8*time.Hour)
		defer cancel()

		hfHome := serverHFHome()
		cmd := exec.CommandContext(ctx, pythonPath, "-c", script)
		cmd.Env = append(os.Environ(), "HF_HOME="+hfHome)

		output, err := cmd.CombinedOutput()
		if err != nil {
			msg := strings.TrimSpace(string(output))
			if msg == "" {
				msg = err.Error()
			}
			if len(msg) > 2000 {
				msg = msg[len(msg)-2000:]
			}
			job.status = "error"
			job.message = msg
		} else {
			job.status = "done"
		}
		globalModelDownloadJobs.Store(modelID, job)
	}()

	writeJSON(w, http.StatusOK, map[string]string{"download_id": modelID})
}

func (s *Server) modelDownloadProgress(w http.ResponseWriter, r *http.Request) {
	rawID := r.URL.Query().Get("id")
	id, err := url.QueryUnescape(rawID)
	if err != nil || strings.TrimSpace(id) == "" {
		writeError(w, http.StatusBadRequest, "id required")
		return
	}
	if entry, ok := globalModelDownloadJobs.Load(id); ok {
		job := entry.(*modelDownloadJob)
		writeJSON(w, http.StatusOK, map[string]string{
			"status":  job.status,
			"message": job.message,
		})
	} else {
		writeJSON(w, http.StatusOK, map[string]string{"status": "not_found"})
	}
}

func ollamaURLCandidates(configured string) []string {
	configured = strings.TrimRight(strings.TrimSpace(configured), "/")
	if configured == "" {
		configured = "http://localhost:11434"
	}

	candidates := []string{configured}
	if !strings.EqualFold(configured, "http://localhost:11434") {
		candidates = append(candidates, "http://localhost:11434")
	}
	return candidates
}

func (s *Server) listModels(w http.ResponseWriter, r *http.Request) {
	models := []map[string]string{
		{"id": "microsoft/VibeVoice-1.5b", "name": "VibeVoice 1.5B (recomendado)", "size": "~6 GB"},
		{"id": "aoi-ot/VibeVoice-Large", "name": "VibeVoice Large (máx. calidad)", "size": "~18.7 GB"},
		{"id": "FabioSarracino/VibeVoice-Large-Q8", "name": "VibeVoice Large Q8 (equilibrado)", "size": "~11.6 GB"},
		{"id": "DevParker/VibeVoice7b-low-vram", "name": "VibeVoice Large Q4 (VRAM reducida)", "size": "~6.6 GB"},
	}

	for _, cm := range s.cfg.CustomModels() {
		models = append(models, map[string]string{
			"id":   cm.ID,
			"name": cm.Name,
			"size": cm.Size,
		})
	}

	writeJSON(w, http.StatusOK, models)
}

// ── Ollama Proxy ───────────────────────────────────────────────────

func (s *Server) ollamaModels(w http.ResponseWriter, r *http.Request) {
	client := &http.Client{Timeout: 10 * time.Second}
	var (
		resp    *http.Response
		err     error
		lastErr error
	)
	for _, baseURL := range ollamaURLCandidates(s.cfg.GetString("ollama_url")) {
		resp, err = client.Get(baseURL + "/api/tags")
		if err == nil {
			break
		}
		lastErr = err
	}
	if err != nil {
		writeError(w, http.StatusBadGateway, fmt.Sprintf("Cannot reach Ollama: %v", lastErr))
		return
	}
	defer resp.Body.Close()

	var result struct {
		Models []struct {
			Name string `json:"name"`
		} `json:"models"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		writeError(w, http.StatusBadGateway, "Invalid Ollama response")
		return
	}

	names := make([]string, 0, len(result.Models))
	for _, m := range result.Models {
		names = append(names, m.Name)
	}
	writeJSON(w, http.StatusOK, names)
}

func (s *Server) ollamaGenerate(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Prompt  string         `json:"prompt"`
		Model   string         `json:"model"`
		Options map[string]any `json:"options"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.Model == "" {
		req.Model = s.cfg.GetString("ollama_model")
	}

	body := map[string]any{
		"model":  req.Model,
		"prompt": req.Prompt,
		"stream": false,
	}
	if req.Options != nil {
		body["options"] = req.Options
	}

	raw, _ := json.Marshal(body)
	client := &http.Client{Timeout: 5 * time.Minute}
	var (
		resp    *http.Response
		err     error
		lastErr error
	)
	for _, baseURL := range ollamaURLCandidates(s.cfg.GetString("ollama_url")) {
		resp, err = client.Post(baseURL+"/api/generate", "application/json", strings.NewReader(string(raw)))
		if err == nil {
			break
		}
		lastErr = err
	}
	if err != nil {
		writeError(w, http.StatusBadGateway, fmt.Sprintf("Ollama error: %v", lastErr))
		return
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	var result struct {
		Response string `json:"response"`
		Model    string `json:"model"`
	}
	json.Unmarshal(respBody, &result)

	writeJSON(w, http.StatusOK, map[string]string{
		"text":  result.Response,
		"model": result.Model,
	})
}

// ── Directory Browse ───────────────────────────────────────────────

func (s *Server) browseDrives(w http.ResponseWriter, r *http.Request) {
	var drives []string
	if runtime.GOOS == "windows" {
		for c := 'A'; c <= 'Z'; c++ {
			drive := fmt.Sprintf("%c:\\", c)
			if _, err := os.Stat(drive); err == nil {
				drives = append(drives, drive)
			}
		}
	} else {
		// Linux: list /mnt/
		entries, err := os.ReadDir("/mnt")
		if err == nil {
			for _, e := range entries {
				if e.IsDir() {
					drives = append(drives, filepath.Join("/mnt", e.Name()))
				}
			}
		}
		if len(drives) == 0 {
			drives = []string{"/"}
		}
	}
	writeJSON(w, http.StatusOK, drives)
}

func (s *Server) browseFolders(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Query().Get("path")
	if path == "" {
		writeError(w, http.StatusBadRequest, "path parameter required")
		return
	}

	// Security: prevent path traversal
	cleaned := filepath.Clean(path)
	if strings.Contains(cleaned, "..") {
		writeError(w, http.StatusBadRequest, "invalid path")
		return
	}

	entries, err := os.ReadDir(cleaned)
	if err != nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("Cannot read directory: %v", err))
		return
	}

	type folderEntry struct {
		Name string `json:"name"`
		Path string `json:"path"`
	}

	folders := make([]folderEntry, 0)
	for _, e := range entries {
		if e.IsDir() && !strings.HasPrefix(e.Name(), ".") {
			folders = append(folders, folderEntry{
				Name: e.Name(),
				Path: filepath.Join(cleaned, e.Name()),
			})
		}
	}
	sort.Slice(folders, func(i, j int) bool {
		return strings.ToLower(folders[i].Name) < strings.ToLower(folders[j].Name)
	})

	parent := filepath.Dir(cleaned)
	if parent == cleaned {
		parent = ""
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"current": cleaned,
		"parent":  parent,
		"folders": folders,
	})
}

// ── Narrators CRUD ─────────────────────────────────────────────────

func (s *Server) listNarrators(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, s.cfg.Narrators())
}

func (s *Server) createOrUpdateNarrator(w http.ResponseWriter, r *http.Request) {
	var n config.NarratorConfig
	if err := json.NewDecoder(r.Body).Decode(&n); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if strings.TrimSpace(n.Key) == "" {
		writeError(w, http.StatusBadRequest, "key is required")
		return
	}
	if n.SpeakerSlot <= 0 {
		n.SpeakerSlot = 1
	}

	list := s.cfg.Narrators()
	found := false
	for i := range list {
		if list[i].Key == n.Key {
			list[i] = n
			found = true
			break
		}
	}
	if !found {
		list = append(list, n)
	}
	if n.IsPrincipal {
		for i := range list {
			if list[i].Key != n.Key {
				list[i].IsPrincipal = false
			}
		}
	}
	if err := s.cfg.SetNarrators(list); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, list)
}

func (s *Server) updateNarrator(w http.ResponseWriter, r *http.Request) {
	key := extractServerPathParam(r.URL.Path, "narrators")
	if key == "" {
		writeError(w, http.StatusBadRequest, "key required")
		return
	}
	var patch map[string]any
	if err := json.NewDecoder(r.Body).Decode(&patch); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	list := s.cfg.Narrators()
	idx := -1
	for i, n := range list {
		if n.Key == key {
			idx = i
			break
		}
	}
	if idx < 0 {
		writeError(w, http.StatusNotFound, "narrator not found")
		return
	}
	if v, ok := patch["name"].(string); ok {
		list[idx].Name = v
	}
	if v, ok := patch["voice"].(string); ok {
		list[idx].Voice = v
	}
	if v, ok := patch["speaker_slot"].(float64); ok {
		list[idx].SpeakerSlot = int(v)
	}
	if v, ok := patch["is_principal"].(bool); ok {
		list[idx].IsPrincipal = v
		if v {
			for i := range list {
				if i != idx {
					list[i].IsPrincipal = false
				}
			}
		}
	}
	if v, ok := patch["key"].(string); ok && v != "" {
		list[idx].Key = v
	}
	if err := s.cfg.SetNarrators(list); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, list[idx])
}

func (s *Server) deleteNarrator(w http.ResponseWriter, r *http.Request) {
	key := extractServerPathParam(r.URL.Path, "narrators")
	if key == "" {
		writeError(w, http.StatusBadRequest, "key required")
		return
	}
	list := s.cfg.Narrators()
	out := make([]config.NarratorConfig, 0, len(list))
	for _, n := range list {
		if n.Key != key {
			out = append(out, n)
		}
	}
	if err := s.cfg.SetNarrators(out); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "deleted"})
}

func (s *Server) setPrincipalNarrator(w http.ResponseWriter, r *http.Request) {
	// Path: /narrators/{key}/set-principal — key is between /narrators/ and /set-principal
	rest := strings.TrimPrefix(r.URL.Path, "/narrators/")
	rest = strings.TrimSuffix(rest, "/set-principal")
	key := strings.TrimSpace(rest)
	if key == "" {
		writeError(w, http.StatusBadRequest, "key required")
		return
	}
	list := s.cfg.Narrators()
	found := false
	for i := range list {
		if list[i].Key == key {
			list[i].IsPrincipal = true
			found = true
		} else {
			list[i].IsPrincipal = false
		}
	}
	if !found {
		writeError(w, http.StatusNotFound, "narrator not found")
		return
	}
	if err := s.cfg.SetNarrators(list); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, list)
}

// ── Custom Models CRUD ─────────────────────────────────────────────

func (s *Server) addCustomModel(w http.ResponseWriter, r *http.Request) {
	var cm config.CustomModel
	if err := json.NewDecoder(r.Body).Decode(&cm); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if strings.TrimSpace(cm.ID) == "" {
		writeError(w, http.StatusBadRequest, "id is required")
		return
	}
	if cm.Name == "" {
		cm.Name = cm.ID
	}
	list := s.cfg.CustomModels()
	found := false
	for i := range list {
		if list[i].ID == cm.ID {
			list[i] = cm
			found = true
			break
		}
	}
	if !found {
		list = append(list, cm)
	}
	if err := s.cfg.SetCustomModels(list); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, list)
}

func (s *Server) deleteCustomModel(w http.ResponseWriter, r *http.Request) {
	raw := extractServerPathParam(r.URL.Path, "models")
	id, err := url.QueryUnescape(raw)
	if err != nil || id == "" {
		writeError(w, http.StatusBadRequest, "id required")
		return
	}
	list := s.cfg.CustomModels()
	out := make([]config.CustomModel, 0, len(list))
	for _, m := range list {
		if m.ID != id {
			out = append(out, m)
		}
	}
	if err := s.cfg.SetCustomModels(out); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "deleted"})
}

func extractServerPathParam(urlPath, after string) string {
	parts := strings.Split(urlPath, "/"+after+"/")
	if len(parts) < 2 {
		return ""
	}
	seg := parts[1]
	if idx := strings.Index(seg, "/"); idx >= 0 {
		seg = seg[:idx]
	}
	return seg
}
