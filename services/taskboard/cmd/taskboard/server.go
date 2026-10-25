package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"time"
)

// Bind both listeners before serving. A failed metrics bind must fail the process
// rather than leave an apparently healthy app without its monitoring endpoint.
func serve(ctx context.Context, servers ...*http.Server) error {
	listeners := make([]net.Listener, 0, len(servers))
	defer func() {
		for _, listener := range listeners {
			_ = listener.Close()
		}
	}()
	for _, server := range servers {
		listener, err := net.Listen("tcp", server.Addr)
		if err != nil {
			return fmt.Errorf("listen on %s: %w", server.Addr, err)
		}
		listeners = append(listeners, listener)
	}
	results := make(chan error, len(servers))
	for index, server := range servers {
		slog.Info("server_start", "address", server.Addr)
		go func(s *http.Server, l net.Listener) { results <- s.Serve(l) }(server, listeners[index])
	}
	var result error
	select {
	case <-ctx.Done():
	case err := <-results:
		if !errors.Is(err, http.ErrServerClosed) {
			result = err
		}
	}
	slog.Info("server_shutdown")
	shutdown, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	for _, server := range servers {
		if err := server.Shutdown(shutdown); err != nil {
			_ = server.Close()
			result = errors.Join(result, err)
		}
	}
	return result
}
