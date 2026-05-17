package training

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"

	"github.com/go-chi/chi/v5"
	"github.com/google/uuid"
)

// RegisterHandlers registers training endpoints
func (m *Manager) RegisterHandlers(r chi.Router) {
	r.Post("/training/upload", m.uploadHandler)
	r.Post("/training/validate", m.validateHandler)
	r.Post("/training/prepare", m.prepareHandler)
	r.Post("/training/start", m.startHandler)
	r.Get("/training/jobs", m.listJobsHandler)
	r.Get("/training/jobs/{job_id}", m.getJobHandler)
	r.Post("/training/jobs/{job_id}/cancel", m.cancelJobHandler)
	r.Get("/training/jobs/{job_id}/logs", m.logsHandler)
	r.Get("/training/loras", m.listLoRAsHandler)
	r.Delete("/training/loras/{name}", m.deleteLoRAHandler)
	r.Post("/training/clear-dataset", m.clearDatasetHandler)
	// Active LoRA endpoints
	r.Get("/training/loras/active", m.getActiveLoRAHandler)
	r.Post("/training/loras/active", m.setActiveLoRAHandler)
	r.Delete("/training/loras/active", m.clearActiveLoRAHandler)
	// Audio splitting + transcription
	r.Post("/training/split-audio", m.splitAudioHandler)
	r.Get("/training/split-progress/{job_id}", m.splitProgressHandler)
}

// uploadHandler handles file uploads (audio + transcript files)
func (m *Manager) uploadHandler(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(100 << 20); err != nil { // 100 MB max
		http.Error(w, "Failed to parse form", http.StatusBadRequest)
		return
	}

	sessionID := r.FormValue("session_id")
	if sessionID == "" {
		http.Error(w, "session_id required", http.StatusBadRequest)
		return
	}

	uploadDir := filepath.Join(projectRoot(), "training_data", sessionID)
	if err := os.MkdirAll(uploadDir, 0755); err != nil {
		http.Error(w, "Failed to create upload directory", http.StatusInternalServerError)
		return
	}

	files := r.MultipartForm.File["files"]
	uploaded := []string{}

	for _, fileHeader := range files {
		file, err := fileHeader.Open()
		if err != nil {
			continue
		}
		defer file.Close()

		// Sanitize filename
		filename := filepath.Base(fileHeader.Filename)
		destPath := filepath.Join(uploadDir, filename)

		dest, err := os.Create(destPath)
		if err != nil {
			continue
		}

		if _, err := io.Copy(dest, file); err != nil {
			dest.Close()
			continue
		}
		dest.Close()

		uploaded = append(uploaded, filename)
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"uploaded":   uploaded,
		"session_id": sessionID,
		"count":      len(uploaded),
	})
}

// validateHandler validates uploaded dataset
func (m *Manager) validateHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		SessionID string `json:"session_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	dataDir := filepath.Join(projectRoot(), "training_data", req.SessionID)
	files, err := ValidateDataset(dataDir)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	validCount := 0
	for _, f := range files {
		if f.Valid {
			validCount++
		}
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"files":   files,
		"total":   len(files),
		"valid":   validCount,
		"invalid": len(files) - validCount,
	})
}

// prepareHandler prepares dataset CSV and creates training config
func (m *Manager) prepareHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		SessionID           string  `json:"session_id"`
		LoRAName            string  `json:"lora_name"`
		ModelBase           string  `json:"model_base"`
		Epochs              int     `json:"epochs"`
		BatchSize           int     `json:"batch_size"`
		LearningRate        float64 `json:"learning_rate"`
		VoicePromptDropRate float64 `json:"voice_prompt_drop_rate"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	dataDir := filepath.Join(projectRoot(), "training_data", req.SessionID)
	files, err := ValidateDataset(dataDir)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	// Count valid files
	validFiles := []DatasetFile{}
	for _, f := range files {
		if f.Valid {
			validFiles = append(validFiles, f)
		}
	}

	if len(validFiles) == 0 {
		http.Error(w, "No valid audio-transcript pairs found", http.StatusBadRequest)
		return
	}

	// Prepare JSONL dataset file
	csvPath := filepath.Join(dataDir, "dataset.jsonl")
	if err := PrepareDatasetJSONL(validFiles, csvPath); err != nil {
		http.Error(w, fmt.Sprintf("Failed to create CSV: %v", err), http.StatusInternalServerError)
		return
	}

	// Create output directory
	outputDir := filepath.Join(projectRoot(), "loras", req.LoRAName)
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		http.Error(w, "Failed to create output directory", http.StatusInternalServerError)
		return
	}

	// Create training job
	config := TrainingConfig{
		LoRAName:            req.LoRAName,
		ModelBase:           req.ModelBase,
		DatasetPath:         csvPath,
		OutputDir:           outputDir,
		Epochs:              req.Epochs,
		BatchSize:           req.BatchSize,
		LearningRate:        req.LearningRate,
		VoicePromptDropRate: req.VoicePromptDropRate,
	}

	job, err := m.CreateJob(config)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	json.NewEncoder(w).Encode(map[string]interface{}{
		"job_id":       job.Config.JobID,
		"valid_files":  len(validFiles),
		"dataset_path": csvPath,
		"output_dir":   outputDir,
	})
}

