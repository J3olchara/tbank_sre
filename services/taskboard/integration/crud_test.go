//go:build integration

package integration

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"
)

func TestCRUD(t *testing.T) {
	base := os.Getenv("TASKBOARD_URL")
	if base == "" {
		t.Fatal("TASKBOARD_URL is required")
	}
	client := &http.Client{Timeout: 10 * time.Second}
	request := func(method, path, body string, status int) []byte {
		t.Helper()
		req, err := http.NewRequest(method, base+path, strings.NewReader(body))
		if err != nil {
			t.Fatal(err)
		}
		req.Header.Set("Content-Type", "application/json")
		response, err := client.Do(req)
		if err != nil {
			t.Fatal(err)
		}
		defer response.Body.Close()
		data, err := io.ReadAll(response.Body)
		if err != nil {
			t.Fatal(err)
		}
		if response.StatusCode != status {
			t.Fatalf("%s %s: %d want %d: %s", method, path, response.StatusCode, status, data)
		}
		return data
	}
	request("GET", "/healthz", "", 200)
	request("GET", "/readyz", "", 200)
	request("GET", "/", "", 200)
	payload := `{"title":"Проверка ' SQL и <script> React","description":"Интеграционный тест","status":"todo"}`
	data := request("POST", "/api/tasks", payload, 201)
	var created struct {
		ID        int64     `json:"id"`
		Title     string    `json:"title"`
		CreatedAt time.Time `json:"created_at"`
	}
	if err := json.Unmarshal(data, &created); err != nil || created.ID <= 0 || created.CreatedAt.IsZero() {
		t.Fatalf("bad created task: %s", data)
	}
	path := fmt.Sprintf("/api/tasks/%d", created.ID)
	t.Cleanup(func() {
		req, _ := http.NewRequest("DELETE", base+path, nil)
		response, err := client.Do(req)
		if err == nil {
			response.Body.Close()
		}
	})
	data = request("GET", path, "", 200)
	if !bytes.Contains(data, []byte("SQL")) {
		t.Fatal("title lost")
	}
	list := request("GET", "/api/tasks", "", 200)
	var tasks []struct {
		ID int64 `json:"id"`
	}
	if err := json.Unmarshal(list, &tasks); err != nil {
		t.Fatal(err)
	}
	found := false
	for _, task := range tasks {
		if task.ID == created.ID {
			found = true
		}
	}
	if !found {
		t.Fatal("created task missing from list")
	}
	updated := request("PUT", path, `{"title":"Готово","description":"Обновлено","status":"done"}`, 200)
	if !bytes.Contains(updated, []byte(`"status":"done"`)) {
		t.Fatal("update lost")
	}
	request("PUT", path, `{"title":"","status":"todo"}`, 400)
	request("GET", path, "", 200)
	request("DELETE", path, "", 204)
	request("GET", path, "", 404)
	request("DELETE", path, "", 404)
	request("PUT", path, `{"title":"Не существует","status":"doing"}`, 404)
}
