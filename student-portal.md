# Student Portal Automation — Implementation Plan

## 1. Цель проекта

Создать локальную систему read-only автоматизации личного кабинета студента магистратуры.

Система должна:

1. Позволять пользователю один раз вручную авторизоваться в браузере.
2. Сохранять Playwright `storage_state` локально.
3. В дальнейшем открывать заданные страницы кабинета без повторного ввода пароля.
4. Получать данные:

   * оценки;
   * расписание;
   * задания;
   * дедлайны;
   * объявления.
5. Преобразовывать данные портала в нормализованный JSON.
6. Сравнивать текущее состояние с предыдущим.
7. Выделять только реальные изменения.
8. Генерировать короткую сводку на русском.
9. Запускаться вручную одной командой.
10. Запускаться автоматически через Hermes cron.
11. Если авторизация истекла — НЕ пытаться логиниться автоматически, а сообщать пользователю о необходимости повторного ручного входа.
12. Никогда не выполнять изменяющих состояние действий в кабинете.

Главный принцип архитектуры:

> Playwright/Python отвечает за браузер, парсинг, состояние и diff.
> Hermes отвечает за расписание, запуск и доставку результата пользователю.

---

# 2. Ограничения безопасности

Это критические требования. Не ослаблять их без явного изменения пользователем.

## Запрещено

Автоматизация не должна:

* хранить пароль пользователя;
* просить пароль через Hermes/Telegram/LLM;
* автоматически вводить пароль;
* автоматически проходить 2FA;
* обходить CAPTCHA;
* обходить anti-bot механизмы;
* отправлять формы;
* менять профиль;
* записываться на курсы;
* регистрироваться на экзамены;
* загружать задания;
* удалять записи;
* совершать платежи;
* подтверждать какие-либо действия.

## Разрешено

Автоматизация может:

* открывать заранее определенные URL;
* читать DOM;
* читать отображаемые пользователю данные;
* сохранять локальные HTML/JSON-снимки;
* сравнивать снимки;
* создавать локальный отчет;
* отправлять текстовую сводку через Hermes.

## Важный секрет

`storage_state.json` является фактически эквивалентом активной пользовательской сессии.

Поэтому:

* никогда не коммитить его в Git;
* хранить только локально;
* добавить в `.gitignore`;
* по возможности выставлять permissions `0600`;
* никогда не выводить содержимое cookies/localStorage в лог;
* никогда не передавать `storage_state.json` Hermes-модели как текст;
* никогда не включать его в bug-report.

---

# 3. Архитектура

Пайплайн должен выглядеть так:

```text
manual login
    ↓
storage_state.json
    ↓
fetch
    ↓
raw HTML
    ↓
parse
    ↓
normalized snapshot.json
    ↓
validate
    ↓
diff with previous snapshot
    ↓
changes.json
    ↓
Russian report
    ↓
Hermes cron
    ↓
Telegram
```

Важно:

**не использовать hash всего HTML как основной механизм обнаружения изменений.**

HTML-хэш допустим только как диагностический fallback.

Основное сравнение должно выполняться по структурированным данным.

Причина: HTML страницы может измениться из-за:

* CSRF-токена;
* session ID;
* timestamp;
* рекламного/аналитического JS;
* случайного DOM ID;
* порядка CSS-классов;
* скрытых элементов.

Это создало бы ложные уведомления.

---

# 4. Предлагаемая структура репозитория

Создать:

```text
student-portal-automation/
│
├── AGENTS.md
├── README.md
├── .gitignore
├── pyproject.toml
│
├── config/
│   ├── portal.example.yaml
│   └── portal.yaml
│
├── secrets/
│   └── storage_state.json
│
├── scripts/
│   ├── login_once.py
│   ├── fetch_pages.py
│   ├── parse_pages.py
│   ├── detect_changes.py
│   └── run_check.py
│
├── src/
│   └── student_portal/
│       ├── __init__.py
│       ├── config.py
│       ├── browser.py
│       ├── auth.py
│       ├── fetcher.py
│       ├── models.py
│       ├── normalize.py
│       ├── diff.py
│       ├── report.py
│       ├── state.py
│       ├── errors.py
│       │
│       └── parsers/
│           ├── __init__.py
│           ├── base.py
│           ├── grades.py
│           ├── schedule.py
│           ├── assignments.py
│           └── announcements.py
│
├── data/
│   ├── latest/
│   ├── state/
│   ├── reports/
│   └── history/
│
├── logs/
│   └── automation.log
│
└── tests/
    ├── fixtures/
    │   ├── grades/
    │   ├── schedule/
    │   ├── assignments/
    │   └── announcements/
    │
    ├── test_auth.py
    ├── test_grades_parser.py
    ├── test_schedule_parser.py
    ├── test_assignments_parser.py
    ├── test_announcements_parser.py
    ├── test_diff.py
    ├── test_state.py
    └── test_report.py
```

---

# 5. `.gitignore`

Минимум:

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/

secrets/
data/
logs/

config/portal.yaml

*.log
.env
```

`portal.example.yaml` должен оставаться в Git.

`portal.yaml` — локальная конфигурация.

---

# 6. Зависимости

Использовать Python 3.11+.

Основные библиотеки:

```text
playwright
beautifulsoup4
lxml
pyyaml
pydantic
filelock
```

Для разработки:

```text
pytest
pytest-cov
ruff
```

Не добавлять тяжелые зависимости без необходимости.

---

# 7. AGENTS.md

Создать жесткие инструкции для Hermes/code-agent:

```markdown
# Student Portal Automation

## Goal

Provide read-only monitoring of the user's university student portal.

## Safety

- Never ask for or store the user's password.
- Authentication is performed manually with scripts/login_once.py.
- Never submit forms.
- Never modify profile information.
- Never enroll or unenroll from courses.
- Never submit assignments.
- Never register for exams.
- Never make payments.
- Never delete anything.
- Never bypass CAPTCHA, 2FA, anti-bot systems, or access controls.
- Treat the portal as read-only.
- If authentication expires, stop and request manual re-authentication.
- storage_state.json is secret and must never be printed or sent to an LLM.
- Do not expose cookies or tokens in logs.

## Normal execution

Run:

python scripts/run_check.py

The command performs:

fetch → parse → validate → diff → report.

## Authentication

If authentication has expired, tell the user:

"Сессия личного кабинета истекла. Выполни локально: python scripts/login_once.py"

Do not attempt automatic login.

## Output

Respond briefly in Russian.

Report only:

- new grades or changed grades;
- schedule changes;
- new assignments;
- deadline changes;
- new announcements;
- authentication problems;
- portal errors.

If nothing changed, say:

"В личном кабинете новых изменений нет."
```

---

# 8. Конфигурация портала

Не зашивать URL и CSS selectors непосредственно в код.

Использовать:

`config/portal.yaml`

Пример:

```yaml
portal:
  name: "University Student Portal"

  login_url: "https://example.edu/login"

  auth:
    authenticated_url_pattern: "/student/"
    authenticated_selector: "nav.student-menu"

    login_url_patterns:
      - "/login"
      - "/signin"

    login_selectors:
      - "form[action*='login']"
      - "input[type='password']"

    challenge_selectors:
      - "iframe[src*='captcha']"
      - ".captcha"

  pages:
    grades:
      enabled: true
      required: true
      url: "https://example.edu/student/grades"
      ready_selector: ".grades-table"

    schedule:
      enabled: true
      required: true
      url: "https://example.edu/student/schedule"
      ready_selector: ".schedule"

    assignments:
      enabled: true
      required: false
      url: "https://example.edu/student/assignments"
      ready_selector: ".assignments"

    announcements:
      enabled: true
      required: false
      url: "https://example.edu/student/announcements"
      ready_selector: ".announcements"

browser:
  headless: true
  timeout_ms: 30000