// startHandler starts a training job
func (m *Manager) startHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		JobID string `json:"job_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	if err := m.StartTraining(req.JobID); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "started"})
}

// listJobsHandler lists all training jobs
func (m *Manager) listJobsHandler(w http.ResponseWriter, r *http.Request) {
	jobs := m.ListJobs()
	
	// Return safe representation (no internal fields)
	safeJobs := make([]map[string]interface{}, len(jobs))
	for i, job := range jobs {
		job.mu.RLock()
		safeJobs[i] = map[string]interface{}{
			"job_id":     job.Config.JobID,
			"lora_name":  job.Config.LoRAName,
			"status":     job.Status,
			"progress":   job.Progress,
			"start_time": job.StartTime,
			"end_time":   job.EndTime,
			"error":      job.Error,
		}
		job.mu.RUnlock()
	}
	
	json.NewEncoder(w).Encode(safeJobs)
}

// getJobHandler gets a specific job
func (m *Manager) getJobHandler(w http.ResponseWriter, r *http.Request) {
	jobID := chi.URLParam(r, "job_id")

	job, ok := m.GetJob(jobID)
	if !ok {
		http.Error(w, "Job not found", http.StatusNotFound)
		return
	}

	job.mu.RLock()
	defer job.mu.RUnlock()

	json.NewEncoder(w).Encode(map[string]interface{}{
		"job_id":     job.Config.JobID,
		"config":     job.Config,
		"status":     job.Status,
		"progress":   job.Progress,
		"start_time": job.StartTime,
		"end_time":   job.EndTime,
		"error":      job.Error,
		"log_lines":  len(job.Logs),
		"logs":       job.Logs,
	})
}

// logsHandler streams job logs
func (m *Manager) logsHandler(w http.ResponseWriter, r *http.Request) {
	jobID := chi.URLParam(r, "job_id")

	job, ok := m.GetJob(jobID)
	if !ok {
		http.Error(w, "Job not found", http.StatusNotFound)
		return
	}

	job.mu.RLock()
	logs := make([]string, len(job.Logs))
	copy(logs, job.Logs)
	job.mu.RUnlock()

	json.NewEncoder(w).Encode(map[string]interface{}{
		"logs": logs,
	})
}

// cancelJobHandler cancels a running job
func (m *Manager) cancelJobHandler(w http.ResponseWriter, r *http.Request) {
	jobID := chi.URLParam(r, "job_id")

	if err := m.CancelJob(jobID); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "cancelled"})
}

// listLoRAsHandler lists trained LoRAs
func (m *Manager) listLoRAsHandler(w http.ResponseWriter, r *http.Request) {
	loras, err := ListLoRAs(projectRoot())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	json.NewEncoder(w).Encode(loras)
}

// deleteLoRAHandler deletes a LoRA
func (m *Manager) deleteLoRAHandler(w http.ResponseWriter, r *http.Request) {
	loraName := chi.URLParam(r, "name")

	if err := DeleteLoRA(projectRoot(), loraName); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "deleted"})
}

// clearDatasetHandler clears a training data session
func (m *Manager) clearDatasetHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		SessionID string `json:"session_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	dataDir := filepath.Join(projectRoot(), "training_data", req.SessionID)
	if err := os.RemoveAll(dataDir); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "cleared"})
}

