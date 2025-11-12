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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BOT_TOKEN = '8173670752:AAEcH32NP9DduazIIbKndey337HEwv_SKfI'
CHAT_ID = '500134490'
bot = Bot(token=BOT_TOKEN)

async def send_alert(text):
    try:
        await asyncio.wait_for(bot.send_message(chat_id=CHAT_ID, text=text), timeout=10)
    except asyncio.TimeoutError:
        print("Таймаут для TG — пропускаем")
    except Exception as e:
        print(f"Ошибка алерта в TG: {e}")

async def scan_fvg_ema(pair='BTC/USDT', tf='15m'):
    try:
        exchange = ccxt.binance({
            'rateLimit': 1200,
            'timeout': 30000,
        })
        ohlcv = exchange.fetch_ohlcv(pair, tf, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['ema20'] = EMAIndicator(df['close'], window=20).ema_indicator()
        
        fvg_zones = []
        for i in range(2, len(df)):
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                fvg_zones.append({'type': 'bullish', 'top': df['low'].iloc[i], 'bottom': df['high'].iloc[i-2], 'timestamp': df['timestamp'].iloc[i-2]})
            elif df['high'].iloc[i] < df['low'].iloc[i-2]:
                fvg_zones.append({'type': 'bearish', 'top': df['low'].iloc[i-2], 'bottom': df['high'].iloc[i], 'timestamp': df['timestamp'].iloc[i-2]})
        
        current_price = df['close'].iloc[-1]
        ema = df['ema20'].iloc[-1]
        dist = abs(current_price - ema) / ema * 100
        
        print(f"Для {pair}: FVG {len(fvg_zones)}, цена {current_price}, EMA {ema}, dist {dist}%")
        
        if dist < 0.5 and fvg_zones:
            alert = f"🚨 {pair}: Цена {current_price:.4f} у EMA {ema:.4f} ({dist:.2f}%). FVG: {fvg_zones[-1]}"
            print(alert)
            asyncio.create_task(send_alert(alert))
        
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

async def calculate_last_imb(pair, tf='15m'):
    try:
        exchange = ccxt.binance({
            'rateLimit': 1200,
            'timeout': 30000,
        })
        ohlcv = exchange.fetch_ohlcv(pair, tf, limit=500)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        imb_zones = []
        for i in range(2, len(df)):
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                size_pct = (df['low'].iloc[i] - df['high'].iloc[i-2]) / df['high'].iloc[i-2] * 100
                imb_zones.append({
                    'type': 'bullish',
                    'top': df['low'].iloc[i],
                    'bottom': df['high'].iloc[i-2],
                    'size_pct': size_pct,
                    'timestamp': df['timestamp'].iloc[i-2],
                    'idx': i-2
                })
            elif df['high'].iloc[i] < df['low'].iloc[i-2]:
                size_pct = (df['low'].iloc[i-2] - df['high'].iloc[i]) / df['high'].iloc[i] * 100
                imb_zones.append({
                    'type': 'bearish',
                    'top': df['low'].iloc[i-2],
                    'bottom': df['high'].iloc[i],
                    'size_pct': size_pct,
                    'timestamp': df['timestamp'].iloc[i-2],
                    'idx': i-2
                })
        
        # Последняя незакрытая зона
        latest = None
        for zone in reversed(imb_zones):
            post_data = df.iloc[zone['idx']+3:]
            filled = False
            if zone['type'] == 'bullish':
                if any(post_data['low'] <= zone['bottom']):
                    filled = True
            else:
                if any(post_data['high'] >= zone['top']):
                    filled = True
            if not filled:
                latest = zone
                break
        
        if not latest:
            return {"type": None, "size_pct": 0, "time_since": "—", "status": "—"}
        
        time_since = datetime.now() - datetime.fromtimestamp(latest['timestamp'] / 1000)
        hours = int(time_since.total_seconds() // 3600)
        minutes = int((time_since.total_seconds() % 3600) // 60)
        time_str = f"{hours}ч {minutes}м" if hours else f"{minutes}м"
        
        return {
            "type": latest['type'],
            "size_pct": round(latest['size_pct'], 2),
            "time_since": time_str,
            "status": "Открыта"
        }
    except Exception as e:
        print(f"Ошибка last IMB для {pair} {tf}: {e}")
        return {"type": None, "size_pct": 0, "time_since": "—", "status": "—"}

@app.get("/scan")
async def get_scan(pair: str, tf: str = '15m'):
    return await scan_fvg_ema(pair, tf)

@app.get("/pairs")
async def get_pairs():
    pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'DOGE/USDT', 'SNX/USDT']
    results = {}
    tfs = ['5m', '15m', '1h', '4h']
    for pair in pairs:
        try:
            scan = await scan_fvg_ema(pair)
            imb_data = {}
            for tf in tfs:
                imb = await calculate_last_imb(pair, tf)
                imb_data[tf] = imb
            results[pair] = {
                "price": scan['current_price'],
                "dist_to_ema": scan['dist'],
                "fvg_count": len(scan['fvg_zones']),
                "imb_5m": imb_data['5m'],
                "imb_15m": imb_data['15m'],
                "imb_1h": imb_data['1h'],
                "imb_4h": imb_data['4h'],
            }
            print(f"Успех для {pair}: price {scan['current_price']}, IMB 5m {imb_data['5m']}")
        except Exception as e:
            print(f"Ошибка для {pair}: {e} — пропускаем")
            continue
    return results or {"error": "Нет данных"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
