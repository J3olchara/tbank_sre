package taskboard

import (
	"context"
	"database/sql"
	"embed"
	"fmt"
	"log/slog"
	"time"
)

//go:embed migrations/*.sql
var migrations embed.FS

// Migrate runs once per release, independently of the HTTP process.
func Migrate(ctx context.Context, db *sql.DB) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("migration connection failed")
	}
	defer tx.Rollback()
	if _, err = tx.ExecContext(ctx, "SELECT pg_advisory_xact_lock(731001)"); err != nil {
		return fmt.Errorf("migration lock failed")
	}
	if _, err = tx.ExecContext(ctx, "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"); err != nil {
		return fmt.Errorf("migration metadata failed")
	}
	entries, err := migrations.ReadDir("migrations")
	if err != nil {
		return err
	}
	for _, entry := range entries {
		var exists bool
		if err = tx.QueryRowContext(ctx, "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version=$1)", entry.Name()).Scan(&exists); err != nil {
			return fmt.Errorf("migration lookup failed")
		}
		if exists {
			continue
		}
		content, err := migrations.ReadFile("migrations/" + entry.Name())
		if err != nil {
			return err
		}
		if _, err = tx.ExecContext(ctx, string(content)); err != nil {
			return fmt.Errorf("migration %s failed", entry.Name())
		}
		if _, err = tx.ExecContext(ctx, "INSERT INTO schema_migrations (version) VALUES ($1)", entry.Name()); err != nil {
			return fmt.Errorf("migration recording failed")
		}
		slog.Info("migration_applied", "version", entry.Name())
	}
	return tx.Commit()
}

type Task struct {
	ID          int64     `json:"id"`
	Title       string    `json:"title"`
	Description string    `json:"description"`
	Status      string    `json:"status"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

const columns = "id, title, description, status, created_at, updated_at"

type scanner interface{ Scan(...any) error }

func scanTask(row scanner) (Task, error) {
	var task Task
	err := row.Scan(&task.ID, &task.Title, &task.Description, &task.Status, &task.CreatedAt, &task.UpdatedAt)
	return task, err
}
