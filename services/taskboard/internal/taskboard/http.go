package taskboard

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"mime"
	"net/http"
	"path/filepath"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

type API struct{ db *sql.DB }

func NewHandler(db *sql.DB, staticDir string) http.Handler {
	api := &API{db: db}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { respond(w, 200, map[string]string{"status": "ok"}) })
	mux.HandleFunc("GET /readyz", api.ready)
	mux.HandleFunc("GET /api/tasks", api.list)
	mux.HandleFunc("GET /api/tasks/{id}", api.get)
	mux.HandleFunc("POST /api/tasks", api.save)
	mux.HandleFunc("PUT /api/tasks/{id}", api.save)
	mux.HandleFunc("DELETE /api/tasks/{id}", api.delete)
	mux.HandleFunc("/api/", func(w http.ResponseWriter, r *http.Request) { fail(w, 404, "Маршрут не найден") })
	mux.Handle("GET /assets/", http.FileServer(http.Dir(staticDir)))
	mux.HandleFunc("GET /{$}", func(w http.ResponseWriter, r *http.Request) {
		http.ServeFile(w, r, filepath.Join(staticDir, "index.html"))
	})
	return logRequests(mux)
}
func respond(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if data != nil {
		_ = json.NewEncoder(w).Encode(data)
	}
}
func fail(w http.ResponseWriter, status int, message string) {
	respond(w, status, map[string]string{"error": message})
}
func dbFailure(w http.ResponseWriter, err error) {
	if errors.Is(err, sql.ErrNoRows) {
		fail(w, 404, "Задача не найдена")
		return
	}
	// DSNs and SQL values must never appear in logs.
	slog.Error("database_request_failed")
	fail(w, 503, "База данных временно недоступна")
}
func requestContext(r *http.Request) (context.Context, context.CancelFunc) {
	return context.WithTimeout(r.Context(), 5*time.Second)
}
func taskID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil || id < 1 {
		fail(w, 400, "Некорректный ID")
		return 0, false
	}
	return id, true
}
func (api *API) ready(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := requestContext(r)
	defer cancel()
	var ready bool
	err := api.db.QueryRowContext(ctx, "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version='001_tasks.sql')").Scan(&ready)
	if err != nil {
		dbFailure(w, err)
		return
	}
	if !ready {
		fail(w, 503, "Миграции не применены")
		return
	}
	respond(w, 200, map[string]string{"status": "ready"})
}
func (api *API) list(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := requestContext(r)
	defer cancel()
	rows, err := api.db.QueryContext(ctx, "SELECT "+columns+" FROM tasks ORDER BY id DESC LIMIT 500")
	if err != nil {
		dbFailure(w, err)
		return
	}
	defer rows.Close()
	tasks := make([]Task, 0)
	for rows.Next() {
		task, err := scanTask(rows)
		if err != nil {
			dbFailure(w, err)
			return
		}
		tasks = append(tasks, task)
	}
	if err := rows.Err(); err != nil {
		dbFailure(w, err)
		return
	}
	respond(w, 200, tasks)
}
func (api *API) get(w http.ResponseWriter, r *http.Request) {
	id, ok := taskID(w, r)
	if !ok {
		return
	}
	ctx, cancel := requestContext(r)
	defer cancel()
	task, err := scanTask(api.db.QueryRowContext(ctx, "SELECT "+columns+" FROM tasks WHERE id=$1", id))
	if err != nil {
		dbFailure(w, err)
		return
	}
	respond(w, 200, task)
}

type Input struct {
	Title       string `json:"title"`
	Description string `json:"description"`
	Status      string `json:"status"`
}

func (in *Input) validate() bool {
	in.Title = strings.TrimSpace(in.Title)
	return utf8.ValidString(in.Title) && utf8.ValidString(in.Description) && !strings.ContainsRune(in.Title, 0) && !strings.ContainsRune(in.Description, 0) && utf8.RuneCountInString(in.Title) >= 1 && utf8.RuneCountInString(in.Title) <= 200 && utf8.RuneCountInString(in.Description) <= 2000 && (in.Status == "todo" || in.Status == "doing" || in.Status == "done")
}
func (api *API) save(w http.ResponseWriter, r *http.Request) {
	var id int64
	if r.Method == http.MethodPut {
		var ok bool
		id, ok = taskID(w, r)
		if !ok {
			return
		}
	}
	media, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || media != "application/json" {
		fail(w, 415, "Нужен Content-Type: application/json")
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, 16*1024)
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()
	var input Input
	if err := decoder.Decode(&input); err != nil {
		fail(w, 400, "Некорректный JSON")
		return
	}
	if decoder.Decode(new(any)) != io.EOF || !input.validate() {
		fail(w, 400, "Нужны title (1–200 символов), description (до 2000), status (todo/doing/done)")
		return
	}
	ctx, cancel := requestContext(r)
	defer cancel()
	var task Task
	if r.Method == http.MethodPost {
		task, err = scanTask(api.db.QueryRowContext(ctx, "INSERT INTO tasks (title,description,status) VALUES ($1,$2,$3) RETURNING "+columns, input.Title, input.Description, input.Status))
	} else {
		task, err = scanTask(api.db.QueryRowContext(ctx, "UPDATE tasks SET title=$1,description=$2,status=$3,updated_at=now() WHERE id=$4 RETURNING "+columns, input.Title, input.Description, input.Status, id))
	}
	if err != nil {
		dbFailure(w, err)
		return
	}
	code := 200
	if r.Method == http.MethodPost {
		code = 201
		w.Header().Set("Location", "/api/tasks/"+strconv.FormatInt(task.ID, 10))
	}
	respond(w, code, task)
}
func (api *API) delete(w http.ResponseWriter, r *http.Request) {
	id, ok := taskID(w, r)
	if !ok {
		return
	}
	ctx, cancel := requestContext(r)
	defer cancel()
	result, err := api.db.ExecContext(ctx, "DELETE FROM tasks WHERE id=$1", id)
	if err != nil {
		dbFailure(w, err)
		return
	}
	count, err := result.RowsAffected()
	if err != nil {
		dbFailure(w, err)
		return
	}
	if count == 0 {
		fail(w, 404, "Задача не найдена")
		return
	}
	w.WriteHeader(204)
}

type loggedResponse struct {
	http.ResponseWriter
	status int
}

func (w *loggedResponse) WriteHeader(status int) {
	w.status = status
	w.ResponseWriter.WriteHeader(status)
}
func (w *loggedResponse) Write(data []byte) (int, error) {
	if w.status == 0 {
		w.WriteHeader(200)
	}
	return w.ResponseWriter.Write(data)
}
func logRequests(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		response := &loggedResponse{ResponseWriter: w}
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'")
		next.ServeHTTP(response, r)
		if response.status == 0 {
			response.status = 200
		}
		slog.Info("http_request", "method", r.Method, "path", r.URL.Path, "status", response.status, "duration_ms", time.Since(start).Milliseconds())
	})
}
