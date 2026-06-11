#!/bin/bash
# Инициализация окружения, установка зависимостей и верификация

INSTALL_CMD="C:/Users/circlealgorythm/AppData/Local/Programs/Python/Python311/python.exe -m pip install -r requirements.txt"
VERIFY_CMD="C:/Users/circlealgorythm/AppData/Local/Programs/Python/Python311/python.exe -m pytest tests/"
START_CMD="C:/Users/circlealgorythm/AppData/Local/Programs/Python/Python311/python.exe main.py"

echo "=== 1. Проверка рабочей директории ==="
pwd

echo "=== 2. Установка зависимостей ==="
$INSTALL_CMD

echo "=== 3. Запуск верификации ==="
$VERIFY_CMD

if [ $? -eq 0 ]; then
    echo "=== Верификация пройдена успешно! ==="
    echo "Для запуска сбора уровней выполните: $START_CMD"
else
    echo "!!! Ошибка верификации. Пожалуйста, исправьте тесты перед началом работы. !!!"
    exit 1
fi