storage:
  storage_state: "secrets/storage_state.json"
  latest_dir: "data/latest"
  state_dir: "data/state"
  reports_dir: "data/reports"
```

Selectors являются примером.

Не придумывать реальные selectors конкретного университета.

После получения локальных HTML fixtures адаптировать их под настоящий DOM.

---

# 9. Этап 1 — `login_once.py`

Реализовать отдельно от автоматической проверки.

Команда:

```bash
python scripts/login_once.py
```

Алгоритм:

1. Запустить Chromium через Playwright.
2. Использовать `headless=False`.
3. Открыть `login_url`.
4. Вывести пользователю в терминал:

```text
Войди в личный кабинет вручную в открывшемся браузере.
Пароль и 2FA не вводятся через этот скрипт.
```

5. Пользователь самостоятельно выполняет login/2FA/CAPTCHA.
6. Скрипт ждет появления признака успешной авторизации:

   * authenticated selector;
   * либо URL, соответствующего authenticated URL pattern.
7. После успешной авторизации сохранить:

```text
secrets/storage_state.json
```

через Playwright `context.storage_state()`.

8. Выставить файлу права `0600`, если ОС это поддерживает.
9. Не выводить cookies.
10. Закрыть браузер.
11. Вывести:

```text
Авторизация сохранена локально.
Теперь можно выполнить:
python scripts/run_check.py
```

Добавить timeout, например несколько минут, но не пытаться выполнять login вместо пользователя.

---

# 10. Этап 2 — определение статуса авторизации

Создать модуль:

```text
src/student_portal/auth.py
```

Функции примерно:

```python
def is_authenticated(page, config) -> bool:
    ...

def is_login_page(page, config) -> bool:
    ...

def is_challenge_page(page, config) -> bool:
    ...
```

Определение должно использовать несколько сигналов:

* текущий URL;
* password input;
* login form;
* authenticated DOM element;
* CAPTCHA/challenge markers.

Нельзя полагаться только на URL.

При обнаружении login page вернуть специальное состояние:

```text
REAUTH_REQUIRED
```

Сообщение:

```text
Сессия личного кабинета истекла. Выполни локально:
python scripts/login_once.py
```

Не пытаться автоматически восстанавливать сессию.

---

# 11. Этап 3 — Fetcher

Создать:

```text
fetcher.py
scripts/fetch_pages.py
```

`fetch_pages.py` должен:

1. Проверить наличие `storage_state.json`.
2. Если его нет:

```text
REAUTH_REQUIRED
```

3. Запустить Chromium.
4. Создать context с сохраненным storage state.
5. Последовательно открыть URL из `portal.yaml`.
6. Использовать прямую навигацию по URL.

Не надо кликать по меню кабинета, если страницу можно открыть напрямую.

Использовать:

```text
wait_until="domcontentloaded"
```

и затем ждать `ready_selector`.

Не полагаться исключительно на `networkidle`, потому что SPA может постоянно выполнять фоновые запросы.

---

# 12. Проверка авторизации после каждого перехода

После загрузки каждой страницы:

```text
navigate
↓
check login/challenge
↓
wait ready selector
↓
save page
```

Если обнаружен login page:

* прекратить весь pipeline;
* не обновлять saved state;
* вернуть `REAUTH_REQUIRED`.

Если обнаружена CAPTCHA/challenge:

* прекратить работу;
* сообщить пользователю;
* не пытаться ее обходить.

---

# 13. Сохранение HTML

На первом этапе сохранять HTML:

```text
data/latest/grades.html
data/latest/schedule.html
data/latest/assignments.html
data/latest/announcements.html
```

Использовать atomic write:

```text
temporary file
→ fsync/close
→ rename
```

Нельзя оставлять наполовину записанный HTML.

HTML содержит потенциально персональные данные, поэтому весь `data/` должен быть исключен из Git.

---

# 14. Transactional fetch

Очень важно исключить частичное обновление.

Получать страницы сначала во временную директорию:

```text
data/.fetch-temp-<uuid>/
```

Только если все `required: true` страницы успешно загружены:

```text
temp → data/latest
```

Если одна обязательная страница упала:

* старый `latest` не заменять;
* baseline не менять;
* diff не выполнять;
* сообщить об ошибке.

Это предотвратит ложные уведомления.

---

# 15. Этап 4 — Parser architecture

Парсеры должны быть независимы от Playwright.

На вход:

```python
html: str
```

На выход:

нормализованные Python/Pydantic models.

Это позволит тестировать парсинг на HTML fixtures без доступа к университетскому сайту.

Создать:

```python
class BaseParser:
    def parse(self, html: str):
        raise NotImplementedError
