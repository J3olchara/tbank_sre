# T-Bank SRE — домашние работы

Общее приложение: **Go + React + PostgreSQL**, простой трекер задач с REST CRUD.

```sh
make up              # сборка образа, PostgreSQL, миграции, приложение
make integration     # проверка CRUD на работающем приложении
make check           # форматирование, vet, race-тесты, сборка React (Go + Node)
make archive         # artifacts/homework-01.zip для сдачи
make down            # остановить, сохранив данные PostgreSQL
```

Открыть http://localhost:8080. Нужны Docker Engine и Docker Compose.
Если порт занят: `APP_PORT=18080 make up`, затем
`TASKBOARD_URL=http://127.0.0.1:18080 make integration`.

| Каталог | Назначение |
|---|---|
| `services/taskboard` | Исходники приложения для всех домашних работ |
| `homework/01` | Первая домашка: инструкция и отчёт |
| `homework/02` | Minikube: инструкция, отчёт и сценарий скринкаста |
| `deploy/k8s` | Манифесты PostgreSQL, миграций и приложения |
| `docs/development.md` | Trunk-based workflow и правила защиты основной ветки |
| `scripts` | Упаковка исходников |
| `artifacts` | Сгенерированные архивы (не в Git) |

Материалы: [домашка 01](homework/01/README.md), [отчёт](homework/01/Отчёт.md),
[разработка](docs/development.md), [правила кода](AGENTS.md).

## Домашняя работа 02 — minikube

```sh
make k8s-start k8s-build k8s-deploy
make k8s-scale REPLICAS=3
make k8s-forward   # UI: http://127.0.0.1:18080
make archive-hw02  # после записи artifacts/homework-02-demo.mp4
```

[Полная инструкция](homework/02/README.md), [отчёт](homework/02/Отчёт.md),
[сценарий записи](homework/02/Сценарий.md). По умолчанию используется отдельный
профиль `tbank-sre-hw02`; все обращения kubectl явно указывают его context.
