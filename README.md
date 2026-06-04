# SENTINEL AI

Локальный AI-ассистент для Windows. Работает полностью офлайн через Ollama.

## Возможности

| Модуль | Описание |
|--------|----------|
| **Agent** | Автономное управление компьютером: планирование задач, выполнение команд (клики, набор текста, поиск), SmartPilot разведка |
| **Aim Coach** | Тренер по прицелу для FPS-игр через CV-анализ экрана (CS2, Valorant, Aim Lab, KovaaK) |
| **Saga** | Интерактивная текстовая RPG с AI-генерацией миров, NPC и ASCII-арта |
| **Voice Translator** | Реальный-времени перевод речи через Whisper + Ollama с плавающими субтитрами |
| **Memory** | Персистентное JSON-хранилище с архивацией, компактификацией и отчётами |

## Быстрый старт

```bash
# 1. Установить зависимости
py -m pip install -r requirements.txt

# 2. Убедиться что Ollama запущена и есть модель
ollama pull qwen3:8b

# 3. Запустить диагностику
py doctor.py

# 4. Запустить
py main.py
```

## Структура проекта

```
ai/
  main.py                 # Точка входа
  gui.py                  # GUI (CustomTkinter, анимированное лицо)
  core.py                 # Центральное ядро (конфиг, Ollama, кадры)
  planner.py              # Планировщик задач (Ollama → команды)
  executor.py             # Исполнитель команд (pyautogui)
  smart_pilot.py          # Безопасная разведка экрана
  screen_sensor.py        # CV-анализ экрана (OpenCV/DXcam)
  aim_coach.py            # FPS-тренер
  memory.py               # JSON-хранилище
  neural_saga.py          # Текстовая RPG
  voice_translator.py     # Голосовой переводчик
  night_custodian.py      # Фоновое обслуживание
  system_info.py          # Информация о Windows
  immutable_truths.py     # Системные промпты
  game_knowledge.py       # База игровых профилей
  file_manager.py         # Файловые операции
  AgentToolbox.py         # Инструментарий (метрики CPU/GPU)
  log.py                  # Центральное логирование
  doctor.py               # Диагностика системы

  config.json             # Конфигурация
  requirements.txt        # Зависимости
  run_tests.bat           # Запуск тестов

  tests/                  # 62 теста (pytest)
```

## Тесты

```bash
py -m pytest tests/ -v
# или
run_tests.bat
```

## Диагностика

```bash
py doctor.py          # полная проверка
py doctor.py --quick  # без проверки модели Ollama
```

## Статус проекта

### ✅ Сделано
- GUI-каркас (customtkinter, 5 вкладок: Agent, Aim Coach, Saga, Translator, Memory)
- AnimatedFace — анимированное лицо (18 эмоций, слежение за мышью)
- Aim Coach — OCR считывание счёта, AI-советы (Ollama), 15 профилей игр, прозрачный оверлей
- Game Knowledge — база всех твоих игр с aliases и фокусом тренировки
- Истории (Saga) — полноэкранный ASCII-квест (4 темы, AI-сюжет, FPS-рендер, NPC, погода, день/ночь)
- Voice Translator — голосовой перевод RU→EN (Whisper + Ollama)
- Memory Store — персистентное JSON-хранилище
- Torch CUDA восстановлен, Moondream скачан, Tesseract 5.4 работает
- CLI `saga.py` — 4 режима (Agent, Watch, Trainer, Aim Coach)

### ❌ Сломано / недоделано
- **benchmark_providers.py** — написана система, НО не интегрирована в aim_coach.py
- **Истории — ASCII-зона + игра** — нет отдельного места под ASCII-арт, нет режима "игра рядом"

### 📋 ОЧЕРЕДЬ — Aim Coach (группы)

#### 🟢 CLICKING / Dynamic Clicking
- [ ] Распознавать сценарии: `pasu`, `1w6ts`, `1w4ts`, `popcorn`, `bounce shot`, `floating heads timing`
- [ ] Сравнивать с порогами Voltaic/Viscose/Riddler/Raw Input
- [ ] AI-совет: "у тебя pasu 85 — стабильный Gold, работай над чтением"
- [ ] Тупой: просто выводить "жми левую кнопку быстрее" без AI

#### 🟡 TRACKING
- [ ] Распознавать: `smoothbot`, `whisphere`, `controlsphere`, `air`, `pgti`, `leaptrack`, `ground plaza`
- [ ] Сравнивать с порогами (6 провайдеров уже загружены)
- [ ] AI-совет: "smoothness проседает — попробуй 30cm/360"
- [ ] Под each game: в CS:GO/Valorant tracking не главное, в OW/Deadlock — критично

#### 🔵 SWITCHING / Flick Tech
- [ ] Распознавать: `voxTargetSwitch`, `beanTS`, `floatTS`, `devTS`, `waldoTS`, `tamTargetSwitch`, `domiSwitch`, `pokeball`, `1w2ts`, `1w3ts`
- [ ] Сравнивать с порогами
- [ ] AI-совет: "target switching слабый — ставь рекорды в тех же играх"

#### 🟣 PRECISION
- [ ] Распознавать: `1wall5targets_pasu`, `pasu angelic`, `voxTargetClick`
- [ ] AI-совет: "микро-флик — это твой потолок в Marvel Rivals"

#### 🔴 UNIFIED AI REASONING
- [ ] AI видит ВСЕ сессии (KovaaK + CS:GO + OW + TF2 + FragPunk + Marvel Rivals + Deadlock)
- [ ] AI сам находит связи: "твой smoothbot упал → ты стал хуже трекать в OW"
- [ ] AI сравнивает несравнимое по логике: "pasu 80 (Gold) + flick в CS:GO медленный → у тебя проблема с микрокликами, не с трекингом"
- [ ] AI использует gemma4 для кросс-доменного анализа
- [ ] AI даёт советы не по шаблону, а по реальным пересечениям в твоих данных

#### 🟠 AIM TRAINER PROFILES
- [ ] **KovaaK's** — распознавание сценариев + сравнение с Voltaic/Viscose/Riddler
- [ ] **3D Aim Trainer** — парсинг результатов
- [ ] **Aimbeast** — парсинг кастомных карт
- [ ] **Furry Aim Trainer** — распознавание

#### ⚪ WEB SCRAPING / DATA MINING
- [ ] Разобрать Voltaic Season 5 полные таблицы (https://voltaic.gg / discord)
- [ ] Разобрать Riddler benchmarks (Google Sheets)
- [ ] Разобрать Raw Input benchmarks
- [ ] Разобрать Aim Lab built-in scores
- [ ] Спарсить Reddit r/FPSAimTrainer — тренды, советы
- [ ] Спарсить профили стримеров (mattyow, viscose, pingu, riddle)
- [ ] Собрать "тупые" метрики: "всего кликов", "средний HP", "K/D за день"
- [ ] Выгрузить всё в benchmark_providers.py как новые провайдеры

### 📋 ОЧЕРЕДЬ — Stories (ASCII + GUI)
- [ ] Выделить зону под ASCII-арт в окне историй
- [ ] Совместить игру и истории в одном окне (split view)
- [ ] Интеграция E-словаря эмоций с сюжетом
- [ ] reForge — генерация картинок к историям (по VRAM)

### 📋 ОЧЕРЕДЬ — Системное
- [ ] H: диск — 2 GB свободно, чистить/переносить ollama blobs (18 GB)
- [ ] Профили каждой игры — добавить в gui.py комбобокс
- [ ] Добавить скорость мыши (cm/360) в профиль
- [ ] Логирование всех сессий в SQLite вместо JSON