```

Реализации:

```text
GradesParser
ScheduleParser
AssignmentsParser
AnnouncementsParser
```

---

# 16. Canonical snapshot format

Создать versioned schema.

Например:

```json
{
  "schema_version": 1,
  "captured_at": "2026-09-07T09:00:00+02:00",
  "grades": [],
  "schedule": [],
  "assignments": [],
  "announcements": []
}
```

Timestamp не должен участвовать в semantic diff.

---

# 17. Модель оценки

Пример:

```json
{
  "id": "stable-id",
  "course": "Machine Learning",
  "assessment": "Final Exam",
  "grade": "8.5",
  "scale": "10",
  "status": "final",
  "published_at": null
}
```

Stable key в порядке предпочтения:

1. ID из портала;
2. assessment URL/id;
3. комбинация:

```text
course + assessment
```

Не использовать позицию строки в таблице.

---

# 18. Модель расписания

```json
{
  "id": "stable-id",
  "course": "Machine Learning",
  "type": "lecture",
  "start": "2026-09-10T10:00:00",
  "end": "2026-09-10T12:00:00",
  "location": "Room A1",
  "teacher": "..."
}
```

Если портал показывает отмененное занятие:

```json
"status": "cancelled"
```

---

# 19. Модель задания

```json
{
  "id": "stable-id",
  "course": "AI Systems",
  "title": "Assignment 2",
  "deadline": "2026-09-20T23:59:00",
  "status": "open",
  "url": "..."
}
```

Отслеживать отдельно:

* новое задание;
* изменение deadline;
* изменение статуса;
* удаление задания.

Удаление не обязательно трактовать как событие для пользователя без дополнительной проверки.

---

# 20. Модель объявления

```json
{
  "id": "stable-id",
  "title": "Exam information",
  "published_at": "2026-09-07T12:00:00",
  "body": "...",
  "url": "..."
}
```

Для длинного текста объявления хранить:

```text
body
body_hash
```

В Telegram не отправлять весь body автоматически.

---

# 21. Нормализация данных

Создать `normalize.py`.

Нормализовать:

* whitespace;
* Unicode spaces;
* line endings;
* HTML entities;
* decimal comma / decimal point при необходимости;
* даты;
* timezone;
* пустые значения;
* регистр некоторых enum/status.

Например:

```text
"  Assignment   1\n"
```

должно стать:

```text
"Assignment 1"
```

Это существенно уменьшит ложные diff.

---

# 22. Parser validation

Нельзя считать пустой результат автоматически корректным.

Например, если вчера было 15 оценок, а сегодня parser вернул 0, возможны два варианта:

1. действительно нет данных;
2. университет поменял HTML.

Поэтому добавить sanity checks.

Пример:

```python
if previous_count > 0 and current_count == 0:
    raise ParserValidationError(...)
```

Аналогично для остальных разделов.

Не обновлять baseline после parser validation failure.

---

# 23. Этап 5 — State manager

Хранить:

```text
data/state/current_snapshot.json
```

После успешной проверки можно архивировать предыдущие состояния:

```text
data/history/2026-09-07T090000.json
```

Количество истории ограничить, например:

```text
30–90 snapshots
```

или хранить только последние N дней.

Все записи выполнять атомарно.

---

# 24. Первый запуск

Это важный UX-кейс.

Если:

```text
current_snapshot.json
```

еще не существует:

считать текущие данные baseline.

НЕ сообщать:

```text
Найдено 18 новых оценок
Найдено 27 новых занятий
```

Вместо этого:

```text
Первоначальное состояние личного кабинета сохранено. Дальнейшие проверки будут сообщать только об изменениях.
```

Добавить настройку:

```yaml
notifications:
  notify_existing_on_first_run: false
