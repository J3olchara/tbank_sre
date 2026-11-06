// Package logging defines the application's stdout JSON schema.
package logging

import (
	"io"
	"log/slog"
	"strings"
)

func New(output io.Writer, level slog.Leveler, service string) *slog.Logger {
	handler := slog.NewJSONHandler(output, &slog.HandlerOptions{
		Level: level,
		ReplaceAttr: func(groups []string, attr slog.Attr) slog.Attr {
			if len(groups) == 0 {
				switch attr.Key {
				case slog.TimeKey:
					attr.Key = "timestamp"
				case slog.MessageKey:
					attr.Key = "message"
				case slog.LevelKey:
					attr.Value = slog.StringValue(strings.ToLower(attr.Value.String()))
				}
			}
			return attr
		},
	})
	return slog.New(handler).With("service.name", service)
}
