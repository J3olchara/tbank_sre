# Домашняя работа 03 — JSON-логи в VictoriaLogs

Решение использует тот же Taskboard и тот же minikube `tbank-sre-hw02`:
приложение пишет JSON в stdout, Vector DaemonSet читает контейнерные логи
и отправляет их в VictoriaLogs Single. Все четыре LogsQL-запроса действительно
выполнены в vmui, скриншоты находятся в `screenshots/` и встроены в `Отчёт.md`.

## Что сдавать

`artifacts/homework-03.zip` содержит исходники приложения, Kubernetes-манифесты,
Helm values и полный render VictoriaLogs, конфиг Vector, отчёт с четырьмя
скриншотами vmui и JSON с фактическими результатами запросов.

Архив можно загрузить отдельным вложением к решению. Рабочие `.env`, kubeconfig,
токены, браузерные зависимости и бинарники в архив не входят.

## Запуск из репозитория или распакованного архива

Нужны Docker, minikube, kubectl, Helm, Bash и Python 3. Для Linux amd64:

```sh
bash scripts/install_k8s_tools.sh
bash scripts/install_helm.sh
export PATH="$PWD/.tools/bin:$PATH"

make k8s-start             # если существующий учебный профиль остановлен
make k8s-build k8s-deploy
make k8s-scale REPLICAS=3
make logging-install
make logging-status
```

Все kubectl/Helm-команды скриптов явно используют context `tbank-sre-hw02`.
Namespace приложения — `taskboard-lab`, стек логирования — `logging`.
Другие кластеры не используются. Переменная `PROFILE` меняет имя учебного context
и должна быть одинаковой для всех команд. Сохраняйте `homework/02/.env`, пока
используется существующий PVC PostgreSQL.

VictoriaLogs устанавливается официальным Helm chart `victoria-logs-single`
**0.13.11**, образ **v1.53.0**, с retention **1 день** и PVC с запросом **1Gi**.
Vector **0.61.0-alpine** развёрнут отдельным DaemonSet. Полный конфиг находится
в `deploy/logging/vector-config.yaml`, RBAC/volumes/DaemonSet — в `vector.yaml`.

## Доступ к vmui и проверка

В первом терминале:

```sh
make logging-forward     # localhost:9428, оставить работать
```

Открыть **http://127.0.0.1:9428/select/vmui/**. Для VictoriaLogs 1.53 это фактический
путь встроенного UI; сокращённый `/vmui/` не поддерживается сервером.

Во втором терминале:

```sh
make k8s-forward          # localhost:18080, оставить работать
```

В третьем:

```sh
make logging-check        # CRUD и проверка свежего события по request.id
make logging-validate    # server-side dry run манифестов Vector
```

Если используются другие порты:
`VL_URL=http://127.0.0.1:19428 APP_URL=http://127.0.0.1:18083 make logging-check`.
Проверка создаёт тестовую задачу и удаляет её, генерирует 400/404 для фильтра
`level:warn`, дожидается доставки и проверяет четыре запроса из `queries.json`.
Максимальное ожидание — 120 секунд. Пароли и тела запросов не логируются.

Запрос через API для диагностики:

```sh
curl --data-urlencode 'query=_time:30m service.name:taskboard level:warn | limit 10' \
  http://127.0.0.1:9428/select/logsql/query
```

Четыре запроса, их объяснения и настоящие скриншоты — в `Отчёт.md`.
Стандартные поля `timestamp` и `message` при приёме отображаются как `_time`
и `_msg`; остальные поля остаются отдельными полями VictoriaLogs.

## Повторные скриншоты и упаковка

Скриншоты уже входят в репозиторий. Для повторного выполнения запросов в браузере
и создания новых скриншотов:

```sh
npm install --prefix .tools/hw03-browser playwright@1.65.0 --no-audit --no-fund
PLAYWRIGHT_BROWSERS_PATH="$PWD/.tools/hw03-browser/browsers" \
  .tools/hw03-browser/node_modules/.bin/playwright install --with-deps --only-shell chromium

NODE_PATH="$PWD/.tools/hw03-browser/node_modules" \
PLAYWRIGHT_BROWSERS_PATH="$PWD/.tools/hw03-browser/browsers" \
  node scripts/capture_logs_vmui.cjs
make logging-render
make archive-hw03
```

Браузер действительно открывает встроенную vmui, вводит каждый запрос и нажимает
Execute. Скрипт проверяет HTTP 200 и непустые результаты именно выполненного
запроса, сохраняет скриншоты и доказательства в `artifacts/hw03/vmui-queries.json`.
Изображения не генерируются и результаты UI не подменяются.

Упаковщик проверяет PNG и соответствие доказательств четырём запросам,
включает полный Helm render. `Отчёт.md` в корне ZIP ссылается на `screenshots/`
в том же архиве. Для пересборки из распакованного ZIP предварительно повторить
браузерную проверку и `make logging-render`.

## Диагностика и остановка

```sh
kubectl --context tbank-sre-hw02 -n logging get pods,daemonset,svc,pvc
kubectl --context tbank-sre-hw02 -n logging logs daemonset/vector-taskboard
kubectl --context tbank-sre-hw02 -n logging logs statefulset/victorialogs
kubectl --context tbank-sre-hw02 -n taskboard-lab logs deployment/taskboard --tail=10
```

Если логов нет, проверить label `app=taskboard`, namespace, JSON-схему,
доступ к файлам ноды и ошибки Vector. Неструктурированные/старые записи до
обновления JSON-схемы отбрасываются remap-transform; собирается только контейнер
`taskboard`, без логов БД, Vector или иных проектов.

`ignore_older_secs: 600` ограничивает перечитывание старых файлов при старте,
состояние offsets и дисковый буфер лежат в node hostPath `/var/lib/vector-taskboard`.
После исправления конфига повторить `make logging-install`: DaemonSet перезапустится.

Ctrl+C завершает port-forward. `minikube stop -p tbank-sre-hw02` сохраняет данные.
Удаление кластера/namespace с PVC может удалить логи; это не обычная остановка.
