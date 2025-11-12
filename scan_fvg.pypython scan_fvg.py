import ccxt
from ta.trend import EMAIndicator
import pandas as pd
from telegram import Bot

BOT_TOKEN = '8173670752:AAEcH32NP9DduazIIbKndey337HEwv_SKfI'  # Твой токен от @BotFather
CHAT_ID = '500134490'  # Твой ID от @userinfobot
bot = Bot(token=BOT_TOKEN)

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
    
    if dist < 0.5 and fvg_zones:
        alert = f"🚨 {pair}: Цена {current_price:.4f} у EMA {ema:.4f} ({dist:.2f}%). FVG: {fvg_zones[-1]}"
        bot.send_message(chat_id=CHAT_ID, text=alert)
        print(alert)
    else:
        print("Нет сигнала — ждём...")

scan_fvg_ema()



