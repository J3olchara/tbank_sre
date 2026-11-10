package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"tbank-sre/taskboard/internal/alertinbox"
	"tbank-sre/taskboard/internal/logging"
)

func run() error {
	path := os.Getenv("INBOX_DATA")
	if path == "" {
		path = "/data/notifications.json"
	}
	store, err := alertinbox.Open(path)
	if err != nil {
		return err
	}
	address := os.Getenv("INBOX_ADDR")
	if address == "" {
		address = ":8085"
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	server := &http.Server{Addr: address, Handler: alertinbox.NewHandler(store), ReadHeaderTimeout: 3 * time.Second,
		ReadTimeout: 5 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 30 * time.Second}
	result := make(chan error, 1)
	go func() { result <- server.ListenAndServe() }()
	slog.Info("inbox_start", "address", address)
	select {
	case err := <-result:
		if !errors.Is(err, http.ErrServerClosed) {
			return err
		}
	case <-ctx.Done():
	}
	shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := server.Shutdown(shutdown); err != nil {
		_ = server.Close()
		return err
	}
	return nil
}

func main() {
	slog.SetDefault(logging.New(os.Stdout, slog.LevelInfo, "taskboard-alert-inbox"))
	if err := run(); err != nil {
		slog.Error("inbox_failed", "reason", err.Error())
		os.Exit(1)
	}
}