// getActiveLoRAHandler returns the currently active LoRA path
func (m *Manager) getActiveLoRAHandler(w http.ResponseWriter, r *http.Request) {
	path := m.cfg.GetString("active_lora_path")
	json.NewEncoder(w).Encode(map[string]string{"active_lora_path": path})
}

// setActiveLoRAHandler sets the active LoRA (by name, resolved to abs path)
func (m *Manager) setActiveLoRAHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name string `json:"name"` // LoRA directory name under loras/
		Path string `json:"path"` // absolute path (alternative)
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request", http.StatusBadRequest)
		return
	}

	loraPath := req.Path
	if loraPath == "" && req.Name != "" {
		loraPath = filepath.Join(projectRoot(), "loras", req.Name)
	}
	if loraPath == "" {
		http.Error(w, "name or path required", http.StatusBadRequest)
		return
	}
	if _, err := os.Stat(loraPath); os.IsNotExist(err) {
		http.Error(w, fmt.Sprintf("LoRA path does not exist: %s", loraPath), http.StatusBadRequest)
		return
	}

	if _, err := m.cfg.Patch(map[string]any{"active_lora_path": loraPath}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	json.NewEncoder(w).Encode(map[string]string{"active_lora_path": loraPath})
}

// clearActiveLoRAHandler removes the active LoRA selection
func (m *Manager) clearActiveLoRAHandler(w http.ResponseWriter, r *http.Request) {
	if _, err := m.cfg.Patch(map[string]any{"active_lora_path": ""}); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	json.NewEncoder(w).Encode(map[string]string{"active_lora_path": ""})
}

// ── Audio split ──────────────────────────────────────────────────────────────

// SplitJob holds the state of a running split job
type SplitJob struct {
	ID        string   `json:"id"`
	Status    string   `json:"status"` // "running" | "done" | "error"
	Progress  int      `json:"progress"`
	Total     int      `json:"total"`
	Done      int      `json:"done"`
	Logs      []string `json:"logs"`
	OutputDir string   `json:"output_dir"`
	Error     string   `json:"error,omitempty"`
	mu        sync.RWMutex
}

var splitJobs sync.Map // map[string]*SplitJob

