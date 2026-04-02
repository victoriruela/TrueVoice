package server

import (
	"embed"
	"io/fs"
	"net/http"
	"path"
	"strings"
)

//go:embed webdist webdist/**
var webDistFS embed.FS

func (s *Server) staticHandler() http.Handler {
	sub, err := fs.Sub(webDistFS, "webdist")
	if err != nil {
		return http.NotFoundHandler()
	}

	fileServer := http.FileServer(http.FS(sub))

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		p := r.URL.Path
		if p == "" || p == "/" {
			http.ServeFileFS(w, r, sub, "index.html")
			return
		}

		clean := strings.TrimPrefix(path.Clean(p), "/")
		if clean == "." {
			clean = "index.html"
		}

		if _, err := fs.Stat(sub, clean); err == nil {
			fileServer.ServeHTTP(w, r)
			return
		}

		// SPA fallback
		http.ServeFileFS(w, r, sub, "index.html")
	})
}
