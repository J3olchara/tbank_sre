# Домашняя работа 05 — SLI, SLO и SLA

Taskboard: три SLI на метриках ДЗ №4, Go-пробер UI/API, RBSLO/TBSLO,
внутренние SLO и учебный SLA, графики в настоящей vmui VictoriaMetrics.
Для сдачи: `artifacts/homework-05.zip`, включая `Отчёт.md` и `screencast.mp4`.

## Развёртывание

Нужны Docker, minikube, kubectl, Helm, Bash и Python 3. На Linux amd64:

```sh
bash scripts/install_k8s_tools.sh
bash scripts/install_helm.sh
export PATH="$PWD/.tools/bin:$PATH"
make k8s-start k8s-build k8s-deploy
make k8s-scale REPLICAS=3
make monitoring-install
make slo-install slo-validate slo-render
make slo-load-start
make monitoring-forward                  # отдельный терминал, localhost:8428
```

В другом терминале: `python3 scripts/check_slo.py --phase healthy --timeout 150`.
Новому проберу нужна полная здоровая минута с попаданием в минутную границу TBSLO.
Используется context `tbank-sre-hw02`, приложение — `taskboard-lab`, TSDB — `monitoring`.
`PROFILE` должен совпадать у всех команд. Сохраняйте `homework/02/.env`, пока
используется существующий PostgreSQL PVC. Рабочие пароли не входят в ZIP.

`slo-install` оставляет официальный chart VictoriaMetrics **0.49.0** и pod SD
ДЗ №4, добавляя values с retention **35 дней** вместо 1d. Повторный
`monitoring-install` вернёт 1d; после него повторить `slo-install`. Retention
не восстанавливает удалённую историю. Образ содержит три Go-команды:
приложение, пробер и генератор временной CRUD-нагрузки.
Для TBSLO 30d/1m/5s лимит `search.maxPointsSubqueryPerTimeseries` увеличен
до 600000: стандартные 100000 не вмещают примерно 518600 точек этого подзапроса.

## Графики и изменения поведения

Открыть **http://127.0.0.1:8428/vmui/**. В `queries.json` находятся готовые ссылки
`demo_vmui_url` с линиями SLI/SLO/SLA и формулы для **30d**. Генерация:
`python3 scripts/slo_queries.py`. В vmui выбрать Last 5 minutes, автообновление 5s.
Для компактной легенды: Settings → Custom Legend Format `{{series}}`, Group Legend By Ungrouped.

Демонстрационное окно — **1m**. Общий `demo_sla_compliance` показывает выполнение
порогов на этом окне, а не заключение о месячном SLA. Без запросов RBSLI не определён.
`monthly_window_ready=0` означает, что полных 30 суток ещё нет: формальный
месячный статус SLA в таком случае отсутствует.
Проверить формулы 30d и этот предохранитель: `python3 scripts/check_slo.py --monthly`.

```sh
make slo-mode MODE=slow                   # задержка API 750 мс
python3 scripts/check_slo.py --phase slow
make slo-mode MODE=errors                 # API отвечает 503 до обращения к SQL
python3 scripts/check_slo.py --phase errors
make slo-mode MODE=healthy                # восстановление обязательно
python3 scripts/check_slo.py --phase recovery --timeout 180
make slo-load-stop
```

Режим меняется только env в Deployment, с rolling update. Без `DEMO_LATENCY` и
`DEMO_FAILURE_EVERY` вмешательство выключено. Пробер каждые 5 с читает `/` и
`/api/tasks`, общий timeout 2 с; БД не меняет. Он проверяет HTML/JSON без исполнения
JS и находится внутри minikube, поэтому не измеряет Интернет/внешний Ingress.

## Повторная запись

Нужны Xvfb, xterm, xdotool, ffmpeg/ffprobe и Playwright Chromium:

```sh
sudo apt-get install -y xvfb xterm xdotool ffmpeg fonts-dejavu-core
npm install --prefix .tools/hw05-browser playwright@1.65.0 --no-audit --no-fund
PLAYWRIGHT_BROWSERS_PATH="$PWD/.tools/hw05-browser/browsers" \
  .tools/hw05-browser/node_modules/.bin/playwright install --with-deps chromium
export NODE_PATH="$PWD/.tools/hw05-browser/node_modules"
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.tools/hw05-browser/browsers"
python3 scripts/record_hw05.py
make archive-hw05
```

Скрипт захватывает настоящий X11-экран xterm/Chromium 1920×1200 без ускорения.
Он использует собственный loopback port-forward 18429 и display :96;
`RECORDING_DISPLAY` позволяет выбрать другой. После записи возвращает healthy
и удаляет только нагрузочный Job. Пробер, TSDB, БД/PVC продолжают работать.

Нагрузочный Job ограничен 30 минутами. Он удаляет только свои задачи с повтором
DELETE при 503; при прерывании или длительном отказе может остаться задача с названием
`SLO demo: temporary task`, о чём генератор пишет в лог. При обычном deploy
приложения нагрузка не запускается.

Упаковщик требует видео до 7 минут, подтверждения четырёх фаз, PNG и Helm render.
Скриншоты и JSON проверок не заменяют видеозапись.

## Проверки

`make check`, `make integration`, `make k8s-validate slo-validate`, `make slo-check`.
Для точных бизнес-счётчиков ДЗ №4 остановить нагрузку и временно уменьшить
Deployment пробера до 0: его GET меняют счётчик просмотров. Пробросить API/metrics
одного pod'а на 18081/19090 и запустить
`TASKBOARD_URL=http://127.0.0.1:18081 TASKBOARD_METRICS_URL=http://127.0.0.1:19090 make integration`.
После теста вернуть проберу 1 реплику. Для обычного CRUD без metrics URL это не требуется.