```

По умолчанию `false`.

---

# 25. Этап 6 — Semantic diff

Создать:

```text
diff.py
```

Функция:

```python
compare_snapshots(old, new) -> PortalChanges
```

Нельзя сравнивать JSON целиком строкой.

Сравнивать сущности по stable IDs.

---

# 26. Grades diff

Отслеживать:

### Новая оценка

Было:

```text
нет записи
```

Стало:

```text
Machine Learning / Exam → 8.5
```

Событие:

```json
{
  "type": "grade_added"
}
```

### Измененная оценка

Было:

```text
7.5
```

Стало:

```text
8.0
```

Событие:

```json
{
  "type": "grade_changed",
  "old": "7.5",
  "new": "8.0"
}
```

---

# 27. Schedule diff

Выделять:

```text
schedule_added
schedule_removed
schedule_time_changed
schedule_room_changed
schedule_teacher_changed
schedule_cancelled
```

Особенно важно не превращать изменение аудитории в:

```text
old event removed
new event added
```

если имеется достаточно данных, чтобы определить, что это одно занятие.

---

# 28. Assignment diff

Выделять:

```text
assignment_added
deadline_changed
assignment_status_changed
```

Deadline change должен содержать:

```text
старый deadline
новый deadline
```

---

# 29. Announcement diff

В основном:

```text
announcement_added
announcement_changed
```

Старые объявления не отправлять повторно.

---

# 30. Changes JSON

После diff создавать:

```text
data/reports/latest_changes.json
```

Например:

```json
{
  "status": "changes",
  "changes": {
    "grades": [
      {
        "type": "grade_added",
        "course": "Machine Learning",
        "assessment": "Exam",
        "grade": "8.5"
      }
    ],
    "schedule": [],
    "assignments": [],
    "announcements": []
  }
}
```

---

# 31. Этап 7 — deterministic report generator

Создать:

```text
report.py
```

Python должен самостоятельно уметь создавать нормальный отчет.

Hermes не должен быть обязан анализировать raw HTML.

Пример:

```text
Изменения в личном кабинете:

