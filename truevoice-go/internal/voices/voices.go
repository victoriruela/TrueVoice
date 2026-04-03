package voices

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"truevoice/internal/config"
)

// DefaultVoices maps alias → filename stem (without .wav).
var DefaultVoices = map[string]string{
	"Alice":  "en-Alice_woman",
	"Carter": "en-Carter_man",
	"Frank":  "en-Frank_man",
	"Mary":   "en-Mary_woman_bgm",
	"Maya":   "en-Maya_woman",
	"Samuel": "in-Samuel_man",
	"Anchen": "zh-Anchen_man_bgm",
	"Bowen":  "zh-Bowen_man",
	"Xinran": "zh-Xinran_woman",
}

type VoiceInfo struct {
	Name     string  `json:"name"`
	Filename string  `json:"filename"`
	Alias    *string `json:"alias"`
}

type Manager struct {
	cfg *config.Store
}

func NewManager(cfg *config.Store) *Manager {
	return &Manager{cfg: cfg}
}

// voicesDir returns the custom voices directory.
func (m *Manager) voicesDir() string {
	custom := m.cfg.GetString("voice_directory")
	if custom != "" {
		return custom
	}
	dir := projectRoot()
	return filepath.Join(dir, "voices")
}

// demoVoicesDir returns the VibeVoice built-in demo voices directory.
func (m *Manager) demoVoicesDir() string {
	dir := projectRoot()
	return filepath.Join(dir, "VibeVoice", "demo", "voices")
}

func projectRoot() string {
	wd, _ := os.Getwd()
	candidates := []string{wd, filepath.Dir(wd)}
	for _, c := range candidates {
		if _, err := os.Stat(filepath.Join(c, "vibevoice_app.py")); err == nil {
			return c
		}
	}
	return wd
}

func (m *Manager) ListHandler(w http.ResponseWriter, r *http.Request) {
	dir := r.URL.Query().Get("directory")
	if dir == "" {
		dir = m.voicesDir()
	}

	voiceList := make([]VoiceInfo, 0)
	seen := make(map[string]bool)

	// 1. Custom voices directory
	if entries, err := os.ReadDir(dir); err == nil {
		for _, e := range entries {
			if e.IsDir() || !isWav(e.Name()) {
				continue
			}
			stem := strings.TrimSuffix(e.Name(), filepath.Ext(e.Name()))
			alias := aliasFor(stem)
			voiceList = append(voiceList, VoiceInfo{
				Name:     stem,
				Filename: e.Name(),
				Alias:    alias,
			})
			seen[strings.ToLower(stem)] = true
		}
	}

	// 2. Demo voices (only those not already listed)
	demoDir := m.demoVoicesDir()
	if entries, err := os.ReadDir(demoDir); err == nil {
		for _, e := range entries {
			if e.IsDir() || !isWav(e.Name()) {
				continue
			}
			stem := strings.TrimSuffix(e.Name(), filepath.Ext(e.Name()))
			if seen[strings.ToLower(stem)] {
				continue
			}
			alias := aliasFor(stem)
			voiceList = append(voiceList, VoiceInfo{
				Name:     stem,
				Filename: filepath.Join("VibeVoice", "demo", "voices", e.Name()),
				Alias:    alias,
			})
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(voiceList)
}

func (m *Manager) UploadHandler(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(50 << 20); err != nil { // 50MB
		writeError(w, http.StatusBadRequest, "Invalid multipart form")
		return
	}

	name := r.FormValue("voice_name")
	if name == "" {
		name = r.FormValue("name")
	}
	if name == "" {
		writeError(w, http.StatusBadRequest, "voice_name is required")
		return
	}

	file, _, err := r.FormFile("audio_file")
	if err != nil {
		file, _, err = r.FormFile("file")
	}
	if err != nil {
		writeError(w, http.StatusBadRequest, "audio_file is required")
		return
	}
	defer file.Close()

	dir := m.voicesDir()
	os.MkdirAll(dir, 0755)

	outPath := filepath.Join(dir, name+".wav")
	out, err := os.Create(outPath)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	defer out.Close()

	if _, err := io.Copy(out, file); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	alias := aliasFor(name)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(VoiceInfo{
		Name:     name,
		Filename: name + ".wav",
		Alias:    alias,
	})
}

func (m *Manager) DeleteHandler(w http.ResponseWriter, r *http.Request) {
	name := filepath.Base(r.URL.Path) // last segment
	if name == "" || name == "." {
		writeError(w, http.StatusBadRequest, "voice name is required")
		return
	}

	dir := m.voicesDir()
	target := filepath.Join(dir, name+".wav")
	if _, err := os.Stat(target); os.IsNotExist(err) {
		// Try without adding .wav
		target = filepath.Join(dir, name)
	}

	if err := os.Remove(target); err != nil {
		writeError(w, http.StatusNotFound, fmt.Sprintf("Voice not found: %s", name))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "deleted", "name": name})
}

// ResolveVoice finds the absolute path to a voice WAV file.
func (m *Manager) ResolveVoice(name string) string {
	if name == "" {
		name = "Alice"
	}

	// 1. Absolute path
	if filepath.IsAbs(name) {
		if _, err := os.Stat(name); err == nil {
			return name
		}
	}

	// 2. Alias lookup
	if stem, ok := DefaultVoices[name]; ok {
		// Check custom dir first
		p := filepath.Join(m.voicesDir(), stem+".wav")
		if _, err := os.Stat(p); err == nil {
			return p
		}
		// Then demo dir
		p = filepath.Join(m.demoVoicesDir(), stem+".wav")
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}

	// 3. Direct filename in voices dir
	p := filepath.Join(m.voicesDir(), name+".wav")
	if _, err := os.Stat(p); err == nil {
		return p
	}

	// 4. Case-insensitive search
	dir := m.voicesDir()
	if entries, err := os.ReadDir(dir); err == nil {
		nameLower := strings.ToLower(name)
		for _, e := range entries {
			stem := strings.TrimSuffix(e.Name(), filepath.Ext(e.Name()))
			if strings.ToLower(stem) == nameLower {
				return filepath.Join(dir, e.Name())
			}
		}
		// Partial match
		for _, e := range entries {
			stem := strings.TrimSuffix(e.Name(), filepath.Ext(e.Name()))
			if strings.Contains(strings.ToLower(stem), nameLower) {
				return filepath.Join(dir, e.Name())
			}
		}
	}

	// 5. Demo dir fallback
	demoDir := m.demoVoicesDir()
	if entries, err := os.ReadDir(demoDir); err == nil {
		nameLower := strings.ToLower(name)
		for _, e := range entries {
			stem := strings.TrimSuffix(e.Name(), filepath.Ext(e.Name()))
			if strings.Contains(strings.ToLower(stem), nameLower) {
				return filepath.Join(demoDir, e.Name())
			}
		}
	}

	return name // Return as-is, let downstream handle the error
}

func isWav(name string) bool {
	return strings.HasSuffix(strings.ToLower(name), ".wav")
}

func aliasFor(stem string) *string {
	for alias, s := range DefaultVoices {
		if strings.EqualFold(s, stem) || strings.EqualFold(alias, stem) {
			return &alias
		}
	}
	return nil
}

func writeError(w http.ResponseWriter, status int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{"detail": msg})
}
