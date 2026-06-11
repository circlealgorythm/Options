# Инструкция по запуску CME GEX Levels (MT5 & Python Pipeline)

Этот проект состоит из двух частей:
1. **Python-скрипт** (запускается локально или через GitHub Actions), который скачивает бюллетени CME, парсит опционные уровни, рассчитывает GEX и Absolute Gamma по формуле Black-Scholes и сохраняет результаты в приватный репозиторий в формате CSV.
2. **MetaTrader 5 Expert Advisor (EA)**, который загружает эти CSV-файлы напрямую из приватного репозитория GitHub и отрисовывает уровни на графиках валютных пар.

---

## Часть 1. Обновление кода из Git

Если вы хотите получить актуальную версию кода на локальном компьютере:

1. Откройте **Git Bash** (или терминал).
2. Перейдите в папку проекта:
   ```bash
   cd /c/Users/circlealgorythm/.antigravity/bot_grid
   ```
3. Выполните команду получения последних изменений:
   ```bash
   git pull origin main
   ```

---

## Часть 2. Настройка MetaTrader 5 (MT5)

Чтобы советник в MT5 мог скачивать CSV-файлы с уровнями из вашего приватного репозитория, выполните следующие шаги:

### Шаг 1. Разрешение WebRequest в терминале MT5
1. Откройте MetaTrader 5.
2. В верхнем меню выберите **Сервис** -> **Настройки** (или нажмите `Ctrl + O`).
3. Перейдите на вкладку **Советники**.
4. Установите галочку **"Разрешить WebRequest для следующих URL:"**.
5. Добавьте в список следующие адреса (дважды кликните по пустому полю ввода):
   * `https://raw.githubusercontent.com`
   * `https://api.github.com`
6. Нажмите **ОК**.

### Шаг 2. Копирование и компиляция советника
1. Скопируйте файл `CME_GEX_Levels_EA.mq5` из папки проекта:
   `C:\Users\circlealgorythm\.antigravity\bot_grid\CME_GEX_Levels_EA.mq5`
2. В MT5 выберите **Файл** -> **Открыть каталог данных**.
3. Перейдите по пути: `MQL5` -> `Experts`.
4. Вставьте файл `CME_GEX_Levels_EA.mq5` в эту папку.
5. Откройте **MetaEditor** (клавиша `F4` в MT5).
6. В дереве файлов слева (Навигатор) в папке `Experts` найдите `CME_GEX_Levels_EA.mq5` и откройте его двойным кликом.
7. Нажмите кнопку **Компилировать** на панели инструментов сверху (или клавишу `F7`). Убедитесь, что в логе внизу нет ошибок (`0 errors, 0 warnings`).

---

## Часть 3. Запуск советника на графике

1. В MT5 откройте график **EURUSD** или **GBPUSD** (таймфрейм рекомендуется H1 или M15, но отрисовка будет работать на любом).
2. В окне **Навигатор** (`Ctrl + N`) найдите группу **Советники** и перетащите `CME_GEX_Levels_EA` на график.
3. В появившемся окне перейдите на вкладку **Входные параметры** и заполните настройки:
   * **GitHub Username**: `circlealgorythm`
   * **GitHub Repository**: `Options`
   * **GitHub Token (PAT)**: Вставьте ваш персональный токен доступа GitHub (Personal Access Token), созданный для этого приватного репозитория.
   * **Token Type**: `Bearer` (рекомендуется) или `token`.
   * **Visual Settings**: Настройте цвета для положительной гаммы (Call GEX), отрицательной гаммы (Put GEX) и Absolute Gamma.
4. Нажмите **ОК**.
5. Убедитесь, что кнопка **"Автовход" / "Авто-торговля" (Algo Trading)** на панели инструментов MT5 горит зеленым цветом.
6. Вкладка **Эксперты** в терминале покажет лог скачивания файла:
   * При успешном скачивании и парсинге вы увидите уровни на графике на текущий день.

---

## Часть 4. Локальный запуск Python-скрипта (Опционально)

Скрипт автоматически запускается раз в день через GitHub Actions. Если вам нужно запустить его вручную локально:

1. Откройте терминал в папке проекта (`c:\Users\circlealgorythm\.antigravity\bot_grid`).
2. Установите необходимые библиотеки (если еще не установлены):
   ```bash
   pip install -r requirements.txt
   ```
3. Запустите скрипт:
   ```bash
   python main.py
   ```
4. Сгенерированные файлы сохранятся в папку `data/` и будут готовы к пушу в репозиторий.

---

## Справка по скачиваемым отчетам CME (Daily Bulletin PDF Sections)

Пайплайн в `main.py` автоматически скачивает официальные ежедневные бюллетени CME Group. Все отчеты и секции публикуются на официальной странице CME Group Daily Bulletin:
* **Сайт-источник:** [CME Group Daily Bulletin](https://www.cmegroup.com/market-data/daily-bulletin.html) (директория для загрузки файлов: `https://www.cmegroup.com/daily_bulletin/current/`)

Секции по конкретным активам:
* **EURUSD (Euro FX):** 
  `Section39_Euro_FX_And_Cme$Index_Options.pdf` (совмещенный файл Call и Put).
* **GBPUSD (British Pound):** 
  `Section27_British_Pound_Call_Options.pdf` (Call) и `Section28_British_Pound_Put_Options.pdf` (Put).
* **XAUUSD (Gold):** 
  `Section64_Metals_Option_Products.pdf` (золотые опционные контракты: OG, GMW, GWT и др.).
* **NAS100 (Nasdaq-100):** 
  `Section40_Nasdaq_100_And_E_Mini_Nasdaq_100_Options.pdf` (контракты E-mini Nasdaq-100).
* **SPX500 (S&P 500):** 
  `Section47_E_Mini_S_And_P_500_Call_Options.pdf` (Call) и `Section48_E_Mini_S_And_P_500_Put_Options.pdf` (Put).
* **Cryptocurrency (BTCUSD & ETHUSD):** 
  `Section74_Cryptocurrency.pdf` (опционы на Bitcoin и Ether).
* **USDCAD (Canadian Dollar):** 
  `Section29_Canadian_Dollar_Call_Options.pdf` (Call) и `Section30_Canadian_Dollar_Put_Options.pdf` (Put, с автоматической инверсией страйков/премий в USDCAD).
