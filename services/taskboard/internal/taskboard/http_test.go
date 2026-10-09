package taskboard

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestInputValidation(t *testing.T) {
	cases := []struct {
		name  string
		input Input
		valid bool
	}{
		{"valid Cyrillic", Input{"  Настроить алерты  ", "Описание", "todo"}, true},
		{"empty title", Input{"  ", "", "todo"}, false},
		{"200 Unicode characters", Input{strings.Repeat("я", 200), "", "done"}, true},
		{"long title", Input{strings.Repeat("я", 201), "", "todo"}, false},
		{"long description", Input{"task", strings.Repeat("я", 2001), "todo"}, false},
		{"unknown status", Input{"task", "", "bad"}, false},
		{"NUL", Input{"task", "a\x00b", "todo"}, false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if got := tc.input.validate(); got != tc.valid {
				t.Fatalf("valid=%v, want %v", got, tc.valid)
			}
		})
	}
}
func TestMalformedRequestsDoNotReachDatabase(t *testing.T) {
	handler := NewHandler(nil, t.TempDir())
	cases := []struct {
		method, path, body, contentType string
		code                            int
	}{
		{"POST", "/api/tasks", "null", "application/json", 400},
		{"POST", "/api/tasks", `{"title":"x","status":"todo","extra":1}`, "application/json", 400},
		{"POST", "/api/tasks", `{"title":"x","status":"todo"} {}`, "application/json", 400},
		{"POST", "/api/tasks", `{"title":"x","status":"todo"}`, "text/plain", 415},
		{"POST", "/api/tasks", strings.Repeat("x", 17000), "application/json", 400},
		{"PUT", "/api/tasks/0", `{}`, "application/json", 400},
		{"GET", "/api/tasks/nope", "", "", 400},
		{"DELETE", "/api/tasks/-1", "", "", 400},
		{"GET", "/api/unknown", "", "", 404},
		{"PATCH", "/api/tasks/1", "", "", 404},
	}
	for _, tc := range cases {
		t.Run(tc.method+tc.path+tc.body[:min(len(tc.body), 30)], func(t *testing.T) {
			req := httptest.NewRequest(tc.method, tc.path, strings.NewReader(tc.body))
			req.Header.Set("Content-Type", tc.contentType)
			rec := httptest.NewRecorder()
			handler.ServeHTTP(rec, req)
			if rec.Code != tc.code {
				t.Fatalf("status %d, want %d: %s", rec.Code, tc.code, rec.Body.String())
			}
		})
	}
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/healthz", nil))
	if rec.Code != 200 {
		t.Fatal(rec.Code)
	}
}
