package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sync"
)

// AppConfig mirrors the frontend_config.json structure.
type AppConfig struct {
	SelectedVoice     string `json:"selected_voice"`
	SelectedModelName string `json:"selected_model_name"`
	SelectedModel     string `json:"selected_model"`
	OutputFormat      string `json:"output_format"`
	CfgScale          float64 `json:"cfg_scale"`
	DdpmSteps         int     `json:"ddpm_steps"`
	DisablePrefill    bool    `json:"disable_prefill"`
	VoiceFolderType   string `json:"voice_folder_type"`
	CustomFolderPath  string `json:"custom_folder_path"`
	OutputFolderType  string `json:"output_folder_type"`
	CustomOutputPath  string `json:"custom_output_path"`
	TextsFolderType   string `json:"texts_folder_type"`
	CustomTextsPath   string `json:"custom_texts_path"`
	OutputDirectory   string `json:"output_directory"`
	VoiceDirectory    string `json:"voice_directory"`
	OllamaURL         string `json:"ollama_url"`
	OllamaModel       string `json:"ollama_model"`
	LastTextInput     string `json:"last_text_input"`
	LastCustomName    string `json:"last_custom_name"`
	LastRaceSession   string `json:"last_race_session"`
	AudioOutputFolder string `json:"audio_output_folder"`
	TextsOutputFolder string `json:"texts_output_folder"`

	// Extra holds unknown keys for forward compatibility.
	Extra map[string]any `json:"-"`
}

// Store provides thread-safe access to the config file.
type Store struct {
	mu   sync.RWMutex
	path string
	data map[string]any // raw JSON map, superset of AppConfig
}

func Default() *Store {
	s := &Store{
		data: map[string]any{
			"selected_voice":      "Alice",
			"selected_model_name": "VibeVoice 1.5B (recomendado)",
			"selected_model":      "microsoft/VibeVoice-1.5b",
			"output_format":       "wav",
			"cfg_scale":           2.0,
			"ddpm_steps":          30.0,
			"disable_prefill":     false,
			"voice_folder_type":   "default",
			"custom_folder_path":  "",
			"output_folder_type":  "default",
			"custom_output_path":  "",
			"texts_folder_type":   "default",
			"custom_texts_path":   "",
			"output_directory":    "",
			"voice_directory":     "",
			"ollama_url":          "http://localhost:11434",
			"ollama_model":        "llama3.2",
			"last_text_input":     "",
			"last_custom_name":    "",
			"last_race_session":   "",
			"audio_output_folder": "",
			"texts_output_folder": "",
		},
	}
	return s
}

func Load() (*Store, error) {
	exePath, err := os.Executable()
	if err != nil {
		return nil, err
	}
	dir := filepath.Dir(exePath)
	path := filepath.Join(dir, "frontend_config.json")

	// Also check working directory
	if _, err := os.Stat(path); os.IsNotExist(err) {
		wd, _ := os.Getwd()
		path = filepath.Join(wd, "frontend_config.json")
	}

	s := Default()
	s.path = path

	raw, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			// No config yet — use defaults and set path for future saves
			return s, nil
		}
		return nil, err
	}

	var data map[string]any
	if err := json.Unmarshal(raw, &data); err != nil {
		return nil, err
	}

	// Merge loaded data over defaults
	for k, v := range data {
		s.data[k] = v
	}

	return s, nil
}

func (s *Store) Get() map[string]any {
	s.mu.RLock()
	defer s.mu.RUnlock()
	cp := make(map[string]any, len(s.data))
	for k, v := range s.data {
		cp[k] = v
	}
	return cp
}

func (s *Store) Patch(updates map[string]any) (map[string]any, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for k, v := range updates {
		if v == nil {
			continue
		}
		s.data[k] = v
	}
	if err := s.persist(); err != nil {
		return nil, err
	}
	cp := make(map[string]any, len(s.data))
	for k, v := range s.data {
		cp[k] = v
	}
	return cp, nil
}

func (s *Store) GetString(key string) string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	v, ok := s.data[key]
	if !ok {
		return ""
	}
	str, _ := v.(string)
	return str
}

func (s *Store) GetFloat(key string) float64 {
	s.mu.RLock()
	defer s.mu.RUnlock()
	v, ok := s.data[key]
	if !ok {
		return 0
	}
	f, _ := v.(float64)
	return f
}

func (s *Store) GetBool(key string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	v, ok := s.data[key]
	if !ok {
		return false
	}
	b, _ := v.(bool)
	return b
}

func (s *Store) persist() error {
	if s.path == "" {
		return nil
	}
	raw, err := json.MarshalIndent(s.data, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.path, raw, 0644)
}
