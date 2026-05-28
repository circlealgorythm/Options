import sys

def update_todo():
    with open('tasks/todo.md', 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
        
    target = """## Фаза 2: Разработка Индикатора для ручной торговли (MT5 / TradingView)
- [ ] Разработать индикатор уровней GEX (зеленый/красный) и абсолютной гаммы (синий/золотой) на MQL5 или Pine Script.
- [ ] Добавить отрисовку ключевых опционных уровней CME (MD, 68-я и 95-я границы рынка).
- [ ] Реализовать отображение истории уровней за последние N дней (по умолчанию 30), ограничивая линии горизонтально временем начала и конца соответствующих суток.
- [ ] Реализовать динамическое масштабирование гистограмм относительно дневного максимума.
- [ ] Добавить поддержку суффиксов/префиксов для брокерских тикеров."""

    replacement = """## Фаза 2: Разработка Индикатора для ручной торговли (MT5 / TradingView)
- [/] Расширить GEX дата-пайплайн расчетом MDD и 68%/95% зон волатильности
    - [ ] Реализовать расчет дневной волатильности sigma и зон R68/R95 в `main.py`
    - [ ] Добавить колонки R68_High, R68_Low, R95_High, R95_Low в результирующие CSV
- [/] Разработать визуализацию в советнике `CME_GEX_Levels_EA.mq5` в стиле шаблона автора:
    - [ ] Добавить чтение R68/R95 зон из CSV и рисование закрашенных фоновых прямоугольников на графике
    - [ ] Реализовать отрисовку уровней 1-го порядка (Call/Put с максимальным OI) широкими сплошными синими и оранжевыми линиями (width=5)
    - [ ] Реализовать отрисовку уровней 2-го порядка (Call/Put MDD) тонкими пунктирными синими и оранжевыми линиями с описанием "MDD"
    - [ ] Улучшить текстовые подписи с выводом GEX/AG объемов и процентов относительно дневного максимума
- [ ] Реализовать отображение истории уровней за последние N дней (по умолчанию 30)
- [ ] Реализовать динамическое масштабирование гистограмм относительно дневного максимума
- [ ] Добавить поддержку суффиксов/префиксов для брокерских тикеров"""

    # Normalize newlines
    content_norm = content.replace('\r\n', '\n')
    target_norm = target.replace('\r\n', '\n')
    replacement_norm = replacement.replace('\r\n', '\n')
    
    if target_norm in content_norm:
        new_content = content_norm.replace(target_norm, replacement_norm)
        with open('tasks/todo.md', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Successfully updated tasks/todo.md")
    else:
        # Let's try matching with flexible whitespace
        print("Target text not found in tasks/todo.md exactly. Attempting regex...")
        import re
        # Escape target to use in regex, replacing spaces/newlines with flexible whitespace
        pattern = re.escape(target_norm).replace(r'\ ', r'\s+').replace(r'\n', r'\s+')
        match = re.search(pattern, content_norm)
        if match:
            new_content = content_norm[:match.start()] + replacement_norm + content_norm[match.end():]
            with open('tasks/todo.md', 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("Successfully updated tasks/todo.md via regex")
        else:
            print("Failed to find target even with regex.")

if __name__ == '__main__':
    update_todo()
