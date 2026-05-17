package training

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
)

// GenerationManager interface to avoid circular import
type GenerationManager interface {
	GetPythonPath() string
}

// ConfigStore interface for reading/writing config (avoids circular import)
type ConfigStore interface {
	GetString(key string) string
	Patch(updates map[string]any) (map[string]any, error)
}

// TrainingConfig holds configuration for a training job
type TrainingConfig struct {
	JobID              string  `json:"job_id"`
	LoRAName           string  `json:"lora_name"`
	ModelBase          string  `json:"model_base"`
	DatasetPath        string  `json:"dataset_path"`
	OutputDir          string  `json:"output_dir"`
	Epochs             int     `json:"epochs"`
	BatchSize          int     `json:"batch_size"`
	GradientAccum      int     `json:"gradient_accumulation_steps"`
	LearningRate       float64 `json:"learning_rate"`
	VoicePromptDropRate float64 `json:"voice_prompt_drop_rate"`
	MaxGradNorm        float64 `json:"max_grad_norm"`
	DiffusionLossWeight float64 `json:"diffusion_loss_weight"`
	CELossWeight       float64 `json:"ce_loss_weight"`
}

// TrainingJob represents a running or completed training job
type TrainingJob struct {
	Config    TrainingConfig `json:"config"`
	Status    string         `json:"status"` // "preparing", "running", "completed", "failed", "cancelled"
	Progress  float64        `json:"progress"` // 0.0 - 1.0
	StartTime time.Time      `json:"start_time"`
	EndTime   *time.Time     `json:"end_time,omitempty"`
	Logs      []string       `json:"logs"`
	Error     string         `json:"error,omitempty"`
	
	ctx    context.Context
	cancel context.CancelFunc
	cmd    *exec.Cmd
	mu     sync.RWMutex
}

// DatasetFile represents an uploaded audio-transcript pair
type DatasetFile struct {
	AudioPath      string `json:"audio_path"`
	TranscriptPath string `json:"transcript_path"`
	BaseName       string `json:"base_name"`
	Valid          bool   `json:"valid"`
	ErrorMsg       string `json:"error_msg,omitempty"`
}

// Manager handles training jobs
type Manager struct {
	jobs   map[string]*TrainingJob
	mu     sync.RWMutex
	genMgr GenerationManager
	cfg    ConfigStore
}

// NewManager creates a new training manager
func NewManager(genMgr GenerationManager, cfg ConfigStore) *Manager {
	return &Manager{
		jobs:   make(map[string]*TrainingJob),
		genMgr: genMgr,
		cfg:    cfg,
	}
}

// CreateJob creates a new training job
func (m *Manager) CreateJob(config TrainingConfig) (*TrainingJob, error) {
	if config.JobID == "" {
		config.JobID = uuid.New().String()
	}
	
	// Set defaults
	if config.ModelBase == "" {
		config.ModelBase = "microsoft/VibeVoice-1.5B"
	}
	if config.Epochs == 0 {
		config.Epochs = 1
	}
	if config.BatchSize == 0 {
		config.BatchSize = 4
	}
	if config.GradientAccum == 0 {
		config.GradientAccum = 16
	}
	if config.LearningRate == 0 {
		config.LearningRate = 2.5e-5
	}
	if config.VoicePromptDropRate == 0 {
		config.VoicePromptDropRate = 1.0
	}
	if config.MaxGradNorm == 0 {
		config.MaxGradNorm = 0.8
	}
	if config.DiffusionLossWeight == 0 {
		config.DiffusionLossWeight = 1.4
	}
	if config.CELossWeight == 0 {
		config.CELossWeight = 0.04
	}
	
	ctx, cancel := context.WithCancel(context.Background())
	
	job := &TrainingJob{
		Config:    config,
		Status:    "preparing",
		Progress:  0.0,
		StartTime: time.Now(),
		Logs:      []string{},
		ctx:       ctx,
		cancel:    cancel,
	}
	
	m.mu.Lock()
	m.jobs[config.JobID] = job
	m.mu.Unlock()
	
	return job, nil
}

