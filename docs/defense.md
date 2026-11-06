# Ответы для защиты Taskboard

Памятка объясняет решения именно этого проекта. Основа ответа — путь запроса,
назначение каждого компонента и поведение при отказах. Формулировки можно
сказать вслух; команды и исходники позволяют показать то же самое на практике.

## Рассказ о проекте на одну минуту

«Taskboard — небольшой трекер задач. Фронтенд написан на React, бэкенд — на Go,
постоянные данные хранятся в PostgreSQL. Пользователь может создать, посмотреть,
изменить и удалить задачу. Собранный React и REST API отдаёт один Go-сервис;
Node нужен для сборки, а не для запуска в кластере.

Приложение работает в minikube. Его реплики управляются Deployment, стабильную
точку доступа предоставляет Service. PostgreSQL использует StatefulSet и PVC,
миграции запускаются отдельным Job. Конфигурация передаётся через env.

Для наблюдаемости приложение экспортирует Go- и бизнес-метрики на внутреннем
порту, а JSON-логи пишет в stdout. VictoriaMetrics собирает метрики по pod SD,
Vector читает контейнерные логи и отправляет их в VictoriaLogs. Можно показать
масштабирование, сохранение задач, поиск логов и реакцию SLI на задержки и ошибки.
Это учебная одноузловая установка, поэтому она не обеспечивает высокую доступность
при отказе самой ноды».

## Архитектура и выбор технологий

**Почему Go.** «У приложения небольшая предметная область, поэтому достаточно
net/http, database/sql и явных SQL-запросов. Получается понятный бинарь и немного
компонентов, что удобно для инфраструктурных экспериментов. Пул соединений,
HTTP- и SQL-таймауты заданы явно. Горутины позволяют конкурентно обслуживать запросы».

**Почему простой React.** «Нужны форма и список задач. Функциональных компонентов
и hooks достаточно; отдельный UI-фреймворк не нужен. Vite собирает статические
файлы. API и страница имеют один origin, поэтому не нужна отдельная CORS-настройка».

**Почему PostgreSQL.** «Он требуется заданием и подходит для структурированных
задач: есть ограничения полей, транзакции и SQL. Данные не привязаны к конкретной
реплике Go. ORM для одной сущности усложнил бы понимание происходящего».

**Как проходит создание задачи.** «React отправляет POST /api/tasks с JSON.
Go проверяет Content-Type, размер тела, поля и допустимый статус, выполняет
параметризованный INSERT и получает запись через RETURNING. После успеха
увеличивается бизнес-счётчик, клиент получает 201 и задачу. Middleware учитывает
HTTP-код и длительность, записывает JSON-событие с request.id».

Task содержит id, title, description, status, created_at, updated_at.
Статусы: todo, doing, done. Есть GET списка/задачи, PUT и DELETE. БД назначает ID.
SQL использует параметры `$1`, `$2`, а не конкатенацию пользовательского текста.
Проверки есть в Go и ограничениях БД. Список ограничен 500 записями; авторизации нет.

**Как масштабируется.** «Веб-процессы не хранят задачи и сессии локально, поэтому
реплики работают с общей БД. Но у каждой есть собственный пул до 10 соединений:
три реплики могут использовать до 30 соединений приложения. Увеличение replicas
требует учитывать возможности PostgreSQL».

**Миграции.** «Команда taskboard migrate использует тот же образ и DATABASE_URL.
Версии SQL встроены в бинарь и учитываются в schema_migrations. Транзакционный
advisory lock защищает от параллельного применения; SQL и запись версии выполняются
в транзакции. Уже применённая миграция повторно не выполняется. Скрипт deploy
дожидается Job до запуска приложения. Kubernetes сам не задаёт такую зависимость
между произвольными Deployment и Job».

Исходники: [HTTP и валидация](../services/taskboard/internal/taskboard/http.go),
[SQL и миграции](../services/taskboard/internal/taskboard/store.go),
[настройка процесса](../services/taskboard/cmd/taskboard/main.go),
[Dockerfile](../services/taskboard/Dockerfile).

## Двенадцать факторов на примерах проекта

На вводный вопрос: «Для меня соответствие 12 факторам — это конкретные свойства
приложения: переносимая конфигурация, отсутствие привязки к локальному диску
веб-процесса, отдельные сборка и административные операции, управляемый жизненный
цикл. Одного Dockerfile для этого недостаточно».

