FROM node:24.16.0-alpine AS frontend
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM golang:1.26.4-alpine AS backend
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /taskboard ./cmd/taskboard

FROM alpine:3.23.3
WORKDIR /srv
COPY --from=backend /taskboard /srv/taskboard
COPY --from=frontend /web/dist /srv/web/dist
ENV PORT=8080 STATIC_DIR=/srv/web/dist LOG_LEVEL=INFO
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/srv/taskboard"]
