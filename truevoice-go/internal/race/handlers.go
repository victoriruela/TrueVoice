package race

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/tealeg/xlsx/v3"

	"truevoice/internal/config"
)

type Manager struct {
	cfg *config.Store
}

func NewManager(cfg *config.Store) *Manager {
	return &Manager{cfg: cfg}
}

func (m *Manager) sessionsDir() string {
	dir, _ := os.Getwd()
	d := filepath.Join(dir, "race_sessions")
	os.MkdirAll(d, 0755)
	return d
}

// ── POST /race/parse ───────────────────────────────────────────────

func (m *Manager) ParseHandler(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(50 << 20); err != nil {
		writeError(w, http.StatusBadRequest, "Invalid form data")
		return
	}

	file, _, err := r.FormFile("file")
	if err != nil {
		writeError(w, http.StatusBadRequest, "file field is required")
		return
	}
	defer file.Close()

	data, err := io.ReadAll(file)
	if err != nil {
		writeError(w, http.StatusBadRequest, "Cannot read file")
		return
	}

	xmlStr := string(data)
	header := ParseRaceHeader(xmlStr)
	events := ParseRaceFile(xmlStr)

	writeJSON(w, http.StatusOK, map[string]any{
		"header": header,
		"events": events,
	})
}

// ── POST /race/intro ───────────────────────────────────────────────

func (m *Manager) IntroHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Header RaceHeader `json:"header"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	ollamaURL, ollamaModel := m.resolveOllamaConfig(r)

	h := req.Header

	// Build grid description
	top3 := h.GridOrder
	if len(top3) > 3 {
		top3 = h.GridOrder[:3]
	}
	var top3Parts []string
	for i, name := range top3 {
		top3Parts = append(top3Parts, fmt.Sprintf("%d. %s", i+1, name))
	}
	top3Str := strings.Join(top3Parts, ", ")

	var restParts []string
	if len(h.GridOrder) > 3 {
		for i, name := range h.GridOrder[3:] {
			restParts = append(restParts, fmt.Sprintf("%d. %s", i+4, name))
		}
	}

	gridSection := fmt.Sprintf("Los tres primeros en parrilla son: %s.", top3Str)
	if len(restParts) > 0 {
		gridSection += fmt.Sprintf(" El resto de pilotos salen en estas posiciones: %s.", strings.Join(restParts, ", "))
	}

	prompt := fmt.Sprintf(
		"Eres el comentarista oficial de una carrera de Fórmula 1. "+
			"Presenta la carrera de forma emocionante y natural. "+
			"La carrera se celebra en el circuito '%s', "+
			"con una longitud de %.0f metros por vuelta, "+
			"a lo largo de %d vueltas. "+
			"Participan %d pilotos. "+
			"%s "+
			"Narra la parrilla de salida empezando por el primero. "+
			"Para los 3 primeros pilotos (%s), haz una apreciación graciosa y positiva (en tono de broma amigable) sobre cada uno. "+
			"Para el resto de pilotos, menciona únicamente su posición de salida. "+
			"IMPORTANTE: Todos los números deben escribirse con palabras (ej. 'uno' en lugar de '1'). NO uses dígitos numéricos. "+
			"Responde SOLO con el texto de presentación, sin títulos ni explicaciones adicionales.",
		h.TrackEvent, h.TrackLength, h.RaceLaps, h.NumDrivers, gridSection, top3Str,
	)

	text := callOllama(ollamaURL, ollamaModel, prompt, 0.85, 42)
	writeJSON(w, http.StatusOK, map[string]string{"intro_text": text})
}

// ── POST /race/descriptions ────────────────────────────────────────

func (m *Manager) DescriptionsHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Events []RaceEvent `json:"events"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	ollamaURL, ollamaModel := m.resolveOllamaConfig(r)

	typeHints := map[int]string{
		1: "adelantamiento en carrera de Fórmula 1",
		2: "choque o contacto entre dos pilotos en carrera de Fórmula 1",
		3: "choque de un piloto contra el muro o barrera en carrera de Fórmula 1",
		4: "penalización (STOP and GO o Drive Through) impuesta a un piloto",
		5: "entrada a boxes de un piloto",
	}

	var usedDescs []string

	for i := range req.Events {
		ev := &req.Events[i]
		hint := typeHints[ev.EventType]
		if hint == "" {
			hint = "carrera"
		}

		avoidHint := ""
		if len(usedDescs) > 0 {
			lastFew := usedDescs
			if len(lastFew) > 5 {
				lastFew = lastFew[len(lastFew)-5:]
			}
			avoidHint = fmt.Sprintf("\nEvita usar frases similares a estas descripciones anteriores: %s",
				strings.Join(lastFew, "; "))
		}

		overtakeHint := ""
		if ev.EventType == 1 && strings.Contains(ev.Summary, " adelanta a ") {
			driverA := strings.Split(ev.Summary, " adelanta a ")[0]
			prevCount := 0
			for j := 0; j < i; j++ {
				if req.Events[j].EventType == 1 && strings.HasPrefix(req.Events[j].Summary, driverA+" adelanta a ") {
					prevCount++
				}
			}
			if prevCount >= 3 {
				overtakeHint = fmt.Sprintf(" Menciona que este piloto ya lleva %d adelantamientos en la carrera.", prevCount)
			}
		}

		prompt := fmt.Sprintf(
			"Eres un comentarista deportivo de Fórmula 1 apasionado y dinámico. "+
				"Genera UNA SOLA frase corta (máximo 25 palabras) y emocionante describiendo este evento de %s: "+
				"'%s' en la vuelta %d. "+
				"La descripción debe ser variada, natural y diferente a las anteriores.%s "+
				"IMPORTANTE: Todos los números deben escribirse con palabras (ej. 'uno' en lugar de '1'). NO uses dígitos numéricos. "+
				"Responde SOLO con la frase, sin comillas ni explicaciones adicionales.%s",
			hint, ev.Summary, ev.Lap, overtakeHint, avoidHint,
		)

		seed := i*37 + 13
		desc := callOllama(ollamaURL, ollamaModel, prompt, 0.9, seed)
		if desc == "" {
			desc = ev.Summary
		}
		ev.Description = desc
		usedDescs = append(usedDescs, desc)
	}

	writeJSON(w, http.StatusOK, map[string]any{"events": req.Events})
}

