package contexts

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/url"
	"strings"
)

func (m *Manager) ListHandler(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{"contexts": m.List()})
}

func (m *Manager) StateHandler(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, m.GetInUseState())
}

func (m *Manager) GetHandler(w http.ResponseWriter, r *http.Request) {
	name := extractPathParam(r.URL.Path, "contexts")
	decoded, _ := url.PathUnescape(name)
	ctx, err := m.Get(decoded)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			writeError(w, http.StatusNotFound, "Context not found")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, ctx)
}

func (m *Manager) SaveHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name       string `json:"name"`
		IntroText  string `json:"intro_text"`
		EventsText string `json:"events_text"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	ctx, state, err := m.SaveAndSetInUse(req.Name, req.IntroText, req.EventsText)
	if err != nil {
		if strings.Contains(strings.ToLower(err.Error()), "name is required") {
			writeError(w, http.StatusBadRequest, "Context name is required")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"context": ctx,
		"state":   state,
	})
}

func (m *Manager) LoadHandler(w http.ResponseWriter, r *http.Request) {
	name := extractPathParam(r.URL.Path, "load")
	decoded, _ := url.PathUnescape(name)
	state, err := m.SetInUse(decoded)
	if err != nil {
		if errors.Is(err, ErrNotFound) {
			writeError(w, http.StatusNotFound, "Context not found")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, state)
}

func (m *Manager) DeleteHandler(w http.ResponseWriter, r *http.Request) {
	name := extractPathParam(r.URL.Path, "contexts")
	decoded, _ := url.PathUnescape(name)
	if err := m.Delete(decoded); err != nil {
		if errors.Is(err, ErrNotFound) {
			writeError(w, http.StatusNotFound, "Context not found")
			return
		}
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "deleted"})
}

func extractPathParam(urlPath, after string) string {
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

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"detail": msg})
}
