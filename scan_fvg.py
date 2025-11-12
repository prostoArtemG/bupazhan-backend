import ccxt
from ta.trend import EMAIndicator
import pandas as pd
from telegram import Bot
import asyncio
from datetime import datetime, timedelta

BOT_TOKEN = '8173670752:AAEcH32NP9DduazIIbKndey337HEwv_SKfI'  # Твой токен от @BotFather
CHAT_ID = '500134490'  # Твой ID от @userinfobot
bot = Bot(token=BOT_TOKEN)

async def send_alert(text):
    await bot.send_message(chat_id=CHAT_ID, text=text)

def scan_fvg_ema(pair='XPL/USDT', tf='15m'):
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv(pair, tf, limit=100)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['ema20'] = EMAIndicator(df['close'], window=20).ema_indicator()
    
    fvg_zones = []
    for i in range(2, len(df)):
        if df['low'].iloc[i] > df['high'].iloc[i-2]:  # Bullish FVG
            fvg_zones.append((df['low'].iloc[i], df['high'].iloc[i-2]))
    
    current_price = df['close'].iloc[-1]
    ema = df['ema20'].iloc[-1]
    dist = abs(current_price - ema) / ema * 100
    
    if dist < 0.5 and fvg_zones:  # Реальное условие (для теста смени на if True:)
        alert = f"🚨 {pair}: Цена {current_price:.4f} у EMA {ema:.4f} ({dist:.2f}%). FVG: {fvg_zones[-1]}"
        print(alert)
        asyncio.run(send_alert(alert))  # Отправка в TG
    else:
        print("Нет сигнала — ждём...")

def calculate_stats(pair, tf='15m', period='day'):
    exchange = ccxt.binance()
    days = 1 if period == 'day' else 7
    since = exchange.parse8601((datetime.now() - timedelta(days=days)).isoformat())
    ohlcv = exchange.fetch_ohlcv(pair, tf, since=since, limit=1000)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    fvg_zones = []
    for i in range(2, len(df)):
        if df['low'].iloc[i] > df['high'].iloc[i-2]:  # Bullish FVG
            fvg_zones.append({'type': 'bullish', 'top': df['low'].iloc[i], 'bottom': df['high'].iloc[i-2], 'start_idx': i-2})
    
    closed_zones = 0
    for zone in fvg_zones:
        post_data = df.iloc[zone['start_idx']+3:]
        if any(post_data['low'] <= zone['bottom']):
            closed_zones += 1
    
    win_rate = (closed_zones / len(fvg_zones) * 100) if fvg_zones else 0
    print(f"📊 Стата {pair} ({period}): {len(fvg_zones)} зон, {closed_zones} закрыто ({win_rate:.1f}%)")
    return win_rate

# Вызовы в конце
scan_fvg_ema()
calculate_stats('XPL/USDT', period='day')