// GetJob retrieves a job by ID
func (m *Manager) GetJob(jobID string) (*TrainingJob, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	job, ok := m.jobs[jobID]
	return job, ok
}

// ListJobs returns all jobs
func (m *Manager) ListJobs() []*TrainingJob {
	m.mu.RLock()
	defer m.mu.RUnlock()
	
	jobs := make([]*TrainingJob, 0, len(m.jobs))
	for _, job := range m.jobs {
		jobs = append(jobs, job)
	}
	return jobs
}

// StartTraining starts the training subprocess
func (m *Manager) StartTraining(jobID string) error {
	job, ok := m.GetJob(jobID)
	if !ok {
		return fmt.Errorf("job not found")
	}
	
	job.mu.Lock()
	if job.Status != "preparing" {
		job.mu.Unlock()
		return fmt.Errorf("job already started or completed")
	}
	job.Status = "running"
	job.mu.Unlock()
	
	go m.runTraining(job)
	return nil
}

// runTraining executes the training subprocess
func (m *Manager) runTraining(job *TrainingJob) {
	defer func() {
		job.mu.Lock()
		now := time.Now()
		job.EndTime = &now
		if job.Status == "running" {
			job.Status = "completed"
			job.Progress = 1.0
		}
		job.mu.Unlock()
	}()
	
	cfg := job.Config
	pythonPath := m.genMgr.GetPythonPath()
	if pythonPath == "" {
		m.failJob(job, "Python runtime not ready")
		return
	}
	
	// Build command arguments
	// Prepend patches.py import to fix torch 2.0.x / transformers 4.51+ compatibility
	// (torch.compiler, load_state_dict assign=True)
	patchBootstrap := "import sys, os; sys.path.insert(0, os.getcwd()); import patches; " +
		"from vibevoice.finetune import train_vibevoice; train_vibevoice.main()"

	// DatasetPath is a JSONL file (PrepareDatasetJSONL). Use --train_jsonl for local files.
	jsonlPath := filepath.ToSlash(cfg.DatasetPath)

	args := []string{
		"-c", patchBootstrap,
		"--model_name_or_path", cfg.ModelBase,
		"--train_jsonl", jsonlPath,
		"--text_column_name", "text",
		"--audio_column_name", "audio",
		"--output_dir", cfg.OutputDir,
		"--per_device_train_batch_size", fmt.Sprintf("%d", cfg.BatchSize),
		"--gradient_accumulation_steps", fmt.Sprintf("%d", cfg.GradientAccum),
		"--learning_rate", fmt.Sprintf("%.2e", cfg.LearningRate),
		"--num_train_epochs", fmt.Sprintf("%d", cfg.Epochs),
		"--logging_steps", "10",
		"--save_steps", "500",
		"--remove_unused_columns", "False",
		"--bf16", "False", // CPU-safe default; GPU users can override
		"--do_train",
		"--gradient_clipping",
		"--gradient_checkpointing", "False",
		"--ddpm_batch_mul", "4",
		"--diffusion_loss_weight", fmt.Sprintf("%.2f", cfg.DiffusionLossWeight),
		"--train_diffusion_head", "True",
		"--ce_loss_weight", fmt.Sprintf("%.4f", cfg.CELossWeight),
		"--voice_prompt_drop_rate", fmt.Sprintf("%.2f", cfg.VoicePromptDropRate),
		"--lora_target_modules", "q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj",
		"--lr_scheduler_type", "cosine",
		"--warmup_ratio", "0.03",
		"--max_grad_norm", fmt.Sprintf("%.2f", cfg.MaxGradNorm),
	}
	
	cmd := exec.CommandContext(job.ctx, pythonPath, args...)
	cmd.Dir = projectRoot()
	
	job.mu.Lock()
	job.cmd = cmd
	job.mu.Unlock()
	
	// Capture stdout/stderr
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		m.failJob(job, fmt.Sprintf("Failed to create stdout pipe: %v", err))
		return
	}
	
	stderr, err := cmd.StderrPipe()
	if err != nil {
		m.failJob(job, fmt.Sprintf("Failed to create stderr pipe: %v", err))
		return
	}
	
	if err := cmd.Start(); err != nil {
		m.failJob(job, fmt.Sprintf("Failed to start training: %v", err))
		return
	}
	
	// Stream logs
	go m.streamLogs(job, stdout)
	go m.streamLogs(job, stderr)
	
	if err := cmd.Wait(); err != nil {
		if job.ctx.Err() == context.Canceled {
			job.mu.Lock()
			job.Status = "cancelled"
			job.mu.Unlock()
		} else {
			m.failJob(job, fmt.Sprintf("Training failed: %v", err))
		}
		return
	}
}

