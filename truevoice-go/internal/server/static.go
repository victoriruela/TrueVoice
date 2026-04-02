package server

import (
	"embed"
	"io/fs"
	"mime"
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
		if p == "" || p == "/" || p == "/app" || p == "/app/" {
			http.ServeFileFS(w, r, sub, "index.html")
			return
		}

		clean := strings.TrimPrefix(path.Clean(p), "/")
		clean = strings.TrimPrefix(clean, "app/")
		if clean == "." {
			clean = "index.html"
		}

		if _, err := fs.Stat(sub, clean); err == nil {
			if ext := path.Ext(clean); ext != "" {
				if contentType := mime.TypeByExtension(ext); contentType != "" {
					w.Header().Set("Content-Type", contentType)
				}
			}

			r2 := r.Clone(r.Context())
			r2.URL.Path = "/" + clean
			fileServer.ServeHTTP(w, r2)
			return
		}

		// Asset requests should 404 instead of falling back to index.html.
		if path.Ext(clean) != "" {
			http.NotFound(w, r)
			return
		}

		// SPA fallback
		http.ServeFileFS(w, r, sub, "index.html")
	})
}
