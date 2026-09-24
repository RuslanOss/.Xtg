#!/usr/bin/env python3
"""Xtg — Telegram-bot that tracks X/Y coordinates in real time and replies with a plot."""

from __future__ import annotations

import io
import logging
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from telegram import InputFile, Update
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
        n = len(self._tracks.pop(chat_id, []))
        return n


store = Store()


def parse_xy(text: str) -> Optional[tuple[float, float]]:
    m = POINT_RE.match(text.replace("\u00a0", " "))
    if not m:
        return None
    x = float(m.group(1).replace(",", "."))
    y = float(m.group(2).replace(",", "."))
    return x, y


def dist(a: Point, b: Point) -> float:
    return math.hypot(b.x - a.x, b.y - a.y)


def render_plot(points: list[Point]) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [p.x for p in points]
    ys = [p.y for p in points]

    fig, ax = plt.subplots(figsize=(8, 6), dpi=140)
    fig.patch.set_facecolor("#0f1419")
    ax.set_facecolor("#15202b")

    if len(points) == 1:
        ax.scatter(xs, ys, s=90, c="#1d9bf0", zorder=3)
    else:
        ax.plot(xs, ys, color="#1d9bf0", linewidth=2, marker="o", markersize=5, zorder=2)
        ax.scatter([xs[0]], [ys[0]], s=80, c="#00ba7c", zorder=3, label="start")
        ax.scatter([xs[-1]], [ys[-1]], s=110, c="#f4212e", zorder=4, label="now")
        ax.legend(facecolor="#15202b", edgecolor="#38444d", labelcolor="#e7e9ea")

    ax.set_xlabel("X", color="#8b98a5")
    ax.set_ylabel("Y", color="#8b98a5")
    ax.set_title(f"Track · {len(points)} pts", color="#e7e9ea", pad=12)
    ax.tick_params(colors="#8b98a5")
    for spine in ax.spines.values():
        spine.set_color("#38444d")
    ax.grid(True, color="#38444d", linestyle="--", linewidth=0.6, alpha=0.7)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def format_report(points: list[Point]) -> str:
    last = points[-1]
    lines = [
        f"<b>X</b> = <code>{last.x:.6g}</code>",
        f"<b>Y</b> = <code>{last.y:.6g}</code>",
        f"source: {last.source} · pts: {len(points)}",
    ]
    if len(points) >= 2:
        prev = points[-2]
        dx = last.x - prev.x
        dy = last.y - prev.y
        step = dist(prev, last)
        path = 0.0
        for a, b in zip(points, points[1:]):
            path += dist(a, b)
        from_start = dist(points[0], last)
        lines += [
            f"ΔX = <code>{dx:+.6g}</code> · ΔY = <code>{dy:+.6g}</code>",
            f"step = <code>{step:.6g}</code>",
            f"path = <code>{path:.6g}</code> · from start = <code>{from_start:.6g}</code>",
        ]
    return "\n".join(lines)


async def reply_with_plot(update: Update, points: list[Point]) -> None:
    message = update.effective_message
    if not message or not points:
        return
    png = render_plot(points)
    await message.reply_photo(
        photo=InputFile(io.BytesIO(png), filename="track.png"),
        caption=format_report(points),
        parse_mode=ParseMode.HTML,
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Xtg — live X/Y tracker.\n\n"
        "Send a point:\n"
        "• <code>10 20</code> or <code>10,20</code>\n"
        "• <code>x=10 y=20</code>\n"
        "• Telegram location (X=lon, Y=lat)\n"
        "• live location — graph updates on every ping\n\n"
        "/plot — current graph\n"
        "/last — last point\n"
        "/clear — reset track",
        parse_mode=ParseMode.HTML,
    )


async def cmd_plot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    points = store.get(update.effective_chat.id)
    if not points:
        await update.effective_message.reply_text("Track is empty. Send X Y first.")
        return
    await reply_with_plot(update, points)


async def cmd_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    points = store.get(update.effective_chat.id)
    if not points:
        await update.effective_message.reply_text("No points yet.")
        return
    await update.effective_message.reply_html(format_report(points))


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    n = store.clear(update.effective_chat.id)
    await update.effective_message.reply_text(f"Cleared {n} point(s).")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.effective_message.text or "").strip()
    parsed = parse_xy(text)
    if not parsed:
        await update.effective_message.reply_text(
            "Need two numbers: <code>12.5 -3</code> or share a location.",
            parse_mode=ParseMode.HTML,
        )
        return
    x, y = parsed
    points = store.add(update.effective_chat.id, Point(x=x, y=y, source="text"))
    await reply_with_plot(update, points)


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    loc = update.effective_message.location
    if not loc:
        return
    source = "live" if loc.live_period else "geo"
    point = Point(x=loc.longitude, y=loc.latitude, source=source)
    points = store.add(update.effective_chat.id, point)
    await reply_with_plot(update, points)


async def on_live_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.edited_message
    if not msg or not msg.location:
        return
    loc = msg.location
    point = Point(x=loc.longitude, y=loc.latitude, source="live")
    points = store.add(msg.chat_id, point)
    png = render_plot(points)
    await msg.reply_photo(
        photo=InputFile(io.BytesIO(png), filename="track.png"),
        caption=format_report(points),
        parse_mode=ParseMode.HTML,
    )


def main() -> None:
    if not TOKEN:
        raise SystemExit("Set BOT_TOKEN in .env or the environment.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("plot", cmd_plot))
    app.add_handler(CommandHandler("last", cmd_last))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.LOCATION, on_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & filters.LOCATION, on_live_edit))
    logger.info("Xtg is running")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