• Новая оценка: Machine Learning — Exam: 8.5.
• Перенесена лекция AI Systems: 10 сентября, с 10:00 на 12:00.
• Новый дедлайн: Assignment 2 — 20 сентября, 23:59.
```

Если изменений нет:

```text
В личном кабинете новых изменений нет.
```

Если нужна авторизация:

```text
Сессия личного кабинета истекла. Выполни локально:
python scripts/login_once.py
```

---

# 32. LLM не должен решать, изменились ли данные

Это архитектурное правило.

Неправильно:

```text
old HTML + new HTML → Hermes → "что изменилось?"
```

Правильно:

```text
old canonical JSON
+
new canonical JSON
↓
Python semantic diff
↓
changes.json
↓
короткое форматирование
↓
Hermes
```

Так система будет:

* дешевле;
* стабильнее;
* предсказуемее;
* приватнее;
* легче тестироваться.

---

# 33. Этап 8 — единая команда `run_check.py`

Основная команда пользователя:

```bash
python scripts/run_check.py
```

Она должна выполнить весь pipeline:

```text
acquire lock
↓
preflight
↓
check storage state
↓
fetch
↓
auth validation
↓
parse
↓
schema validation
↓
semantic validation
↓
load previous state
↓
diff
↓
generate report
↓
atomically commit new state
↓
print report
↓
release lock
```

---

# 34. Lock

Cron-задачи не должны запускаться одновременно.

Добавить lock, например:

```text
data/.automation.lock
```

Если предыдущая проверка еще выполняется:

```text
Student portal check is already running.
```

и второй процесс должен корректно завершиться.

Использовать `filelock`.

---

# 35. Порядок обновления baseline

Очень важно:

новый snapshot сохранять как baseline ТОЛЬКО после:

```text
fetch successful
AND
authentication valid
AND
all required parsers successful
AND
schema validation successful
AND
semantic validation successful
AND
diff successfully generated
```

Если что-либо сломалось, оставить предыдущий baseline.

---

# 36. Статусы выполнения

Ввести внутренние статусы:

```text
OK_NO_CHANGES
OK_CHANGES
BASELINE_CREATED
REAUTH_REQUIRED
PORTAL_UNAVAILABLE
PARSER_ERROR
CONFIG_ERROR
PARTIAL_FAILURE
```

Не определять состояние системы анализом произвольного stdout.

---

# 37. Exit codes

Для ожидаемых пользовательских ситуаций предпочтительно не превращать результат в crash.

Например:

```text
0 = pipeline обработал ситуацию и создал отчет
1 = неожиданная внутренняя ошибка
```

`REAUTH_REQUIRED` является ожидаемым состоянием системы и может иметь exit code 0, при этом состояние передается через report JSON.

Это упрощает работу cron.

---

# 38. Machine-readable result

Кроме текста создать:

```text
data/reports/latest_run.json
```

Например:

```json
{
  "status": "REAUTH_REQUIRED",
  "started_at": "...",
  "finished_at": "...",
  "changes_count": 0,
  "report": "Сессия личного кабинета истекла..."
}
```

Hermes сможет ориентироваться на этот файл при необходимости.

---

# 39. Логирование

Использовать Python `logging`.

Логировать:

* начало проверки;
* страницу;
* статус загрузки;
* parser result count;
* diff count;
* duration;
* ошибки.

Не логировать:

* cookies;
* session token;
* Authorization headers;
* полный storage state;
* password;
* 2FA codes.

Желательно использовать rotating log.

---

# 40. Отладка

Добавить:

```bash
python scripts/run_check.py --verbose
```

и:

```bash
python scripts/run_check.py --dry-run
```

`--dry-run`:

* получает страницы;
* парсит;
* считает diff;
* показывает результат;
* НЕ обновляет baseline.

Это очень полезно при разработке parser.

---

# 41. Fixture mode

Добавить возможность тестировать parser без портала:

```bash
python scripts/parse_pages.py \
    --input tests/fixtures/example/
```

Код-агент должен иметь возможность полностью разрабатывать diff/parser infrastructure без доступа к пользовательскому аккаунту.

---

# 42. Что делать до получения реального HTML портала

Если code-agent не имеет доступа к DOM университета:

НЕ придумывать selectors.

Реализовать:

* infrastructure;
* parser interfaces;
* configuration;
* fixtures;
* example parsers;
* diff engine;
* state;
* reporting;
* tests.

После первого ручного запуска пользователь сможет предоставить локальные HTML samples либо агент сможет работать с ними локально.

Только после этого адаптировать selectors.

---

# 43. Тестирование auth

Добавить fixtures:

### Authenticated page

Ожидание:

```text
authenticated = true
```

### Login page

Ожидание:

```text
REAUTH_REQUIRED
```

### CAPTCHA page

Ожидание:

```text
CHALLENGE_DETECTED
```

---

# 44. Diff tests

Обязательные unit tests:

### Grades

```text
same → no diff
new grade → grade_added
changed grade → grade_changed
DOM order changes → no diff
```

### Schedule

```text
same → no diff
new class
removed class
changed time
changed room
cancelled class
```

### Assignments

```text
new assignment
changed deadline
changed status
```

### Announcements

```text
new announcement
same announcement → no diff
```

---

# 45. Critical regression tests

Обязательно проверить:

### Parser suddenly returns zero

Не обновлять state.

### Only HTML formatting changes

Не отправлять notification.

### Entries change order

Не отправлять notification.

### Session expires halfway through fetch

Не обновлять state.

### One required page gives HTTP/server error

Не обновлять state.

### First run

Создать baseline без десятков ложных notifications.

### Re-running same snapshot

Получить:

```text
В личном кабинете новых изменений нет.
```

---

# 46. Rate limiting

Не сканировать портал слишком часто.

Для ежедневного мониторинга достаточно одного запуска в день или нескольких запусков с разумным интервалом.

Между страницами можно использовать небольшой фиксированный технический интервал, если это требуется порталом.

Не создавать высокочастотный crawler.

---

# 47. Не использовать AI для browser navigation

Hermes не должен самостоятельно:

```text
find button
click random element
figure out where grades are
navigate portal autonomously
```

Для production monitoring нужны заранее определенные URL и parser adapters.

Это снижает риск случайного действия в кабинете.

---

# 48. Hermes integration — вариант 1, рекомендуемый для MVP

После успешной ручной проверки:

```bash
python scripts/run_check.py
```

создать Hermes cron из корня проекта.

Пример:

```bash
hermes cron create "0 9 * * *" \
  "Run python scripts/run_check.py. Return its student portal report concisely in Russian. Do not interact with the portal manually. Do not perform any write action. If the report says REAUTH_REQUIRED, tell me to run python scripts/login_once.py locally." \
  --workdir "/absolute/path/to/student-portal-automation" \
  --deliver telegram \
  --name "Student portal daily check"
