package server_test

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"truevoice/internal/config"
	"truevoice/internal/server"
)

// helper: create a temporary config dir and return a server + test HTTP server.
func setupTestServer(t *testing.T) (*httptest.Server, func()) {
	t.Helper()

	// Use default config (no file on disk needed)
	cfg := config.Default()
	srv := server.New(cfg)
	ts := httptest.NewServer(srv.Router())

	cleanup := func() {
		ts.Close()
		srv.Shutdown()
	}

	return ts, cleanup
}

func getJSON(t *testing.T, ts *httptest.Server, path string) (int, map[string]any) {
	t.Helper()
	resp, err := http.Get(ts.URL + path)
	if err != nil {
		t.Fatalf("GET %s failed: %v", path, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var result map[string]any
	_ = json.Unmarshal(body, &result)
	return resp.StatusCode, result
}

func getJSONArray(t *testing.T, ts *httptest.Server, path string) (int, []any) {
	t.Helper()
	resp, err := http.Get(ts.URL + path)
	if err != nil {
		t.Fatalf("GET %s failed: %v", path, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var result []any
	_ = json.Unmarshal(body, &result)
	return resp.StatusCode, result
}

func postJSON(t *testing.T, ts *httptest.Server, path string, payload any) (int, map[string]any) {
	t.Helper()
	data, _ := json.Marshal(payload)
	resp, err := http.Post(ts.URL+path, "application/json", bytes.NewReader(data))
	if err != nil {
		t.Fatalf("POST %s failed: %v", path, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var result map[string]any
	_ = json.Unmarshal(body, &result)
	return resp.StatusCode, result
}

func putJSON(t *testing.T, ts *httptest.Server, path string, payload any) (int, map[string]any) {
	t.Helper()
	data, _ := json.Marshal(payload)
	req, _ := http.NewRequest(http.MethodPut, ts.URL+path, bytes.NewReader(data))
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("PUT %s failed: %v", path, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var result map[string]any
	_ = json.Unmarshal(body, &result)
	return resp.StatusCode, result
}

func doDelete(t *testing.T, ts *httptest.Server, path string) (int, map[string]any) {
	t.Helper()
	req, _ := http.NewRequest(http.MethodDelete, ts.URL+path, nil)
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("DELETE %s failed: %v", path, err)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var result map[string]any
	_ = json.Unmarshal(body, &result)
	return resp.StatusCode, result
}

// ── E2E Tests ──────────────────────────────────────────────────────

func TestE2E_HealthCheck(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	code, body := getJSON(t, ts, "/")
	if code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}
	if body["status"] != "ok" {
		t.Fatalf("expected status=ok, got %v", body["status"])
	}
	if body["service"] != "TrueVoice API" {
		t.Fatalf("expected service=TrueVoice API, got %v", body["service"])
	}
}

func TestE2E_Models(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	code, body := getJSONArray(t, ts, "/models")
	if code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}
	if len(body) < 1 {
		t.Fatal("expected at least 1 model")
	}
	first := body[0].(map[string]any)
	if _, ok := first["id"]; !ok {
		t.Fatal("model should have 'id' field")
	}
}

func TestE2E_Config_GetPut(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	// GET initial config
	code, _ := getJSON(t, ts, "/config")
	if code != 200 {
		t.Fatalf("GET /config: expected 200, got %d", code)
	}

	// PUT a key
	code, body := putJSON(t, ts, "/config", map[string]any{
		"selected_voice": "test_voice",
	})
	if code != 200 {
		t.Fatalf("PUT /config: expected 200, got %d", code)
	}
	if body["selected_voice"] != "test_voice" {
		t.Fatalf("expected selected_voice=test_voice, got %v", body["selected_voice"])
	}

	// GET again to verify persistence
	code, body = getJSON(t, ts, "/config")
	if code != 200 {
		t.Fatalf("GET /config after PUT: expected 200, got %d", code)
	}
	if body["selected_voice"] != "test_voice" {
		t.Fatalf("config not persisted: expected test_voice, got %v", body["selected_voice"])
	}
}

func TestE2E_Voices_ListEmpty(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	code, body := getJSONArray(t, ts, "/voices")
	if code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}
	// Can be empty or contain voices from the default directory
	_ = body
}

func TestE2E_Outputs_ListEmpty(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	code, body := getJSONArray(t, ts, "/outputs")
	if code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}
	_ = body
}

func TestE2E_CleanupTemp(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	code, body := postJSON(t, ts, "/cleanup_temp", nil)
	if code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}
	// Response is {"deleted": N}
	if _, ok := body["deleted"]; !ok {
		t.Fatalf("expected 'deleted' key, got %v", body)
	}
}

func TestE2E_Contexts_CRUD(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	// List contexts
	code, body := getJSON(t, ts, "/contexts")
	if code != 200 {
		t.Fatalf("GET /contexts: expected 200, got %d", code)
	}
	if _, ok := body["contexts"]; !ok {
		t.Fatal("expected 'contexts' key in response")
	}

	// Get state
	code, body = getJSON(t, ts, "/contexts/state")
	if code != 200 {
		t.Fatalf("GET /contexts/state: expected 200, got %d", code)
	}

	// Save a new context
	code, body = postJSON(t, ts, "/contexts/save", map[string]any{
		"name":        "test_context",
		"intro_text":  "Intro de prueba",
		"events_text": "Eventos de prueba",
	})
	if code != 200 {
		t.Fatalf("POST /contexts/save: expected 200, got %d, body: %v", code, body)
	}
	ctx := body["context"].(map[string]any)
	if ctx["name"] != "test_context" {
		t.Fatalf("expected name=test_context, got %v", ctx["name"])
	}
	state := body["state"].(map[string]any)
	if state["in_use_name"] != "test_context" {
		t.Fatalf("expected in_use_name=test_context, got %v", state["in_use_name"])
	}

	// Get the context
	code, body = getJSON(t, ts, "/contexts/test_context")
	if code != 200 {
		t.Fatalf("GET /contexts/test_context: expected 200, got %d", code)
	}
	if body["name"] != "test_context" {
		t.Fatalf("expected name=test_context, got %v", body["name"])
	}

	// Load context
	code, body = postJSON(t, ts, "/contexts/load/test_context", nil)
	if code != 200 {
		t.Fatalf("POST /contexts/load/test_context: expected 200, got %d", code)
	}
	if body["in_use_name"] != "test_context" {
		t.Fatalf("expected in_use_name=test_context, got %v", body["in_use_name"])
	}

	// List contexts should include it
	code, body = getJSON(t, ts, "/contexts")
	if code != 200 {
		t.Fatalf("GET /contexts after save: expected 200, got %d", code)
	}
	ctxList := body["contexts"].([]any)
	found := false
	for _, c := range ctxList {
		cm := c.(map[string]any)
		if cm["name"] == "test_context" {
			found = true
			break
		}
	}
	if !found {
		t.Fatal("test_context not found in contexts list")
	}

	// Delete context
	code, body = doDelete(t, ts, "/contexts/test_context")
	if code != 200 {
		t.Fatalf("DELETE /contexts/test_context: expected 200, got %d", code)
	}
	if body["status"] != "deleted" {
		t.Fatalf("expected status=deleted, got %v", body["status"])
	}

	// Verify context is gone
	code, _ = getJSON(t, ts, "/contexts/test_context")
	if code != 404 {
		t.Fatalf("expected 404 after delete, got %d", code)
	}
}

func TestE2E_Contexts_SaveBadRequest(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	// Missing name
	code, body := postJSON(t, ts, "/contexts/save", map[string]any{
		"name":        "",
		"intro_text":  "something",
		"events_text": "something",
	})
	if code != 400 {
		t.Fatalf("expected 400 for empty name, got %d, body: %v", code, body)
	}
}

func TestE2E_Contexts_SaveDuplicateAutoIncrement(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	baseName := "duplicado_" + time.Now().Format("150405.000000000")

	code, body := postJSON(t, ts, "/contexts/save", map[string]any{
		"name":        baseName,
		"intro_text":  "uno",
		"events_text": "uno",
	})
	if code != 200 {
		t.Fatalf("expected 200 on first save, got %d, body: %v", code, body)
	}

	code, body = postJSON(t, ts, "/contexts/save", map[string]any{
		"name":        baseName,
		"intro_text":  "dos",
		"events_text": "dos",
	})
	if code != 200 {
		t.Fatalf("expected 200 on duplicate save, got %d, body: %v", code, body)
	}

	ctx := body["context"].(map[string]any)
	expectedSecond := baseName + " (1)"
	if ctx["name"] != expectedSecond {
		t.Fatalf("expected auto-incremented name %s, got %v", expectedSecond, ctx["name"])
	}

	code, body = postJSON(t, ts, "/contexts/save", map[string]any{
		"name":        baseName,
		"intro_text":  "tres",
		"events_text": "tres",
	})
	if code != 200 {
		t.Fatalf("expected 200 on second duplicate save, got %d, body: %v", code, body)
	}

	ctx = body["context"].(map[string]any)
	expectedThird := baseName + " (2)"
	if ctx["name"] != expectedThird {
		t.Fatalf("expected auto-incremented name %s, got %v", expectedThird, ctx["name"])
	}
}

func TestE2E_RaceSessions_ListEmpty(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	code, body := getJSONArray(t, ts, "/race/sessions")
	if code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}
	_ = body
}

func TestE2E_SetupStatus(t *testing.T) {
	ts, cleanup := setupTestServer(t)
	defer cleanup()

	code, body := getJSON(t, ts, "/setup/status")
	if code != 200 {
		t.Fatalf("expected 200, got %d", code)
	}
	// Should have "ready" field
	if _, ok := body["ready"]; !ok {
		t.Fatal("expected 'ready' field in setup status")
	}
}
