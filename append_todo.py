import os

todo_path = 'tasks/todo.md'
lessons_path = 'tasks/lessons.md'

with open(todo_path, 'a', encoding='utf-8') as f:
    f.write("\n\n- **S&P 500 Options (10 Июня 2026):**\n")
    f.write("    - Добавлен код парсинга `SPX` (S&P 500) в `main.py`.\n")
    f.write("    - Добавлена поддержка `SPX500` в `CME_GEX_Levels_Indicator.mq5`.\n")
    f.write("    - **ПРОБЛЕМА:** Временно использовано плейсхолдерное имя файла CME (`Section47_E_Mini_S_And_P_500_Options.pdf`), так как защита CME Cloudflare заблокировала просмотр оглавления, а сайт у пользователя также выдавал пустой файл (сбой CME).\n")
    f.write("    - Файлы для `SPX` скачиваются в папку `NAS100/` (согласно требованиям обратной совместимости путей).\n")

with open(lessons_path, 'a', encoding='utf-8') as f:
    f.write("\n\n### Интеграция S&P 500 и обход CME (10 Июня 2026)\n")
    f.write("- **CME Cloudflare:** Частое сканирование корня `daily_bulletin/current/` приводит к бану IP адреса по причине подозрения в Web Scraping. Обычное скачивание конкретного PDF-файла (через `curl_cffi`) продолжает работать, даже если IP забанен для парсинга HTML оглавления.\n")
    f.write("- **Резервные имена:** Так как сайт CME был недоступен, временно оставлен TODO с фейковым именем документа. Как только доступ вернется, необходимо скопировать точное название из браузера.\n")

print("Appended successfully.")
