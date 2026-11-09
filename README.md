# T-Bank SRE — домашние работы

Общее приложение: **Go + React + PostgreSQL**, простой трекер задач с REST CRUD.

```sh
make up              # сборка образа, PostgreSQL, миграции, приложение
make integration     # проверка CRUD на работающем приложении
make check           # fmt, vet, race, React, JSON Grafana (Go + Node + Python 3)
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

[Памятка для защиты проекта](docs/defense.md): архитектура, 12 факторов,
Kubernetes, логирование, ограничения и команды для демонстрации.

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

## Домашняя работа 04 — метрики и VictoriaMetrics

```sh
make k8s-build k8s-deploy
make k8s-scale REPLICAS=3
make monitoring-install
make monitoring-forward  # TSDB: localhost:8428
```

[Инструкция](homework/04/README.md), [отчёт](homework/04/Отчёт.md),
[сценарий скринкаста](homework/04/Сценарий.md). Метрики Go и пять бизнес-counters
на внутреннем порту 9090, PostgreSQL exporter на 9187, Kubernetes service discovery.
Архив: `make monitoring-render`, запись видео, `make archive-hw04`.

## Домашняя работа 03 — логи и VictoriaLogs

```sh
make k8s-build k8s-deploy
make k8s-scale REPLICAS=3
make logging-install
make logging-forward  # UI: http://127.0.0.1:9428/select/vmui/
```

[Инструкция](homework/03/README.md), [отчёт с четырьмя скриншотами vmui](homework/03/Отчёт.md).
JSON stdout → Vector DaemonSet → VictoriaLogs; архив для сдачи: `make archive-hw03`.

## Домашняя работа 05 — SLI, SLO и SLA

```sh
make k8s-build k8s-deploy
make k8s-scale REPLICAS=3
make monitoring-install slo-install
make slo-load-start
make monitoring-forward  # vmui: http://127.0.0.1:8428/vmui/
```

[Инструкция](homework/05/README.md), [отчёт с графиками](homework/05/Отчёт.md).
Три SLI на HTTP/histogram/бизнес-счётчиках, Go-пробер UI/API и TBSLO по минутам.
Режимы `make slo-mode MODE=slow|errors|healthy` демонстрируют деградацию и восстановление.
После демонстрации вернуть healthy и выполнить `make slo-load-stop`.
Для сдачи: `make slo-render`, `python3 scripts/record_hw05.py`, `make archive-hw05`.

## Домашняя работа 06 — Grafana

```sh
make grafana-install grafana-validate grafana-render
make grafana-forward                  # http://127.0.0.1:3000
# в другом терминале
make grafana-import-postgres grafana-export
```

[Инструкция](homework/06/README.md), [отчёт со скриншотами](homework/06/Отчёт.md).
Дашборд Taskboard: RED, Go runtime, бизнес-метрики и отдельная группа SLA пробера.
PostgreSQL: импортированный dashboard №9628. Источник — VictoriaMetrics.
Для сдачи: `make grafana-record grafana-render archive-hw06`.
