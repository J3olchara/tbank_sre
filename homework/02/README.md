# Домашняя работа 02 — приложение в minikube

## Что сдавать

`artifacts/homework-02.zip`: исходники приложения и Dockerfile, все исходные
Kubernetes-манифесты, скрипты, `Отчёт.md` и `screencast.mp4` (не более 7 минут).
Видео не хранится в Git. `make archive-hw02` требует существующий скринкаст и
проверяет его длительность через ffprobe; архив без видео не считается готовым.

## Подготовка

Docker Engine уже должен работать: `docker version` и `docker info`.
Установка Docker — по [официальной инструкции](https://docs.docker.com/engine/install/).
Не запускайте install-скрипты Docker повторно поверх работающей установки.

Для Linux amd64 доступны проверяемые по SHA-256 бинарники minikube 1.39.0 и kubectl 1.35.0:

```sh
bash scripts/install_k8s_tools.sh
export PATH="$PWD/.tools/bin:$PATH"
```

Другие ОС/архитектуры: [minikube](https://minikube.sigs.k8s.io/docs/start/),
[kubectl](https://kubernetes.io/docs/tasks/tools/).
Понадобятся также Bash, curl и Python 3. Для проверки приложения — Go 1.26.

## Сборка и развёртывание

В корне репозитория **или распакованного архива**:

```sh
make k8s-start                  # одноузловой профиль tbank-sre-hw02
make k8s-build                  # сборка в Docker-демоне minikube, загрузка
make k8s-deploy                 # зависимости → миграции → приложение
make k8s-status
make k8s-scale REPLICAS=3
make k8s-forward                # оставить команду работающей
```

Открыть http://127.0.0.1:18080. В другом терминале:

```sh
TASKBOARD_URL=http://127.0.0.1:18080 make integration
make k8s-validate               # серверная проверка манифестов
```

`PROFILE=другое-имя make k8s-start` создаёт отдельный профиль; то же значение
передавать остальным командам. Все kubectl-команды скрипта явно используют этот
context, поэтому не зависят от текущего context пользователя. Если порт занят:
`APP_PORT=28080 make k8s-forward`.

`k8s-build` выполняет `eval "$(minikube -p tbank-sre-hw02 docker-env)"` в отдельном
shell, `docker build -t tbank-sre-taskboard:hw02 services/taskboard`, затем
`docker save` и `minikube image load` с полученным tar. Это позволяет явно
продемонстрировать загрузку без зависимости от образов внешнего Docker-демона.
При сборке внутри minikube образ уже доступен ноде, поэтому загрузка избыточна,
но включена согласно заданию. Подробнее: [способы загрузки образов](https://minikube.sigs.k8s.io/docs/handbook/pushing/).
Для сборки во внешнем Docker альтернативный путь:

```sh
docker build -t tbank-sre-taskboard:hw02 services/taskboard
minikube -p tbank-sre-hw02 image load tbank-sre-taskboard:hw02
```

В Deployment и Job задан `imagePullPolicy: Never`: нужен именно локальный образ.
PostgreSQL 17.6 скачивается нодой отдельно при первом запуске.

## Что делает deploy

1. `kubectl apply` создаёт Namespace и ConfigMap.
2. Скрипт генерирует случайный пароль в `homework/02/.env`, подставляет его в
   `deploy/k8s/secret.template.yaml` и передаёт Secret в `kubectl apply -f -`.
   Пароль не выводится в терминал, файл не попадает в Git/ZIP.
3. Применяет Service/StatefulSet PostgreSQL и ждёт готовности БД.
4. Применяет Job миграций, ждёт `Complete`.
5. Применяет Service/Deployment приложения, ждёт доступности.

Шаблон Secret с заполнителями входит в архив; рабочие пароли — нет.
При повторном deploy завершённый Job удаляется и запускается снова. Миграции
идемпотентны, данные БД сохраняются. Повторное применение app.yaml возвращает
число реплик к указанному в нём значению 1; затем при необходимости снова scale.
Не удалять `.env`, пока используется существующий PVC: иначе пароль Secret и
пароль пользователя в уже инициализированной БД разойдутся.

## Тренировка kubectl

Архив семинара к запросу не приложен. Взамен добавлен независимый пример
`homework/02/practice.yaml`, на котором можно выполнить основные команды
до развёртывания приложения:

```sh
kubectl --context tbank-sre-hw02 apply -f deploy/k8s/namespace.yaml
kubectl --context tbank-sre-hw02 apply -f homework/02/practice.yaml
kubectl --context tbank-sre-hw02 -n taskboard-lab rollout status deployment/practice-http
kubectl --context tbank-sre-hw02 -n taskboard-lab get pods -o wide
kubectl --context tbank-sre-hw02 -n taskboard-lab describe deployment practice-http
kubectl --context tbank-sre-hw02 -n taskboard-lab logs deployment/practice-http
kubectl --context tbank-sre-hw02 -n taskboard-lab exec deployment/practice-http -- nginx -v
kubectl --context tbank-sre-hw02 -n taskboard-lab scale deployment/practice-http --replicas=2
kubectl --context tbank-sre-hw02 -n taskboard-lab rollout status deployment/practice-http
kubectl --context tbank-sre-hw02 delete -f homework/02/practice.yaml
```

## Запись демонстрации

Можно записать экран своим инструментом по сценарию из `Сценарий.md`.
Либо использовать включённую автоматизацию настоящего X11-экрана на Linux:

```sh
sudo apt-get install -y xvfb xterm ffmpeg xdotool fonts-dejavu-core
npm install --prefix /tmp/taskboard-recorder playwright
PLAYWRIGHT_BROWSERS_PATH=/tmp/taskboard-recorder/browsers \
  /tmp/taskboard-recorder/node_modules/.bin/playwright install --with-deps chromium

# Нужны запущенный minikube и загруженный образ, но namespace taskboard-lab
# должен отсутствовать. Скрипт сам не удаляет существующие данные.
NODE_PATH=/tmp/taskboard-recorder/node_modules \
PLAYWRIGHT_BROWSERS_PATH=/tmp/taskboard-recorder/browsers \
  python3 scripts/record_hw02.py
make archive-hw02
```

Скрипт записывает экран Xvfb через ffmpeg: xterm с реально выполняемыми командами,
затем headed Chromium с реальными действиями в UI через Playwright. Вывод не
подменяется, видео не ускоряется. Сценарий использует порт 18080.
Для упаковки своей записи: `python3 scripts/package_hw02.py --video /путь/запись.mp4`.

## Остановка и диагностика

Ctrl+C завершает port-forward. `minikube stop -p tbank-sre-hw02` останавливает
кластер, сохраняя его данные. `minikube delete -p tbank-sre-hw02` удаляет кластер
**вместе с данными**. Удаление namespace также удаляет PVC; это не обычная остановка.

```sh
kubectl --context tbank-sre-hw02 -n taskboard-lab get events --sort-by=.lastTimestamp
kubectl --context tbank-sre-hw02 -n taskboard-lab logs job/taskboard-migrate
kubectl --context tbank-sre-hw02 -n taskboard-lab logs deployment/taskboard
kubectl --context tbank-sre-hw02 -n taskboard-lab describe pod postgres-0
```

`ErrImageNeverPull` — выполнить k8s-build для нужного профиля. `Pending` у PVC —
проверить `kubectl get storageclass` и аддоны default-storageclass/storage-provisioner.
Для удаления ноды/namespace перед новой записью сначала убедиться, что ценных данных нет.
