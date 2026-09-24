#!/usr/bin/env python3
"""Xtg — Telegram-bot: X/Y calculations plus square root, text-only replies."""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("xtg")

TOKEN = os.getenv("BOT_TOKEN", "").strip()
MAX_POINTS = int(os.getenv("MAX_POINTS", "500"))

POINT_RE = re.compile(
    r"""
    ^\s*
    (?:x\s*[=:]\s*)?
    ([+-]?\d+(?:[.,]\d+)?)
    (?:\s*[,;\s]\s*|\s+)
    (?:y\s*[=:]\s*)?
    ([+-]?\d+(?:[.,]\d+)?)
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

NUMBER_RE = re.compile(
    r"""
    ^\s*
    (?:sqrt|sqrt\s*of|\u221a)?\s*
    ([+-]?\d+(?:[.,]\d+)?)
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class Point:
    x: float
    y: float
    source: str
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class Store:
    def __init__(self) -> None:
        self._tracks: dict[int, list[Point]] = {}

    def add(self, chat_id: int, point: Point) -> list[Point]:
        track = self._tracks.setdefault(chat_id, [])
        track.append(point)
        if len(track) > MAX_POINTS:
            del track[: len(track) - MAX_POINTS]
        return track

    def get(self, chat_id: int) -> list[Point]:
        return self._tracks.get(chat_id, [])

    def clear(self, chat_id: int) -> int:
        return len(self._tracks.pop(chat_id, []))


store = Store()


def parse_xy(text: str) -> Optional[tuple[float, float]]:
    m = POINT_RE.match(text.replace("\u00a0", " "))
    if not m:
        return None
    x = float(m.group(1).replace(",", "."))
    y = float(m.group(2).replace(",", "."))
    return x, y


def parse_number(text: str) -> Optional[float]:
    m = NUMBER_RE.match(text.replace("\u00a0", " "))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def dist(a: Point, b: Point) -> float:
    return math.hypot(b.x - a.x, b.y - a.y)


def fmt(n: float) -> str:
    return f"{n:.6g}"


def sqrt_line(label: str, value: float) -> str:
    if value < 0:
        return f"√{label} — не определён (число < 0)"
    return f"√{label} = <code>{fmt(math.sqrt(value))}</code>"


def format_point_report(points: list[Point]) -> str:
    last = points[-1]
    r = math.hypot(last.x, last.y)
    lines = [
        f"<b>X</b> = <code>{fmt(last.x)}</code>",
        f"<b>Y</b> = <code>{fmt(last.y)}</code>",
        f"|r| = <code>{fmt(r)}</code>",
        sqrt_line("X", last.x),
        sqrt_line("Y", last.y),
        f"√(X²+Y²) = <code>{fmt(r)}</code>",
        f"source: {last.source} · pts: {len(points)}",
    ]
    if len(points) >= 2:
        prev = points[-2]
        dx = last.x - prev.x
        dy = last.y - prev.y
        step = dist(prev, last)
        path = sum(dist(a, b) for a, b in zip(points, points[1:]))
        from_start = dist(points[0], last)
        lines += [
            f"ΔX = <code>{dx:+.6g}</code> · ΔY = <code>{dy:+.6g}</code>",
            f"step = <code>{fmt(step)}</code> · √step = <code>{fmt(math.sqrt(step))}</code>",
            f"path = <code>{fmt(path)}</code> · from start = <code>{fmt(from_start)}</code>",
        ]
    return "\n".join(lines)


def format_sqrt_report(n: float) -> str:
    lines = [f"число = <code>{fmt(n)}</code>", sqrt_line("n", n)]
    if n >= 0:
        root = math.sqrt(n)
        lines.append(f"проверка: {fmt(root)}² = <code>{fmt(root * root)}</code>")
    return "\n".join(lines)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_html(
        "Xtg — расчёт X/Y и квадратного корня.\n\n"
        "Точка:\n"
        "• <code>10 20</code> или <code>10,20</code>\n"
        "• <code>x=10 y=20</code>\n"
        "• геолокация Telegram (X=lon, Y=lat)\n"
        "• live location — пересчёт на каждый пинг\n\n"
        "Одно число — только корень: <code>81</code> → √81 = 9\n\n"
        "/last — последняя точка\n"
        "/clear — сброс трека"
    )


async def cmd_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    points = store.get(update.effective_chat.id)
    if not points:
        await update.effective_message.reply_text("Точек пока нет.")
        return
    await update.effective_message.reply_html(format_point_report(points))


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    n = store.clear(update.effective_chat.id)
    await update.effective_message.reply_text(f"Сброшено точек: {n}.")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.effective_message.text or "").strip()
    parsed = parse_xy(text)
    if parsed:
        x, y = parsed
        points = store.add(update.effective_chat.id, Point(x=x, y=y, source="text"))
        await update.effective_message.reply_html(format_point_report(points))
        return
    n = parse_number(text)
    if n is not None:
        await update.effective_message.reply_html(format_sqrt_report(n))
        return
    await update.effective_message.reply_html(
        "Нужны два числа <code>12.5 -3</code>, одно число для √, или геолокация."
    )


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    loc = update.effective_message.location
    if not loc:
        return
    source = "live" if loc.live_period else "geo"
    points = store.add(
        update.effective_chat.id,
        Point(x=loc.longitude, y=loc.latitude, source=source),
    )
    await update.effective_message.reply_html(format_point_report(points))


async def on_live_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.edited_message
    if not msg or not msg.location:
        return
    loc = msg.location
    points = store.add(msg.chat_id, Point(x=loc.longitude, y=loc.latitude, source="live"))
    await msg.reply_html(format_point_report(points))


def main() -> None:
    if not TOKEN:
        raise SystemExit("Set BOT_TOKEN in .env or the environment.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("last", cmd_last))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(
        MessageHandler(filters.UpdateType.EDITED_MESSAGE & filters.LOCATION, on_live_edit)
    )
    logger.info("Xtg is running")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
