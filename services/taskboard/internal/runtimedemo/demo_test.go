package runtimedemo

import (
	"context"
	"errors"
	"runtime"
	"testing"
	"time"
)

func TestConfigurationIsOffByDefaultAndBounded(t *testing.T) {
	config, err := Parse("", "")
	if err != nil || config != (Config{}) {
		t.Fatal(config, err)
	}
	for _, input := range [][2]string{{"-1", "0"}, {"1001", "0"}, {"abc", "0"}, {"1", "-1"}, {"0", "65"}, {"0", "99999999999999999999"}} {
		if _, err := Parse(input[0], input[1]); err == nil {
			t.Fatalf("accepted invalid settings: %v", input)
		}
	}
}

func TestWorkloadIsVisibleToRuntimeAndStops(t *testing.T) {
	runtime.GC()
	var before, during runtime.MemStats
	runtime.ReadMemStats(&before)
	baseline := runtime.NumGoroutine()
	stop, err := Start(context.Background(), Config{Goroutines: 64, HeapMiB: 4})
	if err != nil {
		t.Fatal(err)
	}
	defer stop()
	runtime.GC()
	runtime.ReadMemStats(&during)
	if during.HeapAlloc < before.HeapAlloc+3*1024*1024 || runtime.NumGoroutine() < baseline+64 {
		t.Fatal("demo must create real live heap and goroutines")
	}
	stop()
	stop() // repeated cleanup must remain safe
	if runtime.NumGoroutine() > baseline+2 {
		t.Fatal("workers were not joined")
	}
}

func TestCancellationAndInvalidDirectConfiguration(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := Start(ctx, Config{HeapMiB: 64}); !errors.Is(err, context.Canceled) {
		t.Fatal("cancelled startup must not allocate the workload", err)
	}
	if _, err := Start(context.Background(), Config{HeapMiB: 100}); err == nil {
		t.Fatal("direct callers must also respect bounds")
	}
	ctx, cancel = context.WithCancel(context.Background())
	stop, err := Start(ctx, Config{Goroutines: 100})
	if err != nil {
		t.Fatal(err)
	}
	cancel()
	done := make(chan struct{})
	go func() { stop(); close(done) }()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("shutdown did not join workers")
	}
}
