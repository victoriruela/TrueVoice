package contexts

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"truevoice/internal/config"
)

var (
	ErrConflict = errors.New("context name already exists")
	ErrNotFound = errors.New("context not found")
)

const (
	legacyContextName = "Contexto F1 legado"
)

const (
	defaultIntroTemplate  = "Eres el comentarista oficial de una carrera de Formula 1. Presenta la carrera de forma emocionante y natural. Narra la parrilla de salida empezando por el primero. Para los tres primeros pilotos, haz una apreciacion graciosa y positiva en tono de broma amigable. Para el resto de pilotos, menciona su posicion de salida. IMPORTANTE: Todos los numeros deben escribirse con palabras y no debes usar digitos numericos. Responde solo con el texto de presentacion, sin titulos ni explicaciones adicionales."
	defaultEventsTemplate = "Eres un comentarista deportivo de Formula 1 apasionado y dinamico. Genera una sola frase corta y emocionante para cada evento, con variedad y lenguaje natural. Debes mantener continuidad narrativa respecto a la memoria previa y evitar contradicciones o repeticiones. IMPORTANTE: Todos los numeros deben escribirse con palabras y no debes usar digitos numericos. Responde solo con la frase, sin comillas ni explicaciones adicionales."
)

type ContextTemplate struct {
	Name       string `json:"name"`
	IntroText  string `json:"intro_text"`
	EventsText string `json:"events_text"`
	CreatedAt  string `json:"created_at"`
	UpdatedAt  string `json:"updated_at"`
}

type State struct {
	InUseName       string `json:"in_use_name"`
	InUseIntroText  string `json:"in_use_intro_text"`
	InUseEventsText string `json:"in_use_events_text"`
}

type Manager struct {
	cfg  *config.Store
	mu   sync.RWMutex
	data map[string]ContextTemplate
}

func NewManager(cfg *config.Store) *Manager {
	m := &Manager{cfg: cfg, data: map[string]ContextTemplate{}}
	_ = m.loadFromDisk()
	_ = m.ensureLegacyContext()
	return m
}

func (m *Manager) introTemplate() string {
	return defaultIntroTemplate
}

func (m *Manager) eventsTemplate() string {
	return defaultEventsTemplate
}

func (m *Manager) contextsDir() string {
	wd, _ := os.Getwd()
	d := filepath.Join(wd, "contexts")
	_ = os.MkdirAll(d, 0755)
	return d
}

func (m *Manager) storagePath() string {
	return filepath.Join(m.contextsDir(), "contexts.json")
}

func normalizeName(name string) string {
	return strings.TrimSpace(name)
}

func deduplicateName(name string, existing map[string]ContextTemplate) string {
	base := normalizeName(name)
	if base == "" {
		return ""
	}
	if _, exists := existing[base]; !exists {
		return base
	}
	for i := 1; ; i++ {
		candidate := fmt.Sprintf("%s (%d)", base, i)
		if _, exists := existing[candidate]; !exists {
			return candidate
		}
	}
}

func nowISO() string {
	return time.Now().UTC().Format(time.RFC3339)
}

func (m *Manager) loadFromDisk() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	raw, err := os.ReadFile(m.storagePath())
	if err != nil {
		if os.IsNotExist(err) {
			m.data = map[string]ContextTemplate{}
			return nil
		}
		return err
	}

	var stored []ContextTemplate
	if err := json.Unmarshal(raw, &stored); err != nil {
		return err
	}

	next := make(map[string]ContextTemplate, len(stored))
	for _, ctx := range stored {
		name := normalizeName(ctx.Name)
		if name == "" {
			continue
		}
		ctx.Name = name
		next[name] = ctx
	}
	m.data = next
	return nil
}

