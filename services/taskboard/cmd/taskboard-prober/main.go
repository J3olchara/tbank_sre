package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"tbank-sre/taskboard/internal/logging"
	"tbank-sre/taskboard/internal/prober"
)

func run() error {
	interval, err := time.ParseDuration(env("PROBE_INTERVAL", "5s"))
	if err != nil || interval < time.Second {
		return fmt.Errorf("PROBE_INTERVAL must be at least 1s")
	}
	timeout, err := time.ParseDuration(env("PROBE_TIMEOUT", "2s"))
	if err != nil || timeout <= 0 || timeout >= interval {
		return fmt.Errorf("PROBE_TIMEOUT must be positive and shorter than PROBE_INTERVAL")
	}
	probe, err := prober.New(env("PROBE_TARGET", "http://taskboard:8080"), timeout)
	if err != nil {
		return err
	}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	server := &http.Server{Addr: env("PROBE_METRICS_ADDR", ":9091"), Handler: probe.Handler(), ReadHeaderTimeout: 3 * time.Second,
		ReadTimeout: 5 * time.Second, WriteTimeout: 5 * time.Second, IdleTimeout: 30 * time.Second}
	result := make(chan error, 1)
	go func() { result <- server.ListenAndServe() }()
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	defer func() {
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdown)
	}()
	for {
		check, cancel := context.WithTimeout(ctx, timeout)
		err := probe.Check(check)
		cancel()
		if err != nil {
			slog.Warn("probe_failed", "reason", err.Error())
		}
		select {
		case <-ctx.Done():
			return nil
		case err := <-result:
			return err
		case <-ticker.C:
		}
	}
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func main() {
	slog.SetDefault(logging.New(os.Stdout, slog.LevelInfo, "taskboard-prober"))
	if err := run(); err != nil {
		slog.Error("prober_failed", "reason", err.Error())
		os.Exit(1)
	}
}
