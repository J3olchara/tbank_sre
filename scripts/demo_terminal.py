"""Execute real kubectl commands in the recorded X terminal; never replay output."""
import os
from pathlib import Path
import shlex
import subprocess
import time
import urllib.request

profile = os.environ.get("PROFILE", "tbank-sre-hw02")
k = "kubectl --context " + shlex.quote(profile)
kn = k + " -n taskboard-lab"
state = Path(os.environ["RECORDING_STATE_DIR"])

def section(title):
    print("\033[2J\033[H\033[1;36m" + title + "\033[0m\n", flush=True)
    time.sleep(3)

def command(text, pause=4):
    print("\033[1;32m$ \033[0m", end="", flush=True)
    for char in text:
        print(char, end="", flush=True)
        time.sleep(0.015)
    print(flush=True)
    subprocess.run(["bash", "-c", text], check=True)
    time.sleep(pause)

section("SRE / Домашняя работа 02 — один узел minikube")
command("minikube version", 2)
command(k + " get nodes -o wide", 5)
section("1. Запуск зависимостей: Namespace, ConfigMap, Secret, PostgreSQL")
command(k + " apply -f deploy/k8s/namespace.yaml -f deploy/k8s/configmap.yaml")
command("bash scripts/k8s.sh secret", 2)
command(kn + " apply -f deploy/k8s/postgres.yaml")
command(kn + " rollout status statefulset/postgres --timeout=180s")
section("2. Миграции и запуск Go + React")
command(kn + " apply -f deploy/k8s/migrate.yaml")
command(kn + " wait --for=condition=complete job/taskboard-migrate --timeout=180s")
command(kn + " apply -f deploy/k8s/app.yaml")
command(kn + " rollout status deployment/taskboard --timeout=180s")
section("3. Все pod'ы и ресурсы приложения")
command(kn + " get pods,deploy,statefulset,svc,pvc,job", 8)
section("4. Масштабирование приложения: 1 → 3 реплики")
command(kn + " scale deployment/taskboard --replicas=3")
command(kn + " rollout status deployment/taskboard --timeout=180s")
command(kn + " get pods -o wide", 8)
section("5. Открываем UI через Service Kubernetes")
text = kn + " port-forward service/taskboard 18080:8080 --address=127.0.0.1"
print("$ " + text, flush=True)
with (state / "port-forward.log").open("w") as output:
    process = subprocess.Popen(shlex.split(text), stdout=output, stderr=subprocess.STDOUT)
(state / "forward.pid").write_text(str(process.pid))
for attempt in range(30):
    if process.poll() is not None:
        raise RuntimeError((state / "port-forward.log").read_text())
    try:
        with urllib.request.urlopen("http://127.0.0.1:18080/readyz", timeout=2) as response:
            if response.status == 200:
                break
    except OSError:
        time.sleep(1)
else:
    raise RuntimeError("Port-forward did not become ready")
print((state / "port-forward.log").read_text(), flush=True)
print("\nДалее: создание → редактирование → удаление задачи в React UI.", flush=True)
time.sleep(5)
(state / "terminal.done").touch()
while True:
    time.sleep(1)