| Фактор | Что показать в проекте |
|---|---|
| Codebase | Один Git-репозиторий, общее приложение в services/taskboard, короткие feat/fix-ветки и PR в master |
| Dependencies | go.mod/go.sum и package-lock.json, npm ci, отдельные build stages |
| Config | DATABASE_URL, PORT, LOG_LEVEL, METRICS_ADDR и настройки демонстрации через env; рабочая .env вне Git/ZIP |
| Backing services | PostgreSQL подключается по URL, данные принадлежат БД и её PVC |
| Build, release, run | React/Go собираются заранее; окружение и миграции задают выпуск; при старте сервера сборки нет |
| Processes | Задачи в PostgreSQL, веб-контейнер read-only; потеря реплики не удаляет задачи |
| Port binding | Go сам слушает 8080; отдельный внутренний metrics listener 9090 |
| Concurrency | Масштабирование Deployment, общая БД, отсутствие sticky sessions |
| Disposability | SIGTERM/SIGINT, graceful shutdown с deadline 10 с, SQL/HTTP-таймауты |
| Dev/prod parity | Настоящий PostgreSQL и одинаковые миграции/образ; Compose локально, Kubernetes в лаборатории |
| Logs | JSON stdout; сбор, ротация и хранение вынесены в инфраструктуру |
| Admin processes | Миграции отдельной подкомандой и Job из того же образа |

