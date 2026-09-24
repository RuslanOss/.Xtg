# .Xtg

Telegram-bot that tracks **X / Y** in real time and replies with a plot.

## What it does

- Accepts points as text: `10 20`, `10,20`, `x=10 y=20`
- Accepts Telegram location: **X = longitude**, **Y = latitude**
- Live location: every ping appends a point and sends an updated graph
- Each reply: current X/Y, ΔX/ΔY, step, path length, PNG track

## Commands

| Command | Action |
| --- | --- |
| `/start` | help |
| `/plot` | current graph |
| `/last` | last point without a new image |
| `/clear` | reset the track |

Tracks are stored in memory per chat (up to `MAX_POINTS`, default 500).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # put the token from @BotFather
python bot.py
```

Get a token from [@BotFather](https://t.me/BotFather), paste it into `.env` as `BOT_TOKEN`.

## Stack

- Python 3.10+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 21
- matplotlib (Agg) for PNG plots
