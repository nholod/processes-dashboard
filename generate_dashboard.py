#!/usr/bin/env python3
"""Build the public dashboard from the live OpenClaw cron registry."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "processes.json"
MOSCOW = ZoneInfo("Europe/Moscow")

AGENTS = {
    "main": "Бос",
    "assistant": "Ассистент",
    "analyst": "Аналитик",
    "financier": "Бобби",
    "editor": "Редактор",
    "scout": "Скаут",
    "producer": "Продюсер",
    "security": "Охранник",
    "smm": "SMM",
}

AGENT_ICONS = {
    "main": "🧠",
    "assistant": "🤝",
    "analyst": "📊",
    "financier": "💰",
    "editor": "✍️",
    "scout": "🔭",
    "producer": "🎬",
    "security": "🔐",
    "smm": "📣",
}

# Человекочитаемые карточки для действующих процессов. Технические статусы и
# расписания всё равно берутся из OpenClaw при каждом обновлении.
OVERRIDES = {
    "5f8c4a86-5605-4c6d-8176-55ba3501bad4": {
        "agents": ["financier"],
        "chain": "Telegram и Smart-Lab → скрипт Бобби → шаблонное уведомление → Алексей",
        "goal": "Не пропускать упоминания облигаций из портфелей Алексея.",
        "desc": "Детерминированный скрипт Бобби сохраняет новые материалы, ищет совпадения по ISIN, выпуску и эмитенту и при наличии результата отправляет Алексею одно уведомление по фиксированному шаблону. Для каждого источника показывает ✅ при успешной проверке или 🚫 при ошибке. ИИ не используется.",
    },
    "d685700a-2456-4750-93af-9fa331dad2cd": {
        "chain": "Технические проверки → Охранник → Алексей при критическом риске",
        "goal": "Рано обнаруживать угрозы и критические сбои OpenClaw.",
        "desc": "Охранник запускает аудит сервера и конфигурации каждый час. При штатном результате молчит, при подтверждённой критической проблеме сообщает Алексею.",
    },
    "2d886b40-a26e-4890-806f-4c482eeaa509": {
        "chain": "MOEX → Бобби → сравнение с ценой покупки → Алексей при |Δ| ≥ 2%",
        "goal": "Контролировать существенное изменение цен облигаций портфеля.",
        "desc": "Бобби получает цены MOEX по 53 ISIN и сравнивает их только с подтверждённой ценой покупки. Позиции без базы пропускаются; сообщение приходит лишь при отклонении от 2%.",
    },
    "d5907fa6-2de9-4789-abe1-af8233ecd327": {
        "agents": ["main", "financier"],
        "chain": "Бос → проверка цикла Бобби → один перезапуск → Алексей при сбое",
        "goal": "Не оставлять плановый мониторинг цен невыполненным.",
        "desc": "Через 45 минут после каждого ценового цикла Бос проверяет его результат. Реальный сбой вызывает не более одного перезапуска; штатный цикл не создаёт сообщений.",
    },
    "4a38174c-a0b2-46bd-8e68-069f26deb1a0": {
        "chain": "Google Sheets → Бобби → MOEX → обновление рыночных полей",
        "goal": "Поддерживать актуальные рыночные данные в трёх облигационных таблицах.",
        "desc": "Бобби читает состав портфелей из Google Sheets, получает данные MOEX и обновляет только рыночные поля. Средняя цена покупки не изменяется.",
    },
    "543a5a38-fa7b-4a2d-8e6a-ee3d6844f664": {
        "agents": ["producer", "analyst", "editor"],
        "chain": "Gmail → Продюсер → Аналитик → Брайн → PDF → Продюсер → Алексей",
        "goal": "Готовить проверенный еженедельный доклад к совещанию.",
        "desc": "Продюсер забирает новое письмо и вложения, Аналитик сравнивает данные с прошлой неделей, Брайн формирует PDF, а Продюсер проверяет файл и выполняет единственную доставку.",
    },
    "8fc32d48-1677-4e5a-9024-2a8938d59767": {
        "agents": ["producer", "scout"],
        "chain": "Продюсер → Чак (TG/VK/OK) → Продюсер → Алексей",
        "goal": "Еженедельно отслеживать активность и изменения у конкурентов.",
        "desc": "Чак собирает свежие данные Telegram, VK и OK за семь дней. Продюсер объединяет результаты, отмечает недоступные источники и отправляет один итоговый отчёт.",
    },
    "807225aa-55f5-420c-b525-d49bf4060e50": {
        "agents": ["producer", "scout"],
        "chain": "Продюсер-watchdog → проверка мониторинга конкурентов → один перезапуск",
        "goal": "Гарантировать завершение субботнего мониторинга конкурентов.",
        "desc": "Через 45 минут Продюсер проверяет основной цикл. При отсутствии запуска, ошибке или зависании выполняет один принудительный перезапуск и сообщает Алексею.",
    },
    "23d8fb14-abbd-4093-8ce2-00dac5d3bc64": {
        "chain": "Журналы всех агентов → Охранник → итоговый аудит → Алексей",
        "goal": "Показывать просроченные, зависшие и незавершённые задачи команды.",
        "desc": "Охранник по журналам и историям сессий считает статусы задач каждого агента, отдельно фиксирует подтверждённые проблемы и формирует один воскресный отчёт.",
    },
    "6ce63cb3-31b8-42b3-a939-6fcfe63bd056": {
        "chain": "Календари и первоисточники → Бобби → анализ → отчёт → Алексей",
        "goal": "Заранее оценивать облигационные размещения следующей недели.",
        "desc": "Бобби проходит календари и официальные источники, подтверждает параметры выпусков, сравнивает их с портфелями и формирует отчёт с доходностью, рисками и ссылками.",
    },
    "4c93e24a-b437-4450-9b50-792b006ec8d5": {
        "chain": "Реестр cron → Продюсер → проверка владельцев → Алексей при отклонении",
        "goal": "Контролировать правильное закрепление регламентных задач за агентами.",
        "desc": "Продюсер сверяет владельцев cron с утверждённым распределением. Ничего автоматически не меняет и сообщает только о найденных отклонениях.",
    },
    "85192c8b-82c0-4e24-8d79-e2a15491764f": {
        "agents": ["producer", "analyst"],
        "chain": "Gmail → база ФССП → аналитические скрипты → PDF → Продюсер → Алексей",
        "goal": "Еженедельно анализировать почтовые сообщения ФССП и формировать проверенный отчёт.",
        "desc": "Продюсер обновляет SQLite данными из Gmail и формирует PDF. После подтверждённой загрузки всех релевантных данных и проверки PDF изученные письма, зафиксированные в snapshots, перемещаются в корзину Gmail; неподтверждённые письма не затрагиваются.",
    },
    "5cb6b5f7-54ba-4e99-af90-f4dc8b2976d6": {
        "agents": ["producer", "smm"],
    },
    "180d8e2f-5863-42d8-9ef9-8fac4e31fae2": {
        "agents": ["producer", "smm"],
    },
    "11d2a390-fa03-42d7-a1c9-f9d501d2d5cf": {
        "agents": ["main", "financier"],
        "chain": "Бос → проверка отчёта Бобби → повторный анализ при неполных источниках",
        "goal": "Получать полный отчёт по размещениям даже при временной недоступности источников.",
        "desc": "Бос проверяет итог еженедельного анализа. При ошибке, отсутствии запуска или статусе PARTIAL_SOURCE выполняет ровно один повторный запуск задачи Бобби.",
    },
    "c2f52127-3d5c-4bf5-901b-394831f8f4e9": {
        "agents": ["financier", "editor"],
        "chain": "Google Sheets → Бобби → финансовый анализ → Брайн (PDF) → Алексей",
        "goal": "Ежемесячно оценивать личные финансы, активы и уязвимости.",
        "desc": "Бобби читает таблицу д-р1 без изменений, анализирует доходы, расходы, накопления, детей и недвижимость. Брайн формирует PDF для итоговой доставки.",
    },
    "379c1d61-e15b-4e3f-b3e0-fdede841c113": {
        "agents": ["financier", "editor"],
        "chain": "Google Sheets → Бобби → анализ вкладки «Дети» → Брайн (PDF) → Алексей",
        "goal": "Контролировать целевой капитал и инвестиции для детей.",
        "desc": "Бобби определяет последний полный месяц и анализирует вкладку «Дети» в режиме чтения. Брайн собирает результаты в PDF.",
    },
    "8912d0c3-11b2-45ca-be09-ee9a87320dec": {
        "agents": ["financier", "editor"],
        "chain": "Google Sheets + MOEX → Бобби → анализ портфелей → Брайн (PDF) → Алексей",
        "goal": "Ежемесячно оценивать портфели ААА, ОФЗ и ВДО.",
        "desc": "Бобби обновляет рыночные поля и анализирует стоимость, YTM, дюрацию, купоны и P/L по позициям с подтверждённой базой. Результат оформляется в PDF.",
    },
    "1682e60e-23cc-4b46-968f-ba4823dc8dff": {
        "chain": "Календарь + Gmail + Obsidian + погода → Ассистент → Алексей",
        "goal": "Давать краткую проверенную сводку на начало дня.",
        "desc": "Ассистент собирает события, важные письма, планы и погоду. Недоступные источники помечаются явно; события без отдельного запроса не изменяются.",
    },
    "4028d20f-3578-4fe0-8030-0355ca38b8c0": {
        "chain": "Реестр cron OpenClaw → Бос → генератор → GitHub → дашборд",
        "goal": "Поддерживать эту доску в актуальном состоянии без ручного редактирования.",
        "desc": "Бос ежедневно выгружает действующие и отключённые cron-задачи, обновляет карточки, создаёт Git-коммит и публикует данные на GitHub Pages.",
    },
    "aca39778-4bf0-4c85-b98a-51b4bfe53afb": {
        "agents": ["producer", "analyst", "editor"],
        "chain": "Снимок АРМ «Среда» → Аналитик → Брайн (PDF) → Продюсер → Алексей",
        "goal": "Готовить недельный аналитический доклад по данным АРМ «Среда».",
        "desc": "При наличии свежей базы Аналитик обрабатывает данные, Брайн формирует PDF, Продюсер проверяет и отправляет итог. Старые данные не используются.",
    },
    "ae444a2b-a797-4853-8229-d8891ec11d70": {
        "agents": ["scout", "financier", "producer"],
        "chain": "База Telegram Чака → Бобби → официальные источники → Продюсер → Алексей",
        "goal": "Подтверждать существенные облигационные риски официальными источниками.",
        "desc": "Бобби разбирает очередь сигналов, сопоставляет их с портфелями, фиксирует решения в журнале и передаёт подтверждённые события Продюсеру. Сейчас задача отключена.",
    },
    "b4ad76b6-10a3-4fd7-86cf-c5f6a85f2aee": {
        "agents": ["scout", "analyst"],
        "chain": "АРМ «Среда» → Чак → снимок → Аналитик",
        "goal": "Собирать свежие данные АРМ «Среда» для недельного анализа.",
        "desc": "Чак проверяет доверенный браузерный профиль и 2FA, сохраняет идемпотентный недельный снимок и передаёт его Аналитику. Сейчас задача отключена до восстановления доступа.",
    },
}

DAYS = {
    "0": "вс",
    "1": "пн",
    "2": "вт",
    "3": "ср",
    "4": "чт",
    "5": "пт",
    "6": "сб",
    "7": "вс",
}

FSSP_IDS = {
    "543a5a38-fa7b-4a2d-8e6a-ee3d6844f664",
    "85192c8b-82c0-4e24-8d79-e2a15491764f",
    "aca39778-4bf0-4c85-b98a-51b4bfe53afb",
    "b4ad76b6-10a3-4fd7-86cf-c5f6a85f2aee",
}

SECURITIES_IDS = {
    "5f8c4a86-5605-4c6d-8176-55ba3501bad4",
    "2d886b40-a26e-4890-806f-4c482eeaa509",
    "d5907fa6-2de9-4789-abe1-af8233ecd327",
    "4a38174c-a0b2-46bd-8e68-069f26deb1a0",
    "6ce63cb3-31b8-42b3-a939-6fcfe63bd056",
    "11d2a390-fa03-42d7-a1c9-f9d501d2d5cf",
    "8912d0c3-11b2-45ca-be09-ee9a87320dec",
    "ae444a2b-a797-4853-8229-d8891ec11d70",
}

YANA_IDS = {
    "180d8e2f-5863-42d8-9ef9-8fac4e31fae2",
    "5cb6b5f7-54ba-4e99-af90-f4dc8b2976d6",
    "8fc32d48-1677-4e5a-9024-2a8938d59767",
    "807225aa-55f5-420c-b525-d49bf4060e50",
}

PERSONAL_IDS = {
    "9484101d-b301-4440-975d-6c9746e87bbe",
    "1a676107-a719-4a76-8db0-e7e58d539ed6",
    "c2f52127-3d5c-4bf5-901b-394831f8f4e9",
    "379c1d61-e15b-4e3f-b3e0-fdede841c113",
    "1682e60e-23cc-4b46-968f-ba4823dc8dff",
}

# Пошаговое представление процессов для карточек дашборда. Каждый шаг отвечает
# на два вопроса: что делается и кто именно это делает.
PROCESS_STEPS = {
    "9484101d-b301-4440-975d-6c9746e87bbe": [
        ("Запустить вечернюю рефлексию по расписанию", "OpenClaw"),
        ("Задать шесть вопросов для подведения итогов дня", "Ассистент"),
    ],
    "1682e60e-23cc-4b46-968f-ba4823dc8dff": [
        ("Запустить утренний сбор данных", "OpenClaw"),
        ("Собрать календарь, важные письма, планы из Obsidian и погоду", "Ассистент"),
        ("Проверить полноту источников и отметить недоступные данные", "Ассистент"),
        ("Сформировать и отправить утренний брифинг", "Ассистент"),
    ],
    "cdab620b-19fe-4fac-9be7-fc24aae64c51": [
        ("Проверить наличие ответа или вечерней заметки", "Ассистент"),
        ("При отсутствии результата отправить одно напоминание", "Ассистент"),
    ],
    "1a676107-a719-4a76-8db0-e7e58d539ed6": [
        ("Определить текущий день 35-дневной программы", "Ассистент"),
        ("Подготовить короткое упражнение дня", "Ассистент"),
        ("Отправить тренировку Алексею", "Ассистент"),
    ],
    "4a38174c-a0b2-46bd-8e68-069f26deb1a0": [
        ("Прочитать состав облигационных портфелей", "Бобби"),
        ("Получить актуальные рыночные данные MOEX", "Бобби"),
        ("Обновить только рыночные поля в Google Sheets", "Бобби"),
        ("Сохранить неизменной среднюю цену покупки", "Бобби"),
    ],
    "379c1d61-e15b-4e3f-b3e0-fdede841c113": [
        ("Определить последний полностью завершённый месяц", "Бобби"),
        ("Прочитать вкладку «Дети» в Google Sheets", "Бобби"),
        ("Рассчитать динамику накоплений и отклонение от целей", "Бобби"),
        ("Оформить результаты в PDF", "Брайн"),
        ("Передать готовый отчёт Алексею", "Бобби"),
    ],
    "c2f52127-3d5c-4bf5-901b-394831f8f4e9": [
        ("Прочитать финансовую таблицу д-р1 без изменений", "Бобби"),
        ("Проанализировать доходы, расходы, накопления, детей и недвижимость", "Бобби"),
        ("Оформить результаты в PDF", "Брайн"),
        ("Передать готовый отчёт Алексею", "Бобби"),
    ],
    "8912d0c3-11b2-45ca-be09-ee9a87320dec": [
        ("Получить состав портфелей и актуальные данные MOEX", "Бобби"),
        ("Обновить рыночные показатели", "Бобби"),
        ("Проанализировать стоимость, YTM, дюрацию, купоны и P/L", "Бобби"),
        ("Оформить результаты в PDF", "Брайн"),
        ("Передать готовый отчёт Алексею", "Бобби"),
    ],
    "6ce63cb3-31b8-42b3-a939-6fcfe63bd056": [
        ("Собрать размещения следующей недели из календарей", "Бобби"),
        ("Подтвердить параметры по первичным источникам", "Бобби"),
        ("Сравнить выпуски с целями и портфелями", "Бобби"),
        ("Сформировать отчёт с доходностью, рисками и ссылками", "Бобби"),
        ("Отправить итог Алексею", "Бобби"),
    ],
    "5f8c4a86-5605-4c6d-8176-55ba3501bad4": [
        ("Дочитать всё после сохранённого курсора в Telegram и Smart-Lab", "Бобби"),
        ("Сохранить записи и обновить курсоры без пропусков и дублей", "Бобби"),
        ("Найти совпадения по ISIN, выпуску и эмитенту", "Бобби"),
        ("Сформировать уведомление с точной цитатой и статусом каждого адреса: ✅ или 🚫", "Скрипт Бобби"),
        ("Отправить одно сообщение Алексею через Telegram-аккаунт Бобби", "Скрипт Бобби"),
    ],
    "2d886b40-a26e-4890-806f-4c482eeaa509": [
        ("Получить цены 53 облигаций с MOEX", "Бобби"),
        ("Сопоставить цены с подтверждённой ценой покупки", "Бобби"),
        ("Рассчитать отклонения и исключить позиции без базы", "Бобби"),
        ("Сообщить Алексею только об отклонениях не менее 2%", "Бобби"),
    ],
    "d5907fa6-2de9-4789-abe1-af8233ecd327": [
        ("Проверить результат планового ценового цикла через 45 минут", "Бос"),
        ("При подтверждённом сбое выполнить не более одного перезапуска", "Бос"),
        ("Сообщить Алексею только о сбое или результате восстановления", "Бос"),
    ],
    "11d2a390-fa03-42d7-a1c9-f9d501d2d5cf": [
        ("Проверить итог анализа новых размещений", "Бос"),
        ("При ошибке или неполных источниках запустить один повторный анализ", "Бос"),
        ("Зафиксировать окончательный результат", "Бос"),
    ],
    "4028d20f-3578-4fe0-8030-0355ca38b8c0": [
        ("Выгрузить действующие и отключённые cron-задачи", "Бос"),
        ("Сопоставить задачи с направлениями и описаниями", "Бос"),
        ("Пересобрать данные дашборда", "Бос"),
        ("Создать Git-коммит и опубликовать обновление на GitHub Pages", "Бос"),
    ],
    "d685700a-2456-4750-93af-9fa331dad2cd": [
        ("Запустить технический аудит сервера и конфигурации", "Охранник"),
        ("Проверить и подтвердить найденные риски", "Охранник"),
        ("При штатном результате не отправлять сообщение", "Охранник"),
        ("При критическом риске уведомить Алексея", "Охранник"),
    ],
    "23d8fb14-abbd-4093-8ce2-00dac5d3bc64": [
        ("Собрать журналы и истории сессий всех агентов", "Охранник"),
        ("Выявить просроченные, зависшие и незавершённые задачи", "Охранник"),
        ("Отделить подтверждённые проблемы от технического шума", "Охранник"),
        ("Отправить Алексею один воскресный отчёт", "Охранник"),
    ],
    "5cb6b5f7-54ba-4e99-af90-f4dc8b2976d6": [
        ("Запустить ежедневный цикл в установленное время", "OpenClaw"),
        ("Найти утверждённый недельный пакет и проверить состояние", "Продюсер"),
        ("Проверить текст, изображение, хэши, OCR и допустимость публикации", "Лара"),
        ("Опубликовать один пост и записать message_id", "Лара"),
        ("Проверить итог и сообщить окончательный статус", "Продюсер"),
    ],
    "543a5a38-fa7b-4a2d-8e6a-ee3d6844f664": [
        ("Получить новое письмо и вложения из Gmail", "Продюсер"),
        ("Сравнить показатели с предыдущей неделей", "Аналитик"),
        ("Сформировать итоговый PDF", "Брайн"),
        ("Проверить PDF и полноту данных", "Продюсер"),
        ("Отправить один готовый отчёт Алексею", "Продюсер"),
    ],
    "85192c8b-82c0-4e24-8d79-e2a15491764f": [
        ("Получить все релевантные письма ФССП без удаления", "Аналитик"),
        ("Загрузить данные писем в SQLite и подтвердить их в snapshots", "Аналитик"),
        ("Сформировать и технически проверить PDF", "Аналитик"),
        ("Переместить в корзину только подтверждённо обработанные письма", "Аналитик"),
        ("Проверить результат и доставить отчёт Алексею", "Продюсер"),
    ],
    "180d8e2f-5863-42d8-9ef9-8fac4e31fae2": [
        ("Запустить ежедневный цикл Дзена", "OpenClaw"),
        ("Найти утверждённый state и выполнить API-аудит материала текущего дня", "Продюсер"),
        ("Проверить статус, время, публичную ссылку, обложку, форматирование и отсутствие дубля", "Продюсер"),
        ("По субботам подготовить исследование, семь текстов и семь обложек", "Лара"),
        ("Проверить недельный пакет и передать его на согласование Яне", "Продюсер"),
        ("После согласования синхронизировать семь публикаций через API и повторно провести аудит", "Продюсер"),
        ("Отправить Алексею один итоговый статус", "Продюсер"),
    ],
    "4c93e24a-b437-4450-9b50-792b006ec8d5": [
        ("Выгрузить реестр cron-задач", "Продюсер"),
        ("Сравнить фактических владельцев с утверждённым распределением", "Продюсер"),
        ("При отсутствии отклонений завершить без сообщения", "Продюсер"),
        ("При отклонении сообщить Алексею название и требуемого владельца", "Продюсер"),
    ],
    "ae444a2b-a797-4853-8229-d8891ec11d70": [
        ("Прочитать очередь облигационных сигналов Чака", "Бобби"),
        ("Сопоставить сигналы с портфелями", "Бобби"),
        ("Подтвердить существенные события по официальным источникам", "Бобби"),
        ("Передать подтверждённые риски Продюсеру", "Бобби"),
        ("Проверить и направить итог Алексею", "Продюсер"),
    ],
    "5e377299-1732-49d1-9d14-6358fd552c63": [
        ("Прочитать состояние Telegram-цикла после публикации", "Бос"),
        ("Проверить статус, message_id и отсутствие незавершённой попытки", "Бос"),
        ("Сообщить только о подтверждённом отклонении", "Бос"),
    ],
    "aca39778-4bf0-4c85-b98a-51b4bfe53afb": [
        ("Проверить наличие свежего снимка АРМ «Среда»", "Продюсер"),
        ("Обработать данные и рассчитать недельные показатели", "Аналитик"),
        ("Сформировать итоговый PDF", "Брайн"),
        ("Проверить и отправить отчёт Алексею", "Продюсер"),
    ],
    "807225aa-55f5-420c-b525-d49bf4060e50": [
        ("Проверить завершение мониторинга конкурентов через 45 минут", "Продюсер"),
        ("При подтверждённом сбое выполнить один перезапуск", "Продюсер"),
        ("Сообщить Алексею результат восстановления", "Продюсер"),
    ],
    "8fc32d48-1677-4e5a-9024-2a8938d59767": [
        ("Запустить недельный мониторинг конкурентов", "Продюсер"),
        ("Собрать свежие данные Telegram, VK и OK", "Чак"),
        ("Объединить результаты и отметить недоступные источники", "Продюсер"),
        ("Отправить Алексею один итоговый отчёт", "Продюсер"),
    ],
    "b4ad76b6-10a3-4fd7-86cf-c5f6a85f2aee": [
        ("Проверить браузерный профиль и готовность 2FA", "Чак"),
        ("Получить свежие данные АРМ «Среда»", "Чак"),
        ("Сохранить идемпотентный недельный снимок", "Чак"),
        ("Передать снимок для анализа", "Чак"),
        ("Принять снимок в аналитический контур", "Аналитик"),
    ],
}

# Дашборд опубликован на GitHub Pages, поэтому адреса перечисляются только из
# явного безопасного списка. Приватные таблицы и внутренние системы отмечаются,
# но их фактические URL в публичный JSON не попадают.
GMAIL = ("Gmail", "https://mail.google.com/", "public")
GOOGLE_CALENDAR = ("Google Calendar", "https://calendar.google.com/", "public")
GOOGLE_SHEETS_PRIVATE = ("Google Sheets — рабочие таблицы", None, "private")
OBSIDIAN_LOCAL = ("Obsidian — локальная база знаний", None, "local")
MOEX_ISS = ("MOEX ISS API — рынок облигаций", "https://iss.moex.com/iss/engines/stock/markets/bonds", "public")

PORTFOLIO_TG_RESOURCES = [
    ("Telegram — GoodBonds", "https://t.me/GoodBonds", "public"),
    ("Telegram — oblig_flood", "https://t.me/oblig_flood", "public"),
    ("Telegram — Bonds_Wizzard_Chat", "https://t.me/Bonds_Wizzard_Chat", "public"),
    ("Telegram — philippovich_bonds", "https://t.me/philippovich_bonds", "public"),
    ("Telegram — ludomanechka", "https://t.me/ludomanechka", "public"),
    ("Telegram — cbonds", "https://t.me/cbonds", "public"),
    ("Telegram — probonds", "https://t.me/probonds", "public"),
    ("Telegram — ivolgavdo", "https://t.me/ivolgavdo", "public"),
    ("Telegram — marythebond", "https://t.me/marythebond", "public"),
    ("Smart-Lab — все блоги", "https://smart-lab.ru/allblog/", "public"),
    ("Smart-Lab — форум облигаций", "https://smart-lab.ru/bonds/", "public"),
]

PLACEMENT_RESOURCES = [
    ("Smart-Lab — календарь облигаций", "https://smart-lab.ru/calendar/bonds/", "public"),
    ("Cbonds — ближайшие размещения", "https://cbonds.ru/calendar/nearest_placements/", "public"),
    ("Bonds Lab — размещения", "https://www.bonds-lab.ru/placements", "public"),
    ("Корпоративные облигации — публичные размещения", "https://corpbonds.ru/public_offering", "public"),
    ("Telegram — mozginvest", "https://t.me/mozginvest", "public"),
    ("Telegram — barbados_bond", "https://t.me/barbados_bond", "public"),
    ("Telegram — BondGPT_RU", "https://t.me/BondGPT_RU", "public"),
]

OFFICIAL_BOND_RESOURCES = [
    MOEX_ISS,
    ("НРД — новости", "https://nsddata.ru/ru/news/", "public"),
    ("Центр раскрытия корпоративной информации", "https://www.e-disclosure.ru/", "public"),
    ("Эксперт РА", "https://raexpert.ru/", "public"),
]

COMPETITOR_RESOURCES = [
    ("Telegram — bankrotstvoVE", "https://t.me/bankrotstvoVE", "public"),
    ("Telegram — sudpraktik_bankrot_demo", "https://t.me/sudpraktik_bankrot_demo", "public"),
    ("Telegram — danilexpert", "https://t.me/danilexpert", "public"),
    ("Telegram — rusrvz", "https://t.me/rusrvz", "public"),
    ("Telegram — fssp_gov", "https://t.me/fssp_gov", "public"),
    ("Telegram — fssp_sp", "https://t.me/fssp_sp", "public"),
    ("VK — Услуги по банкротству", "https://vk.com/public183685628", "public"),
    ("VK — Банкротство онлайн", "https://vk.com/bankrotstvo_online", "public"),
    ("VK — Ситора Мажидова", "https://vk.com/sitora_mazhidova", "public"),
    ("VK — ПЛАН Б", "https://vk.com/planb_bankrot", "public"),
    ("VK — ФИКСБАНКРОТ", "https://vk.com/fixbankrot", "public"),
    ("VK — UKFES", "https://vk.com/ukfes", "public"),
    ("OK — Юрист для Людей", "https://ok.ru/group/55384451317910", "public"),
    ("OK — Банкротство / списание долгов", "https://ok.ru/group/70000043606032", "public"),
    ("OK — Юрист: списание долгов", "https://ok.ru/group/70000032312763", "public"),
    ("OK — Банкротство по РФ", "https://ok.ru/group/53392011886739", "public"),
    ("OK — Банкротство физических лиц", "https://ok.ru/group/70000000437557", "public"),
    ("OK — Банкротство физических лиц 2", "https://ok.ru/group/70000048162255", "public"),
    ("OK — Банкротство физических лиц 3", "https://ok.ru/group/70000043078157", "public"),
    ("OK — Банкротство физических лиц 4", "https://ok.ru/group/70000004980700", "public"),
    ("OK — Законное списание долгов", "https://ok.ru/group/70000041741826", "public"),
    ("OK — Бизнес-Юрист", "https://ok.ru/group/70000001420593", "public"),
    ("OK — Юрист Кристина", "https://ok.ru/group/70000003997432", "public"),
    ("OK — Списание долгов", "https://ok.ru/group/70000043529653", "public"),
    ("OK — Банкротство: малая группа", "https://ok.ru/group/70000051996106", "public"),
    ("OK — Банкротство физических лиц 5", "https://ok.ru/group/70000043936642", "public"),
    ("OK — Банкротство граждан", "https://ok.ru/group/53919425364107", "public"),
    ("OK — Резиденция Права", "https://ok.ru/group/70000047316948", "public"),
    ("OK — Finance Expert", "https://ok.ru/group/54099031687350", "public"),
    ("OK — Фонд Защиты Должников", "https://ok.ru/group/60090904019025", "public"),
    ("OK — Центр списания долгов", "https://ok.ru/group/70000006220383", "public"),
    ("OK — Обнулим кредиты", "https://ok.ru/group/70000042529379", "public"),
    ("OK — Банкротство физических лиц 6", "https://ok.ru/group/70000050042089", "public"),
    ("OK — Адвокат: долги и суды", "https://ok.ru/group/70000049704180", "public"),
]

PROCESS_RESOURCES = {
    "1682e60e-23cc-4b46-968f-ba4823dc8dff": [
        GOOGLE_CALENDAR,
        GMAIL,
        OBSIDIAN_LOCAL,
        ("Сервис прогноза погоды wttr.in", "https://wttr.in/", "public"),
    ],
    "4a38174c-a0b2-46bd-8e68-069f26deb1a0": [GOOGLE_SHEETS_PRIVATE, MOEX_ISS],
    "379c1d61-e15b-4e3f-b3e0-fdede841c113": [GOOGLE_SHEETS_PRIVATE],
    "c2f52127-3d5c-4bf5-901b-394831f8f4e9": [GOOGLE_SHEETS_PRIVATE],
    "8912d0c3-11b2-45ca-be09-ee9a87320dec": [GOOGLE_SHEETS_PRIVATE, MOEX_ISS],
    "6ce63cb3-31b8-42b3-a939-6fcfe63bd056": PLACEMENT_RESOURCES,
    "5f8c4a86-5605-4c6d-8176-55ba3501bad4": PORTFOLIO_TG_RESOURCES,
    "2d886b40-a26e-4890-806f-4c482eeaa509": [MOEX_ISS],
    "4028d20f-3578-4fe0-8030-0355ca38b8c0": [
        ("Публичный дашборд", "https://nholod.github.io/processes-dashboard/", "public"),
        ("GitHub-репозиторий дашборда", "https://github.com/nholod/processes-dashboard", "public"),
    ],
    "5cb6b5f7-54ba-4e99-af90-f4dc8b2976d6": [
        ("Telegram-канал Яны", "https://t.me/yanapravo", "public"),
        ("Telegram Bot API", "https://api.telegram.org/", "public"),
    ],
    "543a5a38-fa7b-4a2d-8e6a-ee3d6844f664": [GMAIL],
    "85192c8b-82c0-4e24-8d79-e2a15491764f": [GMAIL],
    "180d8e2f-5863-42d8-9ef9-8fac4e31fae2": [
        ("Дзен-канал Яны", "https://dzen.ru/id/6657b50d7e3fa97193655716", "public"),
    ],
    "ae444a2b-a797-4853-8229-d8891ec11d70": PORTFOLIO_TG_RESOURCES + OFFICIAL_BOND_RESOURCES,
    "aca39778-4bf0-4c85-b98a-51b4bfe53afb": [
        ("АРМ «Среда»", None, "private"),
    ],
    "8fc32d48-1677-4e5a-9024-2a8938d59767": COMPETITOR_RESOURCES,
    "b4ad76b6-10a3-4fd7-86cf-c5f6a85f2aee": [
        ("АРМ «Среда»", None, "private"),
    ],
}


def direction_for(job_id: str) -> str:
    if job_id in FSSP_IDS:
        return "fssp"
    if job_id in SECURITIES_IDS:
        return "securities"
    if job_id in YANA_IDS:
        return "yana"
    if job_id in PERSONAL_IDS:
        return "personal"
    return "system"


def run_json(*args: str) -> dict:
    result = subprocess.run(
        ["openclaw", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    return json.loads(result.stdout)


def hhmm(hour: str, minute: str) -> str:
    return f"{int(hour):02d}:{int(minute):02d}"


def schedule_label(schedule: dict) -> str:
    kind = schedule.get("kind")
    tz = schedule.get("tz") or "локальное время сервера"
    suffix = " МСК" if tz == "Europe/Moscow" else f" ({tz})"

    if kind == "cron":
        expr = schedule.get("expr", "")
        fields = expr.split()
        if len(fields) == 5:
            minute, hour, dom, month, dow = fields
            if minute.startswith("*/") and hour == dom == month == dow == "*":
                return f"Каждые {minute[2:]} минут"
            if hour == dom == month == dow == "*" and minute.isdigit():
                return f"Ежечасно в :{int(minute):02d}"
            if dom == month == dow == "*" and minute.isdigit():
                times = [hhmm(h, minute) for h in hour.split(",")]
                return "Ежедневно " + ", ".join(times) + suffix
            if dom == month == "*" and dow in DAYS and minute.isdigit() and hour.isdigit():
                return f"Еженедельно, {DAYS[dow]} {hhmm(hour, minute)}{suffix}"
            if month == dow == "*" and dom.isdigit() and minute.isdigit() and hour.isdigit():
                return f"Ежемесячно, {int(dom)}-го в {hhmm(hour, minute)}{suffix}"
        return f"Cron: {expr}" + suffix

    if kind == "every":
        ms = int(schedule.get("everyMs", 0))
        if ms and ms % 3_600_000 == 0:
            return f"Каждые {ms // 3_600_000} ч"
        if ms and ms % 60_000 == 0:
            return f"Каждые {ms // 60_000} мин"
        return f"Интервал {ms} мс"

    if kind == "at":
        return f"Однократно: {schedule.get('at', '—')}"
    return "Расписание не указано"


def format_run(timestamp_ms: int | None, status: str | None) -> str:
    if not timestamp_ms:
        return "Запусков ещё не было"
    when = datetime.fromtimestamp(timestamp_ms / 1000, MOSCOW).strftime("%d.%m.%Y %H:%M")
    labels = {"ok": "успешно", "error": "ошибка", "failed": "ошибка"}
    return f"{when} МСК — {labels.get(status or '', status or 'статус неизвестен')}"


def format_next(timestamp_ms: int | None, enabled: bool) -> str:
    if not enabled:
        return "Отключён"
    if not timestamp_ms:
        return "Ожидает расчёта"
    return datetime.fromtimestamp(timestamp_ms / 1000, MOSCOW).strftime("%d.%m.%Y %H:%M МСК")


def process_from_job(job: dict) -> dict:
    agent_id = job.get("agentId") or "main"
    owner = AGENTS.get(agent_id, agent_id)
    enabled = bool(job.get("enabled"))
    state = job.get("state") or {}
    description = job.get("description") or "Регламентная задача OpenClaw."
    job_id = job.get("id", "")
    timezone = (job.get("schedule") or {}).get("tz") or "не указан"

    process = {
        "id": job_id,
        "name": job.get("name") or "Без названия",
        "status": "active" if enabled else "pending",
        "icon": AGENT_ICONS.get(agent_id, "🔄"),
        "schedule": schedule_label(job.get("schedule") or {}),
        "chain": f"OpenClaw cron → {owner}",
        "last": format_run(state.get("lastRunAtMs"), state.get("lastRunStatus")),
        "next": format_next(state.get("nextRunAtMs"), enabled),
        "owner": owner,
        "goal": description,
        "desc": description,
        "notes": f"ID: {job_id}. Часовой пояс: {timezone}. "
        + ("Задача включена." if enabled else "Задача отключена."),
        "type": "individual",
        "agents": [agent_id],
        "runner": "cron",
    }
    process.update(OVERRIDES.get(job_id, {}))
    raw_steps = PROCESS_STEPS.get(job_id) or [
        ("Запустить задачу по расписанию", "OpenClaw"),
        (description, owner),
        ("Зафиксировать результат выполнения", "OpenClaw"),
    ]
    process["steps"] = [
        {"action": action, "actor": actor} for action, actor in raw_steps
    ]
    process["resources"] = [
        {"label": label, "url": url, "access": access}
        for label, url, access in PROCESS_RESOURCES.get(job_id, [])
    ]
    process["chain"] = " → ".join(
        f"{index}. {action} — {actor}"
        for index, (action, actor) in enumerate(raw_steps, start=1)
    )
    process["type"] = "group" if len(process.get("agents", [])) > 1 else "individual"
    process["direction"] = direction_for(job_id)
    return process


def main() -> None:
    jobs = run_json("cron", "list", "--all", "--json").get("jobs", [])
    processes = [process_from_job(job) for job in jobs]
    processes.sort(key=lambda item: (item["status"] != "active", item["owner"], item["name"]))

    counts = {
        "active": sum(item["status"] == "active" for item in processes),
        "pending": sum(item["status"] == "pending" for item in processes),
        "completed": sum(item["status"] == "completed" for item in processes),
    }
    data = {
        "generated_at": datetime.now(MOSCOW).isoformat(timespec="seconds"),
        "summary": counts,
        "processes": processes,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="processes-", suffix=".json", dir=OUTPUT.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temp_name, OUTPUT)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

    print(f"OK: сохранено задач: {len(processes)}")


if __name__ == "__main__":
    main()
