// Package runtimedemo provides bounded, opt-in workloads for runtime alerts.
package runtimedemo

import (
	"context"
	"fmt"
	"runtime"
	"strconv"
	"sync"
)

type Config struct {
	Goroutines int
	HeapMiB    int
}

func Parse(goroutines, heapMiB string) (Config, error) {
	var c Config
	for _, setting := range []struct {
		name, value string
		destination *int
		maximum     int
	}{{"DEMO_GOROUTINES", goroutines, &c.Goroutines, 1000}, {"DEMO_HEAP_MIB", heapMiB, &c.HeapMiB, 64}} {
		if setting.value == "" {
			continue
		}
		value, err := strconv.Atoi(setting.value)
		if err != nil || value < 0 || value > setting.maximum {
			return Config{}, fmt.Errorf("%s must be between 0 and %d", setting.name, setting.maximum)
		}
		*setting.destination = value
	}
	return c, nil
}

// Start allocates real Go heap and goroutines. The regular Go collector observes
// them; no metric is manually changed. The returned stop function joins workers.
func Start(parent context.Context, c Config) (func(), error) {
	if c.Goroutines < 0 || c.Goroutines > 1000 || c.HeapMiB < 0 || c.HeapMiB > 64 {
		return nil, fmt.Errorf("runtime demo configuration exceeds limits")
	}
	if err := parent.Err(); err != nil {
		return nil, err
	}
	ctx, cancel := context.WithCancel(parent)
	var workers sync.WaitGroup
	for range c.Goroutines {
		workers.Add(1)
		go func() {
			defer workers.Done()
			<-ctx.Done()
		}()
	}
	if c.HeapMiB > 0 {
		heap := make([]byte, c.HeapMiB*1024*1024)
		// Touch pages so the demonstration reserves actual resident memory too.
		for page := 0; page < len(heap); page += 4096 {
			heap[page] = 1
		}
		workers.Add(1)
		go func() {
			defer workers.Done()
			<-ctx.Done()
			runtime.KeepAlive(heap)
		}()
	}
	return func() { cancel(); workers.Wait() }, nil
}
