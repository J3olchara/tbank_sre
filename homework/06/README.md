# ДЗ №6 — алерты

Нужны Docker, kubectl, minikube и Helm. Команды выполняются из корня репозитория.
Используется только context `tbank-sre-hw02`.

```sh
make k8s-start k8s-build k8s-deploy
make k8s-scale REPLICAS=3
make monitoring-install slo-install
make alerting-test
make alerting-install alerting-validate alerting-render
make alerting-forward
```

Интерфейсы через loopback port-forward:

- vmalert: <http://127.0.0.1:18880/vmalert/groups>
- Alertmanager: <http://127.0.0.1:19093>
- Доставленные webhook-уведомления: <http://127.0.0.1:18085>

В другом терминале запустить `make monitoring-forward`, затем `make alerting-check`.
Проверка сама запускает временную CRUD-нагрузку, переключает healthy → slow → errors →
runtime → healthy, ждёт срабатывания и доставки всех пяти алертов и их resolved.
В конце отключает DEMO-режимы и удаляет нагрузочный Job. Результат — `artifacts/hw06`.

Для новых скриншотов нужен Playwright с Chromium. Указать `NODE_PATH` до установленного
пакета, при необходимости `PLAYWRIGHT_BROWSERS_PATH`, затем:

```sh
python3 scripts/check_alerting.py --screenshots
make archive-hw06
```

Архив `artifacts/homework-06.zip` содержит исходники, конфиги, отчёт, настоящие
скриншоты и результаты проверки. Видео в этом задании не требуется.

Отдельный режим: `make alerting-mode MODE=slow|errors|runtime|healthy`.
После ручной демонстрации: `make alerting-mode MODE=healthy` и `make slo-load-stop`.
