package taskboard

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"sync/atomic"
	"time"
)

// DemoConfig only affects task API routes. Both settings are off by default.
// There is deliberately no HTTP control endpoint or client-controlled switch.
type DemoConfig struct {
	FailureEvery uint64
	Latency      time.Duration
}

func ParseDemoConfig(failureEvery, latency string) (DemoConfig, error) {
	var config DemoConfig
	var err error
	if failureEvery != "" {
		config.FailureEvery, err = strconv.ParseUint(failureEvery, 10, 32)
		if err != nil {
			return config, fmt.Errorf("DEMO_FAILURE_EVERY must be a nonnegative integer")
		}
	}
	if latency != "" {
		config.Latency, err = time.ParseDuration(latency)
		if err != nil || config.Latency < 0 || config.Latency > 2*time.Second {
			return config, fmt.Errorf("DEMO_LATENCY must be a duration between 0s and 2s")
		}
	}
	return config, nil
}

type demoBehavior struct {
	config   DemoConfig
	requests atomic.Uint64
}

func (demo *demoBehavior) wrap(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if demo.config.Latency > 0 {
			timer := time.NewTimer(demo.config.Latency)
			defer timer.Stop()
			select {
			case <-timer.C:
			case <-r.Context().Done():
				fail(w, http.StatusRequestTimeout, context.Canceled.Error())
				return
			}
		}
		if every := demo.config.FailureEvery; every > 0 && demo.requests.Add(1)%every == 0 {
			fail(w, http.StatusServiceUnavailable, "Учебная демонстрация отказа")
			return
		}
		next(w, r)
	}
}
