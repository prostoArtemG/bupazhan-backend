from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import ccxt
from ta.trend import EMAIndicator
import pandas as pd
from telegram import Bot
import asyncio
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для теста
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOT_TOKEN = '8173670752:AAEcH32NP9DduazIIbKndey337HEwv_SKfI'
CHAT_ID = '500134490'
bot = Bot(token=BOT_TOKEN)

async def send_alert(text):
    await bot.send_message(chat_id=CHAT_ID, text=text)

def scan_fvg_ema(pair='BTC/USDT', tf='15m'):
    try:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(pair, tf, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['ema20'] = EMAIndicator(df['close'], window=20).ema_indicator()
        
        fvg_zones = []
        for i in range(2, len(df)):
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                fvg_zones.append((df['low'].iloc[i], df['high'].iloc[i-2]))
        
        current_price = df['close'].iloc[-1]
        ema = df['ema20'].iloc[-1]
        dist = abs(current_price - ema) / ema * 100
        
        if dist < 0.5 and fvg_zones:
            alert = f"🚨 {pair}: Цена {current_price:.4f} у EMA {ema:.4f} ({dist:.2f}%). FVG: {fvg_zones[-1]}"
            print(alert)
            asyncio.run(send_alert(alert))
        
        return {
            "ohlcv": ohlcv,
            "ema": ema,
            "current_price": current_price,
            "dist": dist,
            "fvg_zones": fvg_zones[-3:] if fvg_zones else []
        }
    except Exception as e:
        print(f"Ошибка scan для {pair}: {e}")
        return {
            "ohlcv": [],
            "ema": 0,
            "current_price": 0,
            "dist": 0,
            "fvg_zones": []
        }

def calculate_stats(pair, tf='15m', period='day'):
    try:
        exchange = ccxt.binance()
        days = 1 if period == 'day' else 7
        since = exchange.parse8601((datetime.now() - timedelta(days=days)).isoformat())
        ohlcv = exchange.fetch_ohlcv(pair, tf, since=since, limit=1000)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        fvg_zones = []
        for i in range(2, len(df)):
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                fvg_zones.append({'type': 'bullish', 'top': df['low'].iloc[i], 'bottom': df['high'].iloc[i-2], 'start_idx': i-2})
        
        closed_zones = 0
        for zone in fvg_zones:
            post_data = df.iloc[zone['start_idx']+3:]
            if any(post_data['low'] <= zone['bottom']):
                closed_zones += 1
        
        win_rate = (closed_zones / len(fvg_zones) * 100) if fvg_zones else 0
        return {"total": len(fvg_zones), "closed": closed_zones, "winRate": win_rate}
    except Exception as e:
        print(f"Ошибка stats для {pair}: {e}")
        return {"total": 0, "closed": 0, "winRate": 0}

@app.get("/scan")
def get_scan(pair: str, tf: str = '15m'):
    return scan_fvg_ema(pair, tf)

@app.get("/stats")
def get_stats(pair: str, period: str = 'day'):
    return calculate_stats(pair, period=period)

@app.get("/pairs")
def get_pairs():
    pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT', 'SNX/USDT']  # Только валидные
    results = {}
    for pair in pairs:
        try:
            stats = calculate_stats(pair, period='day')
            scan = scan_fvg_ema(pair)
            results[pair] = {
                "price": scan['current_price'],
                "dist_to_ema": scan['dist'],
                "fvg_count": len(scan['fvg_zones']),
                "win_rate": stats['winRate'],
            }
            print(f"Успех для {pair}: price {scan['current_price']}, win_rate {stats['winRate']}")
        except Exception as e:
            print(f"Ошибка для {pair}: {e} — пропускаем")
            continue
    print("Итоговый results:", results)
    return results or {"error": "Нет данных"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