Это применение принципов [12-Factor App](https://12factor.net/) к коду проекта.
Близость окружений не означает существование production-кластера. Учебные теги
образов hw01/hw02 переиспользуются: для воспроизводимого выпуска нужны уникальные
теги или digest. Stateless относится к приложению, а не к требованию убрать
постоянное состояние у PostgreSQL.

## Kubernetes в проекте

| Ресурс | Назначение |
|---|---|
| Namespace taskboard-lab | Приложение, PostgreSQL, миграции и пробер |
| Deployment taskboard | Управляет числом одинаковых реплик Go и rolling update |
| Service taskboard | ClusterIP:8080, selector app=taskboard, стабильный DNS/адрес |
| StatefulSet postgres | Одна БД со стабильным именем postgres-0 и отдельным хранилищем |
| Headless Service postgres | DNS-доступ к PostgreSQL; ClusterIP None |
| PVC | Данные PostgreSQL переживают замену pod'а; отдельные PVC есть у TSDB и логового хранилища |
| Job taskboard-migrate | Одноразовое применение миграций |
| ConfigMap / Secret | Обычные настройки / пароль и DATABASE_URL, передаваемые процессу через env |
| Namespace monitoring | VictoriaMetrics Single, установленный Helm-чартом |
| Namespace logging | VictoriaLogs Single и Vector |
| DaemonSet vector-taskboard | По одному сборщику логов на подходящую ноду |
| ServiceAccount и RBAC | Права VictoriaMetrics на pod discovery; права Vector на метаданные Kubernetes |
| Deployment taskboard-prober | Синтетические HTTP-проверки, метрики на 9091 |
| Job taskboard-slo-load | Ограниченная по времени демонстрационная нагрузка |

«Deployment через ReplicaSet поддерживает желаемое число pod'ов и заменяет их
при обновлении. Service обнаруживает подходящие готовые endpoints по selector.
Приложению не нужно знать адреса всех реплик». Механизмы:
[Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/),
[Service](https://kubernetes.io/docs/concepts/services-networking/service/).

**Контейнер и Pod.** «Контейнер запускает процесс из образа. Pod — единица
размещения Kubernetes; его контейнеры имеют общую сеть. Поэтому postgres-exporter
может подключаться к PostgreSQL по localhost:5432: они находятся в одном Pod,
экспортёр слушает другой порт — 9187. Сам Go-сервис находится в других pod'ах
и подключается через DNS postgres».

**Readiness, liveness, startup.** «/healthz подтверждает, что HTTP-процесс жив;
/readyz проверяет БД и версию схемы. Неуспешная readiness исключает pod из обычных
Service endpoints, liveness после порога приводит к перезапуску контейнера,
startup защищает старт от ранних проверок. Отказ БД не должен заставлять
перезапускаться все исправные Go-процессы». См.
[Kubernetes probes](https://kubernetes.io/docs/concepts/workloads/pods/probes/).

**Что происходит после kubectl apply.** «Клиент отправляет желаемое состояние
в API server, оно сохраняется в etcd. Контроллер Deployment создаёт ReplicaSet,
тот — Pod-объекты. Scheduler назначает ноды, kubelet через runtime запускает
контейнеры и сообщает статус через API. Сеть настраивается компонентами ноды;
в этом стенде Service-трафик обслуживает kube-proxy, DNS — CoreDNS.
Контроллеры, scheduler и kubelet не пишут напрямую в etcd».
[Компоненты Kubernetes](https://kubernetes.io/docs/concepts/overview/components/).

**Requests и limits.** «Requests учитываются при планировании, limits ограничивают
потребление. CPU limit может привести к throttling, memory limit — к OOM kill.
Избыточные requests могут оставить pod в Pending. Это проверяется через describe
и Events, а не только через логи приложения».

**Пределы масштабирования.** «Три реплики на одной ноде помогают при замене
контейнера и распределении нагрузки, но не при отказе ноды. Одна PostgreSQL —
отдельная точка отказа. StatefulSet и PVC сами по себе не добавляют репликацию
БД и резервные копии».

`kubectl port-forward service/taskboard` выбирает один pod: это удобный доступ
для демонстрации, а не доказательство равномерной балансировки. Внутри кластера
Service работает с соединениями, поэтому keep-alive тоже влияет на распределение.

## Логирование и безопасность

«Go log/slog с JSONHandler пишет по событию в строку stdout. Runtime сохраняет
поток в файлы ноды. Vector kubernetes_logs снимает контейнерную обёртку, VRL
разбирает JSON приложения и добавляет namespace, pod, container, node. Затем
Elasticsearch bulk sink с gzip отправляет записи через Service в VictoriaLogs.
Встроенный UI доступен по /select/vmui/ через loopback port-forward».

Основные поля stdout: timestamp, level, message, service.name. HTTP-событие
содержит request.id, method, path, route, status, duration_ms. Успех — info,
4xx — warn, 5xx — error. JSON экранирует переносы строк, сохраняя одно событие
на строку. HTTP X-Request-ID генерируется сервером; входному заголовку не доверяют.

При приёме timestamp превращается в `_time`, message — в `_msg`.
Числовые поля VictoriaLogs отображает строками, но LogsQL агрегирует их как числа.
В stream fields оставлены сервис и Kubernetes-метаданные; request.id — поле
события, чтобы не создавать отдельный поток для каждого запроса.

**Почему DaemonSet.** «Сборщик отделён от бизнес-кода, не нужен sidecar у каждой
реплики. Он обнаруживает новые pod'ы при масштабировании. Приложение продолжает
писать stdout независимо от конкретного логового хранилища».

**Если VictoriaLogs недоступна.** «Есть повторы отправки, checkpoints и дисковый
буфер Vector примерно 256 MiB на ноде. При заполнении включается backpressure.
Это помогает пережить короткий сбой, но буфер конечен: ротация исходных файлов
или потеря ноды могут привести к потерям. Exactly-once не гарантируется,
повторная отправка может дать дубли».

**Если JSON повреждён.** «В remap включены drop_on_error и drop_on_abort:
невалидные записи не попадают в VictoriaLogs. Поэтому отсутствие записи нужно
проверять по всей цепочке: stdout, обнаружение pod, файлы и ошибки Vector,
доставка, затем запрос и временное окно в VictoriaLogs».

**Рестарт и старые логи.** «Позиции чтения и буфер находятся в hostPath, поэтому
переживают замену pod'а Vector на этой ноде. При старте файлы старше 600 с по
времени изменения могут не читаться. Это настройка файлов, а не строгий фильтр
возраста каждой записи. Логи VictoriaLogs имеют retention 1 день и PVC 1Gi».

**Какие данные защищены.** «Приложение не логирует пароли, DATABASE_URL,
тела запросов, query-параметры и SQL-параметры. Ошибки SQL наружу заменяются
общим сообщением. Vector фильтрует Taskboard, mounts логов read-only,
Docker socket не смонтирован. Права сервисных аккаунтов ограничены задачей».

**Ограничения защиты.** «Vector читает hostPath и работает от root для доступа
к файлам ноды. Фильтр источника — не жёсткая изоляция от всех файлов в mount.
Namespace не является сетевым firewall; NetworkPolicy в этом стенде нет.
ClusterIP скрывает сервис от обычного внешнего доступа, но не от других pod'ов.
Secret отделяет секретную конфигурацию, однако base64 — не шифрование: нужны
права доступа и отдельная настройка encryption at rest».
[Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/).

request.id есть у HTTP-события, но отдельный database_request_failed сейчас
не получает тот же ID. Поэтому это корреляция HTTP-запроса, не полноценная
распределённая трассировка всех событий операции.

Конфигурация цепочки: [Vector](../deploy/logging/vector-config.yaml),
[его RBAC и mounts](../deploy/logging/vector.yaml),
[JSON-логгер](../services/taskboard/internal/logging/logger.go).

## Частые дополнительные вопросы

**Логи и метрики.** «Метрики показывают, насколько часто и насколько долго
происходит проблема; лог помогает разобрать конкретный запрос. VictoriaMetrics —
TSDB и MetricsQL; VictoriaLogs — события и LogsQL. Это разные хранилища».

**Service discovery.** «Аннотация сама не включает мониторинг. В Helm values
есть scrape config и pod SD, а RBAC разрешает читать pod'ы. Relabeling оставляет
Running pod'ы с нужной аннотацией и единственный объявленный metrics port.
Поэтому добавленная реплика автоматически становится отдельным target».

**Почему metrics listener отдельно.** «На 9090 доступны Go/process, HTTP и
бизнес-метрики; публичный API-порт 8080 /metrics не обслуживает. Доступ к БД
не нужен для выдачи runtime-метрик. PostgreSQL экспортируется готовым sidecar».

**SLI, SLO, SLA.** «SLI — фактическое отношение хороших событий ко всем событиям.
SLO — внутренняя цель; SLA — внешнее обещание с последствиями нарушения.
В ДЗ №5 используются успешность HTTP, доля ответов ≤250 мс, успешность создания
и хорошие минуты пробера. Целевое окно 30 дней, в видео — 1 минута.
Быстрые 503 не делают сервис работоспособным, поэтому latency оценивается вместе
с успешностью. Отсутствие запросов не превращается в 100% доступности».

**Что проверено.** «make check запускает fmt/vet/race-тесты и сборку React.
Интеграционные тесты выполняют CRUD с настоящей БД, проверяют ошибки и счётчики.
В кластере проверяются готовность, масштабирование и discovery. Логи проверяются
по свежему request.id, а не по факту наличия старых записей в хранилище».

**Что улучшить для эксплуатации.** «Сначала авторизация и TLS, резервное
копирование БД с проверкой восстановления, репликация и несколько нод.
Затем сетевые политики, управление секретами, уникальные версии образов,
обоснованный retention и дисковые лимиты, алерты по пользовательским SLI.
Эти возможности не стоит приписывать текущему учебному стенду».

## Что показать в терминале

Все команды привязаны к учебному context; чтение Secret в демонстрацию не включается.

```sh
kubectl --context tbank-sre-hw02 -n taskboard-lab get pods,deploy,sts,svc,pvc,job
kubectl --context tbank-sre-hw02 -n taskboard-lab describe deployment taskboard
kubectl --context tbank-sre-hw02 -n taskboard-lab logs deployment/taskboard --tail=5
kubectl --context tbank-sre-hw02 -n logging get pods,ds,svc,pvc
kubectl --context tbank-sre-hw02 -n logging logs ds/vector-taskboard --tail=10
kubectl --context tbank-sre-hw02 -n monitoring get pods,svc,pvc
```

Через `make logging-forward` открыть http://127.0.0.1:9428/select/vmui/:

```logsql
_time:30m service.name:taskboard level:warn | limit 10
```

Через `make monitoring-forward` открыть http://127.0.0.1:8428/vmui/:

```promql
up{job="taskboard"}
sum(rate(taskboard_http_requests_total{job="taskboard"}[1m]))
```

Перед защитой полезно пройти один CRUD в UI и найти соответствующее HTTP-событие,
объяснить отсутствие локальных данных веб-процесса и показать, где задан каждый
из env, probes, PVC, scrape config и буфер Vector.
