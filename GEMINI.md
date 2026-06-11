# Описание проекта
Разработка бота для торговли по опционным уровням (CME + GEX и абсолютная гамма).

---

## 1. Управление задачами и Harness-цикл
Перед началом выполнения любой задачи агент обязан:
1. Прочесть лог сессий в `progress.md` (ранее `claude-progress.md`).
2. Прочесть список фич в `feature_list.json`.
3. Поставить статус `in_progress` для целевой фичи в `feature_list.json` (разрешена только одна активная фича за раз).
4. Записать план в файл `tasks/todo.md` с отмечаемыми пунктами.
5. Фиксировать изменения в `tasks/todo.md` и в конце сессии обновлять `tasks/lessons.md`.

---

## 2. Команды для разработки и верификации
Для запуска и тестирования использовать системный Python 3.11:
* **Интерпретатор:** `C:\Users\circlealgorythm\AppData\Local\Programs\Python\Python311\python.exe`
* **Запуск тестов:**
  `C:\Users\circlealgorythm\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/`
* **Запуск сбора уровней (пайплайн):**
  `C:\Users\circlealgorythm\AppData\Local\Programs\Python\Python311\python.exe main.py`
* **Запуск веб-дашборда:**
  `C:\Users\circlealgorythm\AppData\Local\Programs\Python\Python311\python.exe Dashboard/run_dashboard.py`
* **Инициализация проекта:** Запустить в PowerShell: `powershell -File init.ps1`

---

## 3. Основные принципы и соглашения

* **Простота прежде всего:** Делай каждое изменение максимально простым. Минимальные правки кода.
* **Не ленись:** Находи первопричины. Никаких временных решений. Соответствуй практикам опытных разработчиков.
* **Минимальное влияние:** Изменения должны затрагивать только необходимое.

### 3.1. Python (Пайплайн и Бэкенд)
* Использовать `curl_cffi` для обхода WAF Cloudflare/Akamai при загрузке файлов с CME Group.
* Все расчеты математики (IV, Gamma) должны быть изолированы в `src/bs_math.py`.
* Логика извлечения таблиц из PDF должна находиться в `src/parser.py`.
* Копирование CSV-файлов в MT5 должно выполняться через функцию `copy_csv_to_mt5` с поддержкой кастомного пути.

### 3.2. MQL5 (Индикатор)
* Разработка ведется исключительно в индикаторе `CME_GEX_Levels_Indicator.mq5` (советник EA удален).
* Функции чтения файлов не должны использовать `WebRequest` во избежание фризов графического интерфейса (ошибка 4014). Использовать локальное чтение из `Files/GEX/`.
* При смене таймфрейма использовать функцию `GetDailySpotReferenceWithRetry` с ожиданием синхронизации D1-истории во избежание прыжков уровней.

### 3.3. Веб-Дашборд
* Бэкенд `run_dashboard.py` должен использовать исключительно стандартную библиотеку Python (никаких Flask, FastAPI).
* Фронтенд пишется на чистом HTML, CSS и Vanilla JS (никакого React/Vite/Tailwind).
* Запрещены тяжелые GPU-эффекты размытия (`backdrop-filter: blur`, `.glow-bg`) для обеспечения 0% нагрузки на графический процессор.

---

## 4. Definition of Done (Критерии готовности)
Задача считается полностью выполненной только в том случае, если:
* Все измененные файлы не содержат плейсхолдеров или заглушек.
* Локальные тесты `pytest tests/` успешно пройдены (13 passed).
* Доказано отсутствие регрессии существующих функций (файлы уровней генерируются корректно).
* Пройден чек-лист [clean-state-checklist.md](file:///c:/Users/circlealgorythm/.antigravity/bot_grid/clean-state-checklist.md).
* Обновлены файлы [progress.md](file:///c:/Users/circlealgorythm/.antigravity/bot_grid/progress.md) (запись о сессии) и [feature_list.json](file:///c:/Users/circlealgorythm/.antigravity/bot_grid/feature_list.json) (статус `passing`).
* Обновлены логи задач в `tasks/todo.md` и уроки в `tasks/lessons.md`.
