package training

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"

	"github.com/go-chi/chi/v5"
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

	// Prepare CSV
	csvPath := filepath.Join(dataDir, "dataset.csv")
	if err := PrepareDatasetCSV(validFiles, csvPath); err != nil {
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
