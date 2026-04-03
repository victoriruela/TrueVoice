package server

import (
	"encoding/json"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"

	"truevoice/internal/config"
	"truevoice/internal/contexts"
	"truevoice/internal/generation"
	"truevoice/internal/race"
	"truevoice/internal/voices"
)

// Server holds all shared state and provides the HTTP router.
type Server struct {
	cfg      *config.Store
	gen      *generation.Manager
	voices   *voices.Manager
	race     *race.Manager
	contexts *contexts.Manager
	router   chi.Router
}

func New(cfg *config.Store) *Server {
	s := &Server{
		cfg:      cfg,
		gen:      generation.NewManager(cfg),
		voices:   voices.NewManager(cfg),
		race:     race.NewManager(cfg),
		contexts: contexts.NewManager(cfg),
	}
	s.router = s.buildRouter()
	return s
}

func (s *Server) Router() http.Handler {
	return s.router
}

func (s *Server) Shutdown() {
	s.gen.CancelAll()
}

func (s *Server) BootstrapRuntime() error {
	return s.gen.BootstrapRuntime()
}

func (s *Server) buildRouter() chi.Router {
	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"*"},
		AllowCredentials: true,
		MaxAge:           300,
	}))

	// Health
	r.Get("/", s.healthCheck)

	// Config
	r.Get("/config", s.getConfig)
	r.Put("/config", s.putConfig)

	// Voices
	r.Get("/voices", s.voices.ListHandler)
	r.Post("/voices/upload", s.voices.UploadHandler)
	r.Delete("/voices/{name}", s.voices.DeleteHandler)

	// Models
	r.Get("/models", s.listModels)

	// Generation
	r.Post("/generate", s.gen.GenerateHandler)
	r.Get("/audio/{audioID}", s.gen.AudioHandler)
	r.Get("/progress/{progressID}", s.gen.ProgressHandler)
	r.Post("/cancel/{progressID}", s.gen.CancelHandler)
	r.Post("/cancel_all", s.gen.CancelAllHandler)
	r.Post("/confirm_save", s.gen.ConfirmSaveHandler)

	// Outputs
	r.Get("/outputs", s.gen.ListOutputsHandler)
	r.Delete("/outputs/delete", s.gen.DeleteOutputsHandler)
	r.Post("/cleanup_temp", s.gen.CleanupTempHandler)

	// Ollama proxy
	r.Get("/ollama/models", s.ollamaModels)
	r.Post("/ollama/generate", s.ollamaGenerate)

	// Directory browse
	r.Get("/browse/drives", s.browseDrives)
	r.Get("/browse/folders", s.browseFolders)

	// Contexts
	r.Get("/contexts", s.contexts.ListHandler)
	r.Get("/contexts/state", s.contexts.StateHandler)
	r.Get("/contexts/{name}", s.contexts.GetHandler)
	r.Post("/contexts/save", s.contexts.SaveHandler)
	r.Post("/contexts/load/{name}", s.contexts.LoadHandler)
	r.Delete("/contexts/{name}", s.contexts.DeleteHandler)

	// Race
	r.Post("/race/parse", s.race.ParseHandler)
	r.Post("/race/intro", s.race.IntroHandler)
	r.Post("/race/descriptions", s.race.DescriptionsHandler)
	r.Get("/race/sessions", s.race.ListSessionsHandler)
	r.Get("/race/sessions/{name}", s.race.GetSessionHandler)
	r.Post("/race/sessions/{name}", s.race.SaveSessionHandler)
	r.Delete("/race/sessions/{name}", s.race.DeleteSessionHandler)
	r.Post("/race/csv", s.race.CSVExportHandler)
	r.Get("/race/sessions/{name}/csv", s.race.CSVHandler)

	// Setup / sidecar status
	r.Get("/setup/status", s.gen.SetupStatusHandler)
	r.Post("/setup/bootstrap", s.gen.SetupBootstrapHandler)

	// Static files (Expo web build) — served last as catch-all
	r.Handle("/*", s.staticHandler())

	return r
}

func (s *Server) healthCheck(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{
		"status":  "ok",
		"service": "TrueVoice API",
		"version": "2.0.0",
	})
}

func (s *Server) getConfig(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, s.cfg.Get())
}

func (s *Server) putConfig(w http.ResponseWriter, r *http.Request) {
	var patch map[string]any
	if err := json.NewDecoder(r.Body).Decode(&patch); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	result, err := s.cfg.Patch(patch)
	if err != nil {
		writeError(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"detail": msg})
}
