# Trunk-based development

Один trunk и короткие ветки: `trunk → codex/задача → PR → squash → trunk`.
Не держим отдельную ветку на весь курс или каждую домашку: приложение эволюционирует
в `services/taskboard`, материалы заданий остаются в `homework/NN`.

Текущая основная ветка GitHub — `master`. Рабочая ветка первого задания —
`codex/hw01-taskboard`. Можно оставить имя `master`: trunk-based development не
зависит от имени ветки. Если переименовывать в `main`, сначала изменить default
branch в GitHub, затем обновить локальные checkout и правила защиты.

1. Обновить trunk: `git switch master && git pull --ff-only`.
2. Создать ветку: `git switch -c codex/краткое-название`.
3. Сделать небольшой законченный срез; запустить `make check`, `make up`, `make integration`.
4. Открыть PR к trunk. Проверки `checks` и `integration` должны быть зелёными.
5. Squash merge. После сдачи отметить trunk тегом `hw01-v1`, не менять содержимое тега.

Для следующей домашней работы добавить `homework/02/README.md` и `Отчёт.md`,
изменять общее приложение небольшими PR. Несовместимые изменения БД проводить
поэтапно: сначала добавить новое, переключить код, затем отдельным PR удалить старое.

## Защита trunk в GitHub

В Settings → Rules → Rulesets включить для default branch:
require pull request; require checks `checks` и `integration`; запрет force push
и удаления. Для личного учебного репозитория достаточно PR без обязательного чужого
approve; разрешить squash merge, включить автоматическое удаление веток.
Эти настройки серверные: файлы репозитория сами их не включают.

За основу соглашений взяты локальные `neformeet` (`/home/arseniizxc/trunk`):
Makefile-команды, Go/PostgreSQL, миграции отдельной подкомандой, bounded pool,
корректная остановка, React/Vite и проверки перед слиянием. Исходники и конфиги
продуктового проекта не копируются.