// splitAudioHandler starts a split-audio job
func (m *Manager) splitAudioHandler(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseMultipartForm(500 << 20); err != nil { // 500 MB max
		http.Error(w, "Failed to parse form", http.StatusBadRequest)
		return
	}

	// Accept optional params from form
	sessionID := r.FormValue("session_id")
	if sessionID == "" {
		sessionID = uuid.New().String()
	}
	whisperModel := r.FormValue("whisper_model")
	if whisperModel == "" {
		whisperModel = "base"
	}
	silenceThreshold := r.FormValue("silence_threshold")
	if silenceThreshold == "" {
		silenceThreshold = "-35"
	}
	minSilenceLen := r.FormValue("min_silence_len")
	if minSilenceLen == "" {
		minSilenceLen = "0.5"
	}
	minSegmentLen := r.FormValue("min_segment_len")
	if minSegmentLen == "" {
		minSegmentLen = "2.0"
	}
	maxSegmentLen := r.FormValue("max_segment_len")
	if maxSegmentLen == "" {
		maxSegmentLen = "30.0"
	}
	speakerNumber := r.FormValue("speaker_number")
	if speakerNumber == "" {
		speakerNumber = "1"
	}
	device := r.FormValue("device")
	if device == "" {
		device = "cpu"
	}

	// Save uploaded audio file
	file, header, err := r.FormFile("audio")
	if err != nil {
		http.Error(w, "audio file required", http.StatusBadRequest)
		return
	}
	defer file.Close()

	uploadDir := filepath.Join(projectRoot(), "training_data", sessionID)
	if err := os.MkdirAll(uploadDir, 0755); err != nil {
		http.Error(w, "Failed to create upload dir", http.StatusInternalServerError)
		return
	}

	inputPath := filepath.Join(uploadDir, filepath.Base(header.Filename))
	dest, err := os.Create(inputPath)
	if err != nil {
		http.Error(w, "Failed to save audio", http.StatusInternalServerError)
		return
	}
	if _, err := io.Copy(dest, file); err != nil {
		dest.Close()
		http.Error(w, "Failed to write audio", http.StatusInternalServerError)
		return
	}
	dest.Close()

	outputDir := filepath.Join(uploadDir, "segments")
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		http.Error(w, "Failed to create segments dir", http.StatusInternalServerError)
		return
	}

	// Create job
	jobID := uuid.New().String()
	job := &SplitJob{
		ID:        jobID,
		Status:    "running",
		OutputDir: outputDir,
	}
	splitJobs.Store(jobID, job)

	// Launch in background
	pythonPath := m.genMgr.GetPythonPath()
	scriptPath := filepath.Join(projectRoot(), "split_audio.py")

	go func() {
		args := []string{
			scriptPath,
			"--input", inputPath,
			"--output_dir", outputDir,
			"--whisper_model", whisperModel,
			"--silence_threshold", silenceThreshold,
			"--min_silence_len", minSilenceLen,
			"--min_segment_len", minSegmentLen,
			"--max_segment_len", maxSegmentLen,
			"--speaker_number", speakerNumber,
			"--device", device,
			"--base_name", sessionID,
		}
		cmd := exec.CommandContext(context.Background(), pythonPath, args...)
		cmd.Dir = projectRoot()

		stdout, _ := cmd.StdoutPipe()
		stderr, _ := cmd.StderrPipe()

		if err := cmd.Start(); err != nil {
			job.mu.Lock()
			job.Status = "error"
			job.Error = err.Error()
			job.mu.Unlock()
			return
		}

		// Pipe stderr to logs
		go func() {
			scanner := bufio.NewScanner(stderr)
			for scanner.Scan() {
				line := scanner.Text()
				job.mu.Lock()
				job.Logs = append(job.Logs, line)
				job.mu.Unlock()
			}
		}()

		// Parse stdout progress
		scanner := bufio.NewScanner(stdout)
		for scanner.Scan() {
			line := scanner.Text()
			job.mu.Lock()
			job.Logs = append(job.Logs, line)
			if strings.HasPrefix(line, "SPLIT_PROGRESS:") {
				// SPLIT_PROGRESS:N/TOTAL
				parts := strings.TrimPrefix(line, "SPLIT_PROGRESS:")
				var n, total int
				fmt.Sscanf(parts, "%d/%d", &n, &total)
				job.Progress = n
				job.Total = total
			} else if strings.HasPrefix(line, "SPLIT_DONE:") {
				var done int
				fmt.Sscanf(strings.TrimPrefix(line, "SPLIT_DONE:"), "%d", &done)
				job.Done = done
			}
			job.mu.Unlock()
		}

		cmd.Wait()
		job.mu.Lock()
		if job.Status == "running" {
			if cmd.ProcessState != nil && cmd.ProcessState.ExitCode() == 0 {
				job.Status = "done"
			} else {
				job.Status = "error"
				if job.Error == "" {
					job.Error = "split_audio.py exited with non-zero code"
				}
			}
		}
		job.mu.Unlock()
	}()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"job_id":     jobID,
		"session_id": sessionID,
		"output_dir": outputDir,
	})
}

// splitProgressHandler returns split job status
func (m *Manager) splitProgressHandler(w http.ResponseWriter, r *http.Request) {
	jobID := chi.URLParam(r, "job_id")
	raw, ok := splitJobs.Load(jobID)
	if !ok {
		http.Error(w, "Split job not found", http.StatusNotFound)
		return
	}
	job := raw.(*SplitJob)

	job.mu.RLock()
	defer job.mu.RUnlock()

	// If done, also list generated files
	var segments []map[string]string
	if job.Status == "done" {
		entries, _ := os.ReadDir(job.OutputDir)
		for _, e := range entries {
			if !e.IsDir() && strings.HasSuffix(e.Name(), ".wav") {
				base := strings.TrimSuffix(e.Name(), ".wav")
				txtPath := filepath.Join(job.OutputDir, base+".txt")
				entry := map[string]string{
					"audio":     e.Name(),
					"audio_dir": job.OutputDir,
				}
				if _, err := os.Stat(txtPath); err == nil {
					entry["transcript"] = base + ".txt"
				}
				segments = append(segments, entry)
			}
		}
	}

	json.NewEncoder(w).Encode(map[string]any{
		"id":         job.ID,
		"status":     job.Status,
		"progress":   job.Progress,
		"total":      job.Total,
		"done":       job.Done,
		"error":      job.Error,
		"output_dir": job.OutputDir,
		"segments":   segments,
	})
}
