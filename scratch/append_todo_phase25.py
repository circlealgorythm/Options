todo_path = 'tasks/todo.md'

phase25_text = """

## Фаза 25: Исправление юнит-тестов и копирования уровней в MT5
- [ ] Добавить поддержку `mt5_gex_dir` в `copy_csv_to_mt5` в `main.py` и возврат пути скопированного файла.
- [ ] Запустить локальные тесты и убедиться в успешном прохождении всех тестов.
"""

with open(todo_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Avoid duplicate append
if "Фаза 25: Исправление юнит-тестов" not in content:
    with open(todo_path, 'a', encoding='utf-8') as f:
        f.write(phase25_text)
    print("Appended Phase 25 successfully.")
else:
    print("Phase 25 already present.")
