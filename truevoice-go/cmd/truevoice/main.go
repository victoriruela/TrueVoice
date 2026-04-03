package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"runtime"
	"syscall"

	"truevoice/internal/config"
	"truevoice/internal/server"
)

const defaultPort = "8000"

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = defaultPort
	}

	cfg, err := config.Load()
	if err != nil {
		log.Printf("WARN: could not load config: %v (using defaults)", err)
		cfg = config.Default()
	}

	srv := server.New(cfg)

	log.Println("Bootstrapping Python runtime and VibeVoice dependencies (first run can take several minutes)...")
	if err := srv.BootstrapRuntime(); err != nil {
		log.Fatalf("Startup bootstrap failed: %v", err)
	}
	log.Println("Runtime bootstrap ready")

	// Graceful shutdown
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		addr := fmt.Sprintf(":%s", port)
		log.Printf("TrueVoice listening on http://localhost%s", addr)
		if err := http.ListenAndServe(addr, srv.Router()); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Open browser on Windows
	if runtime.GOOS == "windows" {
		url := fmt.Sprintf("http://localhost:%s/app", port)
		_ = exec.Command("rundll32", "url.dll,FileProtocolHandler", url).Start()
	}

	<-stop
	log.Println("Shutting down...")
	srv.Shutdown()
}
