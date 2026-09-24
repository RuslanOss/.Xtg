# .Xtg

Telegram-bot: **X / Y calculations** and **square root**. Text replies only, no graphs.

## What it does

- Point as text: `10 20`, `10,20`, `x=10 y=20`
- Telegram location: **X = longitude**, **Y = latitude**
- Live location: recalculates on every ping
- Single number: square root only (`81` → √81 = 9)

Each point reply:

- X, Y, |r|
- √X, √Y, √(X²+Y²)
- ΔX / ΔY, step, √step, path, distance from start

Negative values: real square root is reported as undefined.

## Commands

| Command | Action |
| --- | --- |
| `/start` | help |
| `/last` | last point |
| `/clear` | reset the track |

Tracks are stored in memory per chat (up to `MAX_POINTS`, default 500).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # token from @BotFather
python bot.py
```

## Stack

- Python 3.10+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 21
