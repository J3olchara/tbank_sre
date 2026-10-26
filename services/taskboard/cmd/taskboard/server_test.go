package main

import (
	"context"
	"net"
	"net/http"
	"testing"
	"time"
)

func TestServeRejectsOccupiedMetricsAddress(t *testing.T) {
	busy, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer busy.Close()
	err = serve(context.Background(), &http.Server{Addr: "127.0.0.1:0"}, &http.Server{Addr: busy.Addr().String()})
	if err == nil {
		t.Fatal("metrics listener failure was ignored")
	}
}

func TestServeClosesBothListenersOnCancellation(t *testing.T) {
	listeners := []net.Listener{}
	for range 2 {
		l, err := net.Listen("tcp", "127.0.0.1:0")
		if err != nil {
			t.Fatal(err)
		}
		listeners = append(listeners, l)
	}
	first, second := listeners[0].Addr().String(), listeners[1].Addr().String()
	for _, l := range listeners {
		_ = l.Close()
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan error, 1)
	go func() { done <- serve(ctx, &http.Server{Addr: first}, &http.Server{Addr: second}) }()
	deadline := time.Now().Add(2 * time.Second)
	for {
		connection, err := net.DialTimeout("tcp", second, 50*time.Millisecond)
		if err == nil {
			_ = connection.Close()
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("metrics listener did not start")
		}
		time.Sleep(10 * time.Millisecond)
	}
	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("shutdown blocked")
	}
	for _, address := range []string{first, second} {
		connection, err := net.DialTimeout("tcp", address, 100*time.Millisecond)
		if err == nil {
			_ = connection.Close()
			t.Fatalf("listener %s left open", address)
		}
	}
}