// streamLogs reads from pipe and appends to job logs
func (m *Manager) streamLogs(job *TrainingJob, pipe interface{ Read([]byte) (int, error) }) {
	scanner := bufio.NewScanner(pipe)
	for scanner.Scan() {
		line := scanner.Text()
		
		job.mu.Lock()
		job.Logs = append(job.Logs, line)
		
		// Parse progress from logs (example: looking for "epoch 1/3" patterns)
		if strings.Contains(line, "loss") || strings.Contains(line, "step") {
			// Simple progress estimation based on log output
			// TODO: more sophisticated progress parsing
		}
		job.mu.Unlock()
	}
}

// failJob marks job as failed
func (m *Manager) failJob(job *TrainingJob, errMsg string) {
	job.mu.Lock()
	defer job.mu.Unlock()
	
	job.Status = "failed"
	job.Error = errMsg
	job.Logs = append(job.Logs, fmt.Sprintf("ERROR: %s", errMsg))
	now := time.Now()
	job.EndTime = &now
}

// CancelJob cancels a running job
func (m *Manager) CancelJob(jobID string) error {
	job, ok := m.GetJob(jobID)
	if !ok {
		return fmt.Errorf("job not found")
	}
	
	job.mu.Lock()
	defer job.mu.Unlock()
	
	if job.Status != "running" {
		return fmt.Errorf("job not running")
	}
	
	job.cancel()
	return nil
}

// ValidateDataset validates audio-transcript pairs in a directory
func ValidateDataset(dataDir string) ([]DatasetFile, error) {
	entries, err := os.ReadDir(dataDir)
	if err != nil {
		return nil, err
	}
	
	// Group files by base name
	audioFiles := make(map[string]string)
	transcriptFiles := make(map[string]string)
	
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		
		name := entry.Name()
		ext := filepath.Ext(name)
		baseName := strings.TrimSuffix(name, ext)
		
		switch strings.ToLower(ext) {
		case ".wav", ".mp3", ".flac", ".ogg":
			audioFiles[baseName] = filepath.Join(dataDir, name)
		case ".txt":
			transcriptFiles[baseName] = filepath.Join(dataDir, name)
		}
	}
	
	// Match pairs
	var files []DatasetFile
	
	for baseName, audioPath := range audioFiles {
		file := DatasetFile{
			AudioPath: audioPath,
			BaseName:  baseName,
			Valid:     false,
		}
		
		if transcriptPath, ok := transcriptFiles[baseName]; ok {
			file.TranscriptPath = transcriptPath
			
			// Validate transcript format
			content, err := os.ReadFile(transcriptPath)
			if err != nil {
				file.ErrorMsg = fmt.Sprintf("Cannot read transcript: %v", err)
			} else {
				text := strings.TrimSpace(string(content))
				if !strings.HasPrefix(text, "Speaker 1:") {
					file.ErrorMsg = "Transcript must start with 'Speaker 1:'"
				} else {
					file.Valid = true
				}
			}
		} else {
			file.ErrorMsg = "Missing transcript file"
		}
		
		files = append(files, file)
	}
	
	return files, nil
}