```

Использовать абсолютный `--workdir`.

---

# 49. Hermes должен запускать только orchestrator

Не давать Hermes последовательность:

```text
fetch_pages
parse_pages
detect_changes
...
```

в production.

Дать одну точку входа:

```bash
python scripts/run_check.py
```

Python сам отвечает за порядок операций.

Это предотвращает ситуацию, когда LLM:

* пропустил шаг;
* выполнил команды не в том порядке;
* обновил state после ошибки.

---

# 50. Возможная следующая оптимизация Hermes

После стабилизации проекта можно сделать отдельный wrapper script для Hermes scheduler.

Тогда scheduled task будет максимально детерминированной.

Если итоговый Python-report уже хорошо читается, LLM вообще не обязателен для каждой проверки.

Hermes может использоваться только для:

```text
schedule
+
delivery
```

А Python будет формировать финальный Telegram-ready текст.

---

# 51. README

README должен содержать только понятный user workflow.

## Installation

```bash
git clone ...
cd student-portal-automation

python -m venv .venv
source .venv/bin/activate

pip install -e .
playwright install chromium
```

## Configure

```bash
cp config/portal.example.yaml config/portal.yaml
```

Заполнить URL/selectors.

## First login

```bash
python scripts/login_once.py
```

## First check

```bash
python scripts/run_check.py
```

## Debug check

```bash
python scripts/run_check.py --dry-run --verbose
```

## Tests

```bash
pytest
```

---

# 52. Реализация должна идти итерациями

## Milestone 1 — Skeleton

Создать:

* project structure;
* pyproject;
* config loader;
* AGENTS.md;
* `.gitignore`;
* models;
* CLI stubs.

Definition of Done:

```bash
pytest
```

работает.

---

## Milestone 2 — Manual authentication

Реализовать:

```text
login_once.py
browser.py
auth.py
```

Definition of Done:

пользователь вручную логинится, после чего существует:

```text
secrets/storage_state.json
```

Пароль нигде не сохранен.

---

## Milestone 3 — Fetch

Реализовать:

```text
fetcher.py
fetch_pages.py
```

Definition of Done:

заданные страницы сохраняются в `data/latest`.

При expired session возвращается `REAUTH_REQUIRED`.

---

## Milestone 4 — Canonical data model

Реализовать модели:

```text
Grade
ScheduleEvent
Assignment
Announcement
PortalSnapshot
```

Definition of Done:

модели сериализуются в стабильный JSON.

---

## Milestone 5 — Parser infrastructure

Реализовать все parser interfaces.

Если настоящий HTML еще неизвестен, использовать fixtures.

Definition of Done:

```bash
pytest tests/test_*_parser.py
```

проходит.

---

## Milestone 6 — Portal-specific adapters

После появления реальных HTML samples:

адаптировать:

```text
grades.py
schedule.py
assignments.py
announcements.py
```

под реальную структуру сайта.

Definition of Done:

каждый parser извлекает ожидаемые сущности из fixtures.

---

## Milestone 7 — Semantic diff

Реализовать:

```text
diff.py
```

Definition of Done:

все diff regression tests проходят.

---

## Milestone 8 — State

Реализовать:

* baseline;
* atomic writes;
* no-update-on-failure;
* history;
* dry-run.

Definition of Done:

повторный запуск одинаковых fixtures не создает изменений.

---

## Milestone 9 — Reporting

Реализовать русский текстовый отчет.

Definition of Done:

сценарии:

```text
no changes
new grade
schedule changed
new assignment
deadline changed
announcement
reauth required
parser failure
```

имеют понятные сообщения.

---

## Milestone 10 — `run_check.py`

Объединить весь pipeline.

Definition of Done:

одна команда:

```bash
python scripts/run_check.py
```

выполняет всю проверку.

---

## Milestone 11 — Hermes

Создать cron.

Сначала вручную выполнить:

```bash
hermes cron run <job_id>
```

Проверить delivery.

Только после успешного test run оставить автоматическое расписание.

---

# 53. Definition of Done всего проекта

Проект считается готовым, когда выполняются все условия:

1. Пользователь самостоятельно выполняет manual login.
2. Password нигде не сохраняется.
3. Session state хранится только локально.
4. Команда `python scripts/run_check.py` работает без Hermes.
5. При неизменном кабинете нет ложных notifications.
6. Новая оценка корректно определяется.
7. Измененная оценка корректно определяется.
8. Изменение расписания корректно определяется.
9. Новый assignment корректно определяется.
10. Измененный deadline корректно определяется.
11. Новое announcement корректно определяется.
12. Expired session корректно определяется.
13. При expired session автоматический login не выполняется.
14. CAPTCHA не обходится.
15. При parser failure baseline не повреждается.
16. При partial fetch baseline не повреждается.
17. Первый запуск создает baseline без ложной лавины notifications.
18. State записывается атомарно.
19. Одновременный cron run заблокирован lock-файлом.
20. `pytest` проходит.
21. `storage_state.json` исключен из Git.
22. HTML/state пользователя исключены из Git.
23. Hermes запускает только `run_check.py`.
24. Hermes присылает короткую русскую сводку.
25. Ни один production workflow не выполняет write actions в student portal.

---

# 54. Приоритет реализации

Не пытаться сразу сделать интеллектуальный универсальный scraper.

Приоритет:

```text
1. Safety
2. Session handling
3. Reliable fetch
4. Canonical data
5. Reliable parser
6. Semantic diff
7. State integrity
8. Tests
9. Reporting
10. Hermes cron
```

AI использовать только там, где он действительно дает пользу.

Критические операции:

```text
authentication detection
parsing
diff
state update
```

должны быть обычным детерминированным Python-кодом.

---

# 55. Инструкция code-agent перед началом работы

Перед внесением изменений:

1. Изучи существующий repository.
2. Прочитай `AGENTS.md`.
3. Не удаляй safety restrictions.
4. Не добавляй автоматический login.
5. Не придумывай selectors реального портала без HTML evidence.
6. Сначала реализуй generic infrastructure.
7. Для каждого milestone добавляй tests.
8. После каждого milestone запускай:

   ```bash
   pytest
   ```
9. Не переходи к Hermes integration, пока:

   ```bash
   python scripts/run_check.py
   ```

   не работает самостоятельно.
10. Не считай задачу завершенной без проверки failure scenarios.

В конце работы выведи:

```text
Implemented:
- ...

Tests:
- ...

Manual configuration still required:
- ...

Security assumptions:
- ...

Command for first login:
- ...

Command for manual check:
- ...

Recommended Hermes cron command:
- ...
```
