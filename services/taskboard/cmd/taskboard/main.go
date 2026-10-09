package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/lib/pq"
	"tbank-sre/taskboard/internal/taskboard"
)

func run() error {
	level := slog.LevelInfo
	if err := level.UnmarshalText([]byte(env("LOG_LEVEL", "INFO"))); err != nil {
		return fmt.Errorf("invalid LOG_LEVEL")
	}
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level})))
	if len(os.Args) > 1 && os.Args[1] == "healthcheck" {
		client := &http.Client{Timeout: 4 * time.Second}
		response, err := client.Get("http://127.0.0.1:" + env("PORT", "8080") + "/readyz")
		if err != nil {
			return fmt.Errorf("healthcheck failed")
		}
		defer response.Body.Close()
		if response.StatusCode != 200 {
			return fmt.Errorf("not ready")
		}
		return nil
	}
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		return fmt.Errorf("DATABASE_URL is required")
	}
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return fmt.Errorf("invalid database configuration")
	}
	defer db.Close()
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)
	if len(os.Args) > 1 {
		if os.Args[1] != "migrate" || len(os.Args) != 2 {
			return fmt.Errorf("usage: taskboard [migrate|healthcheck]")
		}
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		return taskboard.Migrate(ctx, db)
	}
	handler := taskboard.NewHandler(db, env("STATIC_DIR", "web/dist"))
	server := &http.Server{Addr: ":" + env("PORT", "8080"), Handler: handler,
		ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 60 * time.Second}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	result := make(chan error, 1)
	go func() { slog.Info("server_start", "address", server.Addr); result <- server.ListenAndServe() }()
	select {
	case err := <-result:
		return err
	case <-ctx.Done():
		slog.Info("server_shutdown")
		shutdown, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdown); err != nil {
			return err
		}
		err := <-result
		if !errors.Is(err, http.ErrServerClosed) {
			return err
		}
		return nil
	}
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
func main() {
	if err := run(); err != nil {
		slog.Error("application_failed", "reason", err.Error())
		os.Exit(1)
	}
}
