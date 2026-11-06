# Домашняя работа 04 — VictoriaMetrics и метрики приложения

## Решение

Taskboard экспортирует метрики Go и пять бизнес-счётчиков на отдельном
внутреннем порту 9090. PostgreSQL экспортируется sidecar-контейнером
postgres-exporter на 9187. VictoriaMetrics Single установлен через официальный
Helm-чарт и сам опрашивает pod'ы по Kubernetes service discovery и аннотациям
`prometheus.io/*`. Отдельный vmagent и Grafana для этого решения не нужны.

Для сдачи — `artifacts/homework-04.zip`: исходники приложения, Dockerfile,
манифесты Kubernetes, Helm values и полный Helm render, отчёт и настоящий
скринкаст `screencast.mp4`.

## Подготовка и запуск

Нужны Docker, minikube, kubectl, Helm и Python 3. В архиве сохранена структура
репозитория, команды ниже выполняются из корня распакованного архива.
На Linux amd64 можно установить бинарники с проверкой SHA-256:

```sh
bash scripts/install_k8s_tools.sh
bash scripts/install_helm.sh
export PATH="$PWD/.tools/bin:$PATH"

make k8s-start k8s-build k8s-deploy
make k8s-scale REPLICAS=3
make monitoring-install
make monitoring-status
```

Используются **только** профиль/context `tbank-sre-hw02`, namespace приложения
`taskboard-lab` и namespace мониторинга `monitoring`. Другой профиль задаётся
через `PROFILE`, одинаково для всех команд. Перед обновлением нужно сохранить
`homework/02/.env`, если используется существующий PVC PostgreSQL.
Пароль генерируется автоматически; в архиве находится лишь шаблон Secret.

Helm-релиз `vm-single`: chart `vm/victoria-metrics-single` **0.49.0**, образ
VictoriaMetrics **v1.154.0**, retention **1 день**, PVC с запросом **1Gi**.
Параметры — в `deploy/monitoring/values.yaml`. Release устанавливается командой
`helm upgrade --install` с явными `--kube-context` и `--namespace`.

Основа: [первые два шага официального руководства](https://docs.victoriametrics.com/guides/k8s-monitoring-via-vm-single/).
В этом варианте используется встроенный scraper VictoriaMetrics Single.

## Проверка

В одном терминале:

```sh
make monitoring-forward   # оставить работать, localhost:8428
```

Во втором (оба порта выбирают один и тот же pod для точного сравнения счётчиков):

```sh
kubectl --context tbank-sre-hw02 -n taskboard-lab \
  port-forward deployment/taskboard 18081:8080 19090:9090
```

В третьем:

```sh
TASKBOARD_URL=http://127.0.0.1:18081 \
TASKBOARD_METRICS_URL=http://127.0.0.1:19090 make integration
make monitoring-check

curl --get --data-urlencode 'query=up' http://127.0.0.1:8428/api/v1/query
curl --get --data-urlencode 'query=pg_up' http://127.0.0.1:8428/api/v1/query
curl --get --data-urlencode 'query=go_goroutines{job="taskboard"}' http://127.0.0.1:8428/api/v1/query
curl --get --data-urlencode 'query=sum(taskboard_tasks_created_total)' http://127.0.0.1:8428/api/v1/query
curl http://127.0.0.1:8428/api/v1/label/__name__/values
curl http://127.0.0.1:8428/targets
```

Проверка OpenMetrics (ответ заканчивается `# EOF`):

```sh
curl -H 'Accept: application/openmetrics-text; version=1.0.0' http://127.0.0.1:19090/metrics
```

Простой curl без Accept получает совместимый Prometheus text. Проверочный
port-forward к 9090 — временный доступ для разработчика; в API/UI Service
экспортируется только порт 8080, где `/metrics` возвращает 404. Порты 9090/9187
не опубликованы через Service NodePort, Ingress или порты хоста.

`make monitoring-check` проверяет три различных pod-таргета приложения и один
PostgreSQL, значения `up=1`, `pg_up=1`, наличие Go/process/SQL-метрик, ненулевые
пять бизнес-счётчиков после CRUD и свежесть данных. Ожидает новые данные до 90 с.
При другом числе реплик: `python3 scripts/check_monitoring.py --replicas N`.

Чтобы подтвердить динамическое обнаружение:

```sh
make k8s-scale REPLICAS=4
python3 scripts/check_monitoring.py --replicas 4
make k8s-scale REPLICAS=3
make monitoring-check
```

Конфигурация scrape при масштабировании не меняется. `up` — HTTP-доступность
таргета, `pg_up` — доступ экспортёра к самой PostgreSQL.

## Сборка, тесты и скринкаст

```sh
make check
make k8s-validate
make monitoring-render
python3 scripts/record_hw04.py
make archive-hw04
```

Запись требует Xvfb, xterm, ffmpeg и Go для интеграционного теста:
`sudo apt-get install -y xvfb xterm ffmpeg fonts-dejavu-core`.
Скрипт записывает настоящее выполнение команд в xterm через X11/ffmpeg;
видео не генерируется из текста и не ускоряется. Для записи использует
свободные loopback-порты 18428, 18082, 19092; создаёт и останавливает собственные
port-forward. Запущенные minikube, приложение и Helm-релиз должны существовать.
Во время демонстрации число реплик меняется 3 → 4 → 3; данные БД не удаляются.

Свой скринкаст можно упаковать командой:
`python3 scripts/package_hw04.py --video /путь/запись.mp4`.
Упаковщик требует видео длительностью до 7 минут и полный Helm render,
исключает рабочие `.env`, node_modules и сборки фронтенда.

## Диагностика и остановка

```sh
kubectl --context tbank-sre-hw02 -n monitoring get pods,svc,pvc
kubectl --context tbank-sre-hw02 -n monitoring logs vm-single-0
kubectl --context tbank-sre-hw02 -n taskboard-lab logs postgres-0 -c postgres-exporter
kubectl --context tbank-sre-hw02 -n taskboard-lab get pods -o yaml
```

Аннотации должны находиться в `spec.template.metadata.annotations`.
Наличие аннотаций само по себе не включает scraping: он включён и настроен
в Helm values. Role/RoleBinding дают ServiceAccount мониторинга только
get/list/watch pod'ов namespace приложения. Совпадение аннотированного порта
с declared containerPort устраняет дубли от остальных портов pod'а.

Остановить port-forward: Ctrl+C. Остановить кластер с сохранением данных:
`minikube stop -p tbank-sre-hw02`. Удаление namespace или minikube может удалить
PVC и данные; для обычной остановки оно не требуется.
