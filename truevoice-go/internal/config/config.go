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

	// Advanced generation parameters
	VoiceSpeedFactor float64 `json:"voice_speed_factor"`
	MaxWordsPerChunk int     `json:"max_words_per_chunk"`
	QuantizeLLM      string  `json:"quantize_llm"`
	Temperature      float64 `json:"temperature"`
	TopP             float64 `json:"top_p"`
	UseSampling      bool    `json:"use_sampling"`

	// Narrator system & custom models
	Narrators    []NarratorConfig `json:"narrators"`
	CustomModels []CustomModel    `json:"custom_models"`

	// Active LoRA for generation
	ActiveLoRAPath string `json:"active_lora_path"`

	// Extra holds unknown keys for forward compatibility.
	Extra map[string]any `json:"-"`
}

// NarratorConfig defines a named narrator with a voice and speaker slot.
type NarratorConfig struct {
	Key         string `json:"key"`
	Name        string `json:"name"`
	Voice       string `json:"voice"`
	IsPrincipal bool   `json:"is_principal"`
	SpeakerSlot int    `json:"speaker_slot"`
}

// CustomModel is a user-registered VibeVoice model (HF id or local path).
type CustomModel struct {
	ID   string `json:"id"`
	Name string `json:"name"`
	Size string `json:"size"`
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
			"voice_speed_factor":  1.0,
			"max_words_per_chunk": 250.0,
			"quantize_llm":        "none",
			"temperature":         0.95,
			"top_p":               0.95,
			"use_sampling":        false,
			"narrators":           []NarratorConfig{},
			"custom_models":       []CustomModel{},
			"active_lora_path":    "",
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

// Narrators returns the configured narrator list (typed copy).
func (s *Store) Narrators() []NarratorConfig {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return decodeNarrators(s.data["narrators"])
}

// SetNarrators replaces the narrator list and persists.
func (s *Store) SetNarrators(list []NarratorConfig) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.data["narrators"] = list
	return s.persist()
}

// CustomModels returns the configured custom-models list (typed copy).
func (s *Store) CustomModels() []CustomModel {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return decodeCustomModels(s.data["custom_models"])
}

// SetCustomModels replaces the custom models list and persists.
func (s *Store) SetCustomModels(list []CustomModel) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.data["custom_models"] = list
	return s.persist()
}

func decodeNarrators(raw any) []NarratorConfig {
	if raw == nil {
		return []NarratorConfig{}
	}
	// Already typed
	if typed, ok := raw.([]NarratorConfig); ok {
		out := make([]NarratorConfig, len(typed))
		copy(out, typed)
		return out
	}
	// From JSON: []any of map[string]any
	if items, ok := raw.([]any); ok {
		out := make([]NarratorConfig, 0, len(items))
		for _, it := range items {
			m, ok := it.(map[string]any)
			if !ok {
				continue
			}
			n := NarratorConfig{}
			if v, ok := m["key"].(string); ok {
				n.Key = v
			}
			if v, ok := m["name"].(string); ok {
				n.Name = v
			}
			if v, ok := m["voice"].(string); ok {
				n.Voice = v
			}
			if v, ok := m["is_principal"].(bool); ok {
				n.IsPrincipal = v
			}
			if v, ok := m["speaker_slot"].(float64); ok {
				n.SpeakerSlot = int(v)
			}
			out = append(out, n)
		}
		return out
	}
	return []NarratorConfig{}
}

func decodeCustomModels(raw any) []CustomModel {
	if raw == nil {
		return []CustomModel{}
	}
	if typed, ok := raw.([]CustomModel); ok {
		out := make([]CustomModel, len(typed))
		copy(out, typed)
		return out
	}
	if items, ok := raw.([]any); ok {
		out := make([]CustomModel, 0, len(items))
		for _, it := range items {
			m, ok := it.(map[string]any)
			if !ok {
				continue
			}
			cm := CustomModel{}
			if v, ok := m["id"].(string); ok {
				cm.ID = v
			}
			if v, ok := m["name"].(string); ok {
				cm.Name = v
			}
			if v, ok := m["size"].(string); ok {
				cm.Size = v
			}
			out = append(out, cm)
		}
		return out
	}
	return []CustomModel{}
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