// ── Sessions CRUD ──────────────────────────────────────────────────

func (m *Manager) ListSessionsHandler(w http.ResponseWriter, r *http.Request) {
	dir := m.sessionsDir()
	entries, _ := os.ReadDir(dir)

	type sessionInfo struct {
		Name     string  `json:"name"`
		Filename string  `json:"filename"`
		Size     int64   `json:"size"`
		Modified float64 `json:"modified"`
	}

	var sessions []sessionInfo
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		info, _ := e.Info()
		name := strings.TrimSuffix(e.Name(), ".json")
		sessions = append(sessions, sessionInfo{
			Name:     name,
			Filename: e.Name(),
			Size:     info.Size(),
			Modified: float64(info.ModTime().Unix()),
		})
	}

	sort.Slice(sessions, func(i, j int) bool {
		return sessions[i].Modified > sessions[j].Modified
	})
	writeJSON(w, http.StatusOK, sessions)
}

func (m *Manager) GetSessionHandler(w http.ResponseWriter, r *http.Request) {
	name := extractPathParam(r.URL.Path, "sessions")
	decoded, _ := url.PathUnescape(name)
	path := filepath.Join(m.sessionsDir(), decoded+".json")

	data, err := os.ReadFile(path)
	if err != nil {
		writeError(w, http.StatusNotFound, "Session not found")
		return
	}

	var session RaceSession
	json.Unmarshal(data, &session)
	if session.EventAudios == nil {
		session.EventAudios = map[string]string{}
	}
	if session.HiddenEventIndices == nil {
		session.HiddenEventIndices = []int{}
	}
	if session.SelectedEventIndices == nil {
		session.SelectedEventIndices = []int{}
	}
	writeJSON(w, http.StatusOK, session)
}

