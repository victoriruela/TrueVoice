package server

import (
	"embed"
	"io/fs"
	"mime"
	"net/http"
	"path"
	"regexp"
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
			w.Header().Set("Cache-Control", "no-store, no-cache, must-revalidate")
			w.Header().Set("Pragma", "no-cache")
			w.Header().Set("Expires", "0")
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
			// If a client has a stale cached index.html, it may request an old hashed JS bundle.
			// Serve the currently referenced bundle from index.html so the app can recover.
			if strings.HasPrefix(clean, "_expo/static/js/web/index-") && strings.HasSuffix(clean, ".js") {
				if fallback, ok := currentBundleFromIndex(sub); ok {
					r2 := r.Clone(r.Context())
					r2.URL.Path = "/" + fallback
					fileServer.ServeHTTP(w, r2)
					return
				}
			}

			http.NotFound(w, r)
			return
		}

		// SPA fallback
		w.Header().Set("Cache-Control", "no-store, no-cache, must-revalidate")
		w.Header().Set("Pragma", "no-cache")
		w.Header().Set("Expires", "0")
		http.ServeFileFS(w, r, sub, "index.html")
	})
}

var bundleRegex = regexp.MustCompile(`src="/app/_expo/static/js/web/(index-[^"]+\.js)"`)

func currentBundleFromIndex(sub fs.FS) (string, bool) {
	indexHTML, err := fs.ReadFile(sub, "index.html")
	if err != nil {
		return "", false
	}

	matches := bundleRegex.FindSubmatch(indexHTML)
	if len(matches) != 2 {
		return "", false
	}

	bundlePath := path.Join("_expo/static/js/web", string(matches[1]))
	if _, err := fs.Stat(sub, bundlePath); err != nil {
		return "", false
	}

	return bundlePath, true
}
