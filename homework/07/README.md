# Домашняя работа 07 — Grafana

Taskboard, SLA пробера и импортированный PostgreSQL Exporter dashboard №9628.
Для сдачи: `artifacts/homework-07.zip` с экспортом JSON, отчётом и видео.

## Запуск

Нужны Docker, minikube, kubectl, Helm, Python 3. Используется тот же профиль
`tbank-sre-hw02`, namespaces `taskboard-lab` и `monitoring`. На Linux amd64:

```sh
bash scripts/install_k8s_tools.sh
bash scripts/install_helm.sh
export PATH="$PWD/.tools/bin:$PATH"
# Если стенд из ДЗ №5 уже работает, начать с grafana-install.
make k8s-start k8s-build k8s-deploy
make k8s-scale REPLICAS=3
make monitoring-install slo-install

make grafana-install grafana-validate grafana-render
make grafana-forward                 # отдельный терминал, localhost:3000
```

Логин `admin`. Пароль хранится в Secret `grafana-admin` и первоначально
генерируется в игнорируемом `homework/07/.env`. Посмотреть локально:

```sh
kubectl --context tbank-sre-hw02 -n monitoring get secret grafana-admin \
  -o jsonpath='{.data.admin-password}' | base64 --decode
```

Не публиковать пароль и не включать `.env` в сдачу. Существующий Secret при
повторном install сохраняется; PVC содержит учётную запись Grafana и импортированные
дашборды. Data source и приложение настраиваются автоматически через provisioning.
Отдельные плагины и доступ Grafana к Kubernetes API не нужны.

## PostgreSQL и экспорт

В другом терминале с тем же PATH/context:

```sh
make grafana-import-postgres         # импорт локального JSON через HTTP API
make slo-load-start                  # временный Job со своими CRUD-данными
make grafana-check                   # после 20–30 с накопления rate-метрик
make grafana-export                  # экспорт из работающей Grafana
```

Дашборды: <http://127.0.0.1:3000/d/taskboard-overview> и
<http://127.0.0.1:3000/d/taskboard-postgres>. Источник обоих — VictoriaMetrics,
UID `victoriametrics`, URL внутри кластера `http://vm-single.monitoring.svc.cluster.local:8428`.
`GRAFANA_URL` меняет только loopback-адрес для скриптов, `GRAFANA_PORT` — порт forward.

Можно импортировать PostgreSQL вручную: **Dashboards → New → Import**,
загрузить `deploy/grafana/dashboards/postgres.json`, выбрать папку SRE и Import.
Если он уже есть — Import (Overwrite). Именно этот процесс показан в видео.
Оригинал №9628, SHA256 и перечень изменений сохранены в `deploy/grafana`.

Исходный dashboard приложения генерируется `python3 scripts/grafana_dashboards.py`
с использованием формул ДЗ №5. `make grafana-json-check` проверяет актуальность JSON.
После изменения источника повторить `make grafana-install grafana-export`.
Экспорт для сдачи находится в `homework/07/dashboards`, а не подменяется файлом генератора.

## Показ деградации

```sh
make slo-mode MODE=slow              # задержка API 750 мс: растут перцентили
make slo-mode MODE=errors            # API отвечает 503: падает SLI и SLA пробера
make slo-mode MODE=healthy           # обязательно вернуть нормальное поведение
make slo-load-stop
```

Графики обновляются каждые 5 с. Окно SLI в демонстрации — 1m, месячный SLA — 30d.
Для TBSLO нужен полный интервал хороших минут; восстановление графика занимает
до двух минут. Без request traffic SLI запросов не определён. До 30 суток истории
формальная месячная панель показывает «Нет 30d истории».

## Запись и архив

Для повторения нужны Xvfb, xterm, xdotool, ffmpeg/ffprobe и Playwright Chromium:

```sh
npm install --prefix .tools/hw07-browser playwright@1.65.0 --no-audit --no-fund
PLAYWRIGHT_BROWSERS_PATH="$PWD/.tools/hw07-browser/browsers" \
  .tools/hw07-browser/node_modules/.bin/playwright install --with-deps chromium
export NODE_PATH="$PWD/.tools/hw07-browser/node_modules"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.tools/hw07-browser/browsers"
make grafana-record
make grafana-render archive-hw07
```

Запись настоящего X11/Chromium без ускорения; отдельные loopback forward
13000/18429 и display :95 (`RECORDING_DISPLAY` меняет display).
Скрипт выполняет импорт PostgreSQL в UI, показывает панели и проверяет четыре
фазы healthy/slow/errors/recovery. После записи возвращает healthy и удаляет
только нагрузочный Job. Рабочие БД, VictoriaMetrics, пробер и Grafana остаются.

Архиватор требует настоящее видео до 7 минут, скриншоты, JSON из Grafana,
Helm render и успешные запросы панелей. Секреты, зависимости, MP4 и ZIP не коммитятся.
