package server

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"time"
)

func (s *Server) listModels(w http.ResponseWriter, r *http.Request) {
	models := []map[string]string{
		{
			"id":   "microsoft/VibeVoice-1.5b",
			"name": "VibeVoice 1.5B (recomendado)",
			"size": "~6 GB",
		},
		{
			"id":   "microsoft/VibeVoice-7b",
			"name": "VibeVoice 7B",
			"size": "~28 GB",
		},
	}

	writeJSON(w, http.StatusOK, models)
}

// ── Ollama Proxy ───────────────────────────────────────────────────

func (s *Server) ollamaModels(w http.ResponseWriter, r *http.Request) {
	ollamaURL := s.cfg.GetString("ollama_url")
	if ollamaURL == "" {
		ollamaURL = "http://localhost:11434"
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(ollamaURL + "/api/tags")
	if err != nil {
		writeError(w, http.StatusBadGateway, fmt.Sprintf("Cannot reach Ollama: %v", err))
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
	ollamaURL := s.cfg.GetString("ollama_url")
	if ollamaURL == "" {
		ollamaURL = "http://localhost:11434"
	}

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
	resp, err := client.Post(ollamaURL+"/api/generate", "application/json", strings.NewReader(string(raw)))
	if err != nil {
		writeError(w, http.StatusBadGateway, fmt.Sprintf("Ollama error: %v", err))
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
		// Linux/Docker: list /mnt/
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