func (m *Manager) SaveSessionHandler(w http.ResponseWriter, r *http.Request) {
	name := extractPathParam(r.URL.Path, "sessions")
	decoded, _ := url.PathUnescape(name)

	var session RaceSession
	if err := json.NewDecoder(r.Body).Decode(&session); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	data, _ := json.MarshalIndent(session, "", "  ")
	path := filepath.Join(m.sessionsDir(), decoded+".json")
	if err := os.WriteFile(path, data, 0644); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "saved", "name": decoded})
}

func (m *Manager) DeleteSessionHandler(w http.ResponseWriter, r *http.Request) {
	name := extractPathParam(r.URL.Path, "sessions")
	decoded, _ := url.PathUnescape(name)
	path := filepath.Join(m.sessionsDir(), decoded+".json")

	if err := os.Remove(path); err != nil {
		writeError(w, http.StatusNotFound, "Session not found")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "deleted"})
}

// ── Excel Export ───────────────────────────────────────────────────

func (m *Manager) ExcelHandler(w http.ResponseWriter, r *http.Request) {
	name := extractPathParam(r.URL.Path, "sessions")
	decoded, _ := url.PathUnescape(name)
	path := filepath.Join(m.sessionsDir(), decoded+".json")

	data, err := os.ReadFile(path)
	if err != nil {
		writeError(w, http.StatusNotFound, "Session not found")
		return
	}

	var session RaceSession
	json.Unmarshal(data, &session)

	xf := xlsx.NewFile()
	sheet, err := xf.AddSheet("Eventos")
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	headers := []string{"Vuelta", "Timestamp", "Tipo", "Resumen", "Descripción IA", "Audio"}
	headerRow := sheet.AddRow()
	for _, h := range headers {
		cell := headerRow.AddCell()
		cell.SetString(h)
	}

	for i, ev := range session.Events {
		audioID := session.EventAudios[fmt.Sprintf("%d", i)]
		row := sheet.AddRow()
		row.AddCell().SetInt(ev.Lap)
		row.AddCell().SetFloat(ev.Timestamp)
		row.AddCell().SetInt(ev.EventType)
		row.AddCell().SetString(ev.Summary)
		row.AddCell().SetString(ev.Description)
		row.AddCell().SetString(audioID)
	}

	w.Header().Set("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s.xlsx"`, decoded))
	if err := xf.Write(w); err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
}

// ── Ollama caller ──────────────────────────────────────────────────

func callOllama(ollamaURL, model, prompt string, temp float64, seed int) string {
	body := map[string]any{
		"model":  model,
		"prompt": prompt,
		"stream": false,
		"options": map[string]any{
			"temperature": temp,
			"top_p":       0.95,
			"seed":        seed,
		},
	}
	raw, _ := json.Marshal(body)

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Post(ollamaURL+"/api/generate", "application/json",
		strings.NewReader(string(raw)))
	if err != nil {
		return ""
	}
	defer resp.Body.Close()

	var result struct {
		Response string `json:"response"`
	}
	json.NewDecoder(resp.Body).Decode(&result)
	text := strings.TrimSpace(result.Response)
	text = strings.Trim(text, `"'`)
	return text
}

// ── Helpers ────────────────────────────────────────────────────────

func extractPathParam(urlPath, after string) string {
	// Extract the segment after "/{after}/" in the URL path
	parts := strings.Split(urlPath, "/"+after+"/")
	if len(parts) < 2 {
		return ""
	}
	// Remove trailing path segments (e.g. /excel)
	seg := parts[1]
	if idx := strings.Index(seg, "/"); idx >= 0 {
		seg = seg[:idx]
	}
	return seg
}

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"detail": msg})
}

func (m *Manager) resolveOllamaConfig(r *http.Request) (string, string) {
	ollamaURL := r.URL.Query().Get("ollama_url")
	if ollamaURL == "" {
		ollamaURL = m.cfg.GetString("ollama_url")
	}
	if ollamaURL == "" {
		ollamaURL = "http://localhost:11434"
	}

	ollamaModel := r.URL.Query().Get("ollama_model")
	if ollamaModel == "" {
		ollamaModel = m.cfg.GetString("ollama_model")
	}
	if ollamaModel == "" {
		ollamaModel = "llama3.2"
	}

	return ollamaURL, ollamaModel
}
