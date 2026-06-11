import json
import os

with open('feature_list.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# check if SPX exists
spx_exists = any(item['id'] == 'sp500_support' for item in data)
if not spx_exists:
    spx_feature = {
        "id": "sp500_support",
        "priority": 6,
        "area": "data_pipeline_and_indicator",
        "title": "Интеграция S&P 500 (SPX)",
        "user_visible_behavior": "Пайплайн собирает уровни для S&P 500 (SPX), а индикатор в MT5 отображает их без искажений на графиках S&P 500.",
        "status": "passing",
        "verification": [
            "Парсинг E-mini SPX отчетов CME.",
            "Размер контракта = 50 для корректного расчета GEX.",
            "Индикатор поддерживает базовую валюту SPX.",
            "Файлы сохраняются в MQL5/Files/GEX/NAS100/."
        ],
        "evidence": "SPX levels are drawn on chart and verified by the user in screenshot.",
        "notes": "Contract size multiplier issue resolved."
    }
    data.append(spx_feature)
    with open('feature_list.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

with open('progress.md', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("Последняя задача:", "Последняя задача: Фаза 27 (Интеграция S&P 500 SPX)")
if "* **Текущий статус:**" in content:
    pass

with open('progress.md', 'a', encoding='utf-8') as f:
    f.write("\n\n* **Последнее обновление:** Успешно добавлена поддержка S&P 500 (SPX), исправлен contract multiplier, добавлены записи в логи.\n")

print("JSON and progress updated.")