func (m *Manager) persistLocked() error {
	list := make([]ContextTemplate, 0, len(m.data))
	for _, ctx := range m.data {
		list = append(list, ctx)
	}
	sort.Slice(list, func(i, j int) bool {
		return strings.ToLower(list[i].Name) < strings.ToLower(list[j].Name)
	})

	raw, err := json.MarshalIndent(list, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(m.storagePath(), raw, 0644)
}

func (m *Manager) ensureLegacyContext() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if _, ok := m.data[legacyContextName]; !ok {
		ts := nowISO()
		m.data[legacyContextName] = ContextTemplate{
			Name:       legacyContextName,
			IntroText:  m.introTemplate(),
			EventsText: m.eventsTemplate(),
			CreatedAt:  ts,
			UpdatedAt:  ts,
		}
		if err := m.persistLocked(); err != nil {
			return err
		}
	}

	if m.cfg.GetString("context_in_use_intro_text") == "" || m.cfg.GetString("context_in_use_events_text") == "" {
		ctx := m.data[legacyContextName]
		_, _ = m.cfg.Patch(map[string]any{
			"context_in_use_name":        ctx.Name,
			"context_in_use_intro_text":  ctx.IntroText,
			"context_in_use_events_text": ctx.EventsText,
		})
	}

	return nil
}

func (m *Manager) List() []ContextTemplate {
	m.mu.RLock()
	defer m.mu.RUnlock()
	list := make([]ContextTemplate, 0, len(m.data))
	for _, ctx := range m.data {
		list = append(list, ctx)
	}
	sort.Slice(list, func(i, j int) bool {
		return strings.ToLower(list[i].Name) < strings.ToLower(list[j].Name)
	})
	return list
}

func (m *Manager) Get(name string) (ContextTemplate, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	key := normalizeName(name)
	ctx, ok := m.data[key]
	if !ok {
		return ContextTemplate{}, ErrNotFound
	}
	return ctx, nil
}

func (m *Manager) SaveNew(name, introText, eventsText string) (ContextTemplate, error) {
	key := normalizeName(name)
	if key == "" {
		return ContextTemplate{}, errors.New("name is required")
	}

	m.mu.Lock()
	defer m.mu.Unlock()
	key = deduplicateName(key, m.data)
	ts := nowISO()
	ctx := ContextTemplate{
		Name:       key,
		IntroText:  strings.TrimSpace(introText),
		EventsText: strings.TrimSpace(eventsText),
		CreatedAt:  ts,
		UpdatedAt:  ts,
	}
	m.data[key] = ctx
	if err := m.persistLocked(); err != nil {
		return ContextTemplate{}, err
	}
	return ctx, nil
}

func (m *Manager) Delete(name string) error {
	key := normalizeName(name)
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.data[key]; !ok {
		return ErrNotFound
	}
	delete(m.data, key)
	if err := m.persistLocked(); err != nil {
		return err
	}

	if m.cfg.GetString("context_in_use_name") == key {
		_, _ = m.cfg.Patch(map[string]any{
			"context_in_use_name":        "",
			"context_in_use_intro_text":  "",
			"context_in_use_events_text": "",
		})
	}
	return nil
}

func (m *Manager) SetInUse(name string) (State, error) {
	ctx, err := m.Get(name)
	if err != nil {
		return State{}, err
	}
	_, err = m.cfg.Patch(map[string]any{
		"context_in_use_name":        ctx.Name,
		"context_in_use_intro_text":  ctx.IntroText,
		"context_in_use_events_text": ctx.EventsText,
	})
	if err != nil {
		return State{}, err
	}
	return State{
		InUseName:       ctx.Name,
		InUseIntroText:  ctx.IntroText,
		InUseEventsText: ctx.EventsText,
	}, nil
}

func (m *Manager) SaveAndSetInUse(name, introText, eventsText string) (ContextTemplate, State, error) {
	ctx, err := m.SaveNew(name, introText, eventsText)
	if err != nil {
		return ContextTemplate{}, State{}, err
	}
	state, err := m.SetInUse(ctx.Name)
	if err != nil {
		return ContextTemplate{}, State{}, err
	}
	return ctx, state, nil
}

func (m *Manager) GetInUseState() State {
	return State{
		InUseName:       m.cfg.GetString("context_in_use_name"),
		InUseIntroText:  m.cfg.GetString("context_in_use_intro_text"),
		InUseEventsText: m.cfg.GetString("context_in_use_events_text"),
	}
}
