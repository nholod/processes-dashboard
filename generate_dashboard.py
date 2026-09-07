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
        "agents": ["financier", "producer"],
        "chain": "Telegram-источники → Бобби → Продюсер → Алексей",
        "goal": "Не пропускать упоминания облигаций из портфелей Алексея.",
        "desc": "Бобби сохраняет новые сообщения, ищет совпадения по ISIN, выпуску и эмитенту и без анализа передаёт найденные цитаты Продюсеру. Продюсер отправляет одно сообщение Алексею.",
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
        "goal": "Формировать еженедельную сводку ФССП без потери исходных писем.",
        "desc": "Продюсер обновляет SQLite данными из Gmail, запускает формирование отчёта и отправляет готовый PDF. Письма в автоматическом режиме не удаляются.",
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
        "chain": "Реестр cron OpenClaw → генератор → GitHub → дашборд",
        "goal": "Поддерживать эту доску в актуальном состоянии без ручного редактирования.",
        "desc": "Продюсер ежедневно выгружает действующие и отключённые cron-задачи, обновляет карточки, создаёт Git-коммит и публикует данные на GitHub Pages.",
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
    "c2f52127-3d5c-4bf5-901b-394831f8f4e9",
    "379c1d61-e15b-4e3f-b3e0-fdede841c113",
    "1682e60e-23cc-4b46-968f-ba4823dc8dff",
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