// PrepareDatasetCSV kept for backward compat — delegates to PrepareDatasetJSONL.
func PrepareDatasetCSV(files []DatasetFile, outputPath string) error {
	return PrepareDatasetJSONL(files, outputPath)
}

// PrepareDatasetJSONL creates a JSONL file for VibeVoice training (--train_jsonl format).
// Each line: {"text": "Speaker 1: ...", "audio": "/abs/path/to/audio.wav"}
func PrepareDatasetJSONL(files []DatasetFile, outputPath string) error {
	f, err := os.Create(outputPath)
	if err != nil {
		return err
	}
	defer f.Close()

	for _, file := range files {
		if !file.Valid {
			continue
		}

		content, err := os.ReadFile(file.TranscriptPath)
		if err != nil {
			continue
		}
		text := strings.TrimSpace(string(content))

		// Use forward slashes for Python compatibility on Windows
		audioPath := filepath.ToSlash(file.AudioPath)

		line, err := json.Marshal(map[string]string{
			"text":  text,
			"audio": audioPath,
		})
		if err != nil {
			continue
		}
		if _, err := f.Write(append(line, '\n')); err != nil {
			return err
		}
	}

	return nil
}

// ListLoRAs lists trained LoRAs in the loras/ directory
func ListLoRAs(projectRoot string) ([]map[string]interface{}, error) {
	lorasDir := filepath.Join(projectRoot, "loras")
	
	if _, err := os.Stat(lorasDir); os.IsNotExist(err) {
		return []map[string]interface{}{}, nil
	}
	
	entries, err := os.ReadDir(lorasDir)
	if err != nil {
		return nil, err
	}
	
	loras := []map[string]interface{}{}
	
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		
		loraPath := filepath.Join(lorasDir, entry.Name())
		
		// Check for adapter_config.json
		configPath := filepath.Join(loraPath, "adapter_config.json")
		if _, err := os.Stat(configPath); os.IsNotExist(err) {
			continue
		}
		
		// Read config
		configData, err := os.ReadFile(configPath)
		if err != nil {
			continue
		}
		
		var config map[string]interface{}
		if err := json.Unmarshal(configData, &config); err != nil {
			continue
		}
		
		// Get dir stats
		info, _ := entry.Info()
		
		loras = append(loras, map[string]interface{}{
			"name":      entry.Name(),
			"path":      loraPath,
			"config":    config,
			"size_mb":   getSizeMB(loraPath),
			"modified":  info.ModTime(),
		})
	}
	
	return loras, nil
}

// getSizeMB calculates directory size in MB
func getSizeMB(path string) float64 {
	var size int64
	filepath.Walk(path, func(_ string, info os.FileInfo, err error) error {
		if err == nil && !info.IsDir() {
			size += info.Size()
		}
		return nil
	})
	return float64(size) / 1024 / 1024
}

// DeleteLoRA deletes a LoRA directory
func DeleteLoRA(projectRoot, loraName string) error {
	loraPath := filepath.Join(projectRoot, "loras", loraName)
	return os.RemoveAll(loraPath)
}

// projectRoot returns the project root directory
func projectRoot() string {
	// Try executable path first
	if exePath, err := os.Executable(); err == nil {
		current := filepath.Dir(exePath)
		for i := 0; i < 5; i++ {
			if fileExists(filepath.Join(current, "vibevoice_app.py")) {
				return current
			}
			parent := filepath.Dir(current)
			if parent == current {
				break
			}
			current = parent
		}
	}
	
	// Fallback to current directory
	if cwd, err := os.Getwd(); err == nil {
		if fileExists(filepath.Join(cwd, "vibevoice_app.py")) {
			return cwd
		}
		parent := filepath.Dir(cwd)
		if fileExists(filepath.Join(parent, "vibevoice_app.py")) {
			return parent
		}
	}
	
	return "."
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
