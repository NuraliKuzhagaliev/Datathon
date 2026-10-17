# Проверка интерфейса B с кодом backend A

Дата: 17 октября 2026. Сервер A ещё не готов. Все входные видео в этом прогоне созданы генератором цветовых тестовых шаблонов. Конкурсные материалы не использовались.

## Что реально проверено

| Компонент | Ревизия / результат |
| --- | --- |
| Backend A | `1d10013fbfcff57bd8782077543d5aa4816fab4f`, версия 0.3.0; копия в игнорируемой `.tools/backend-reference` |
| Frontend B | `codex/frontend`, основной коммит `9f3716c`, контракт 1.0.0 |
| Тесты A | **20 passed**, 24.20 секунды; исходные тесты A без изменений |
| Браузер + API | **3 passed**, 38.8 секунды; production-сборка React, Microsoft Edge, настоящий HTTP на loopback |
| Объединение исходников | `git merge-tree --write-tree HEAD origin/codex/backend`: без конфликтов; объединение в `main` не выполнялось |

В трёх браузерных сценариях используются настоящие модули A: FastAPI, авторизация, загрузка файла, SQLite, Pipeline, PyAV/FFmpeg, JPEG-кадры, MP4, сохранение review и серверный ZIP. Вместо Qwen подключён **ScriptedSyntheticModel из тестов A**, возвращающий заданные результаты. Тестовый worker создан только в `apps/web/tests/integration/server.py` и не подключается к production-приложению.

| Сценарий | Проверенные действия |
| --- | --- |
| Положительный | Вход → MOV → состояние обработки → два события → исходный кадр → воспроизводимый MP4 → источник нормы → отклонение и заметка → повторный вход → сохранённое решение → ZIP |
| Отрицательный | Вход → MOV → завершение без событий и без нарушения → ZIP |
| Техническая ошибка | Вход → MOV → `RESOURCE_EXHAUSTED` → состояние ошибки без вердикта; экспорт отключён |
| Общие проверки | 401 без ключа и при доступе jury к UI; jury не видит чужое дело; ключ отсутствует в localStorage; намеренное удаление созданного тестового дела даёт 404 |

После review исходный jury-ответ полностью совпал с ответом до review. При повторном входе решение и заметка восстановились из SQLite. ZIP проверен браузером на скачивание, имя, сигнатуру и непустой размер; содержимое, версии и хеши проверяют отдельные тесты A.

Длительности выше — время выполнения тестов. Они **не являются задержкой настоящей модели** или оценкой производительности на конкурсном видео.

## Как повторить на Windows

Нужны Python 3.11–3.12, Node/pnpm согласно корневому package.json, Git и Microsoft Edge. Выполнять из корня репозитория. Используются только созданные тестами файлы.

### 1. Подготовить копию A

Для проверенной ревизии:

```powershell
git fetch origin codex/backend
New-Item -ItemType Directory -Force .tools/backend-reference | Out-Null
git archive 1d10013fbfcff57bd8782077543d5aa4816fab4f -o .tools/backend-reference.tar
tar -xf .tools/backend-reference.tar -C .tools/backend-reference
```

Не заменять этим архивом рабочее дерево. После окончательного объединения можно использовать объединённое дерево, задав `$env:CASHPROOF_BACKEND_ROOT = (Get-Location).Path`; тогда адаптировать путь `$backendRoot` в следующем блоке. Проверка другой ревизии требует нового протокола результата.

### 2. Подготовить тестовую среду без GPU-зависимостей

Версии берутся из файлов A. Это отдельная среда только для интеграционных проверок; она не заменяет полный runtime модели.

```powershell
python -m venv .tools/integration-venv
$backendRoot = '.tools/backend-reference/services/backend'
$dependencyScript = @'
import sys, tomllib
from pathlib import Path
root = Path(sys.argv[1])
project = tomllib.loads((root / 'pyproject.toml').read_text())['project']
excluded = {'torch', 'torchvision', 'transformers', 'huggingface-hub', 'accelerate', 'lm-format-enforcer'}
requirements = [r for r in project['dependencies'] + project['optional-dependencies']['test'] if r.split('==')[0] not in excluded]
lock = tomllib.loads((root / 'uv.lock').read_text())
requirements.append('filelock==' + next(p['version'] for p in lock['package'] if p['name'] == 'filelock'))
print('\n'.join(requirements))
'@
$requirements = & .tools/integration-venv/Scripts/python.exe -c $dependencyScript $backendRoot
& .tools/integration-venv/Scripts/python.exe -m pip install $requirements
```

В записанном прогоне установленные версии runtime/test-пакетов, включая транзитивные, совпали с A `uv.lock`. Системные pip/setuptools отличаются и не использовались для сборки backend. Приведённая установка через pip не замораживает будущие транзитивные версии; после повторной установки сверить их с lock A. CUDA, torch и Qwen не устанавливались.

### 3. Запустить

```powershell
pnpm install --frozen-lockfile
pnpm build:web
pnpm test:integration
$env:PYTHONPATH = (Resolve-Path '.tools/backend-reference/services/backend/src').Path
& .tools/integration-venv/Scripts/python.exe -m pytest .tools/backend-reference/services/backend/tests -q
```

`CASHPROOF_TEST_PYTHON` позволяет указать другой подготовленный Python. По умолчанию тест использует `.tools/integration-venv/Scripts/python.exe`; backend берётся из `.tools/backend-reference`. В объединённом дереве установить также `PYTHONPATH` на его `services/backend/src`.

Harness привязывается к `127.0.0.1` на свободном порту. Случайные тестовые ключи генерируются на каждый запуск и передаются только дочернему процессу. Тесты создают временные папки с префиксом `cashproof-synthetic-integration-`, работают со своими делами и закрывают своё дерево процессов. Остатки этих папок содержат только синтетические данные. Отчёты Playwright находятся в игнорируемом `apps/web/dist/integration-test-results`.

У pytest было одно предупреждение Starlette о будущей замене TestClient/httpx. Все 20 проверок прошли; менять зависимости A ради предупреждения не стали.

## Исправления B после чтения backend

1. Electron добавляет `-m cashproof.bootstrap` после interpreter-only `args_prefix`; раньше этот обязательный модуль отсутствовал.
2. Несовместимость контракта определяется по коду ошибки `CONTRACT_MISMATCH`, без поиска слова в переводе. Ожидание сразу прекращается; отдельный Electron-сценарий проверяет восстановление кнопок.
3. Windows-пакет включает только `index.html`, `mark.svg`, `assets` и `fonts` из веб-сборки. QA-скриншоты и отчёты не попадают в распространяемые ресурсы.

## Что остаётся перед сдачей

- A объединяет опубликованные ветки и обновляет корневой README, затем обе стороны повторяют проверки на общей ревизии.
- A запускает настоящий сервис и передаёт доступный URL; операторский ключ вводится в UI приватно. Сейчас пользователь подтвердил, что сервер ещё не готов.
- Команда выполняет [I01–I18](INTEGRATION_CHECKLIST.md) с настоящей моделью, локальной человеческой проверкой кадров/норм, внешним HTTPS и автономным запуском на RTX 4060.
- A измеряет качество и задержку. В опубликованном отчёте A для четырёх development-примеров 0.3.0 указаны TP=0, TN=2, FP=0, FN=2: два положительных примера пропущены. Это малая промежуточная выборка, но уже основание считать качество открытым блокером. Статистику всего набора и недоступной B validation-выборки не выдумываем.

Ни синтетическая интеграция, ни отсутствие Git-конфликтов не подтверждают готовность модели, прохождение лимита 300 секунд с очередью, автономность или доступность публичного адреса.
