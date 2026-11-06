"""
Paper-trading bot for USDT/BTC on Binance testnet.
Educational only. No real money involved.
Features: RSI, SMA crossover, stop-loss, take-profit, recurring orders, position tracking.
"""

import time
import logging
import pandas as pd
from binance import Client

# Binance testnet URL
TESTNET_URL = "https://testnet.binance.vision"

# Paper testnet API keys
API_KEY="***"
API_SECRET="***"

# Trading parameters
SYMBOL = "BTCUSDT"
TIMEFRAME = "1m"
QUANTITY_USD = 100.0
RSI_PERIOD = 14
SMA_PERIOD = 20
SL_PCT = 0.005
TP_PCT = 0.01

# Position tracker
POSITION = {
    "in_position": False,
    "entry_price": 0,
    "sl_price": 0,
    "tp_price": 0,
    "qty": 0.001
}

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize client
client = Client(API_KEY, API_SECRET, testnet=True, base_url=TESTNET_URL)

def get_price(symbol):
    """Fetch current price."""
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker["price"])

def get_candles(symbol, interval, limit=50):
    """Fetch recent OHLCV candles."""
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "number_of_trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["close"] = pd.to_numeric(df["close"])
    return df

def calc_rsi(df, period=14):
    """Calculate RSI."""
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def calc_sma(df, period=20):
    """Calculate SMA."""
    return df["close"].rolling(window=period).mean().iloc[-1]

def place_order(action, symbol, quantity, price, stop_loss=None, take_profit=None):
    """Place a limit order on testnet."""
    try:
        order = client.order_limit_buy(
            symbol=symbol,
            quantity=quantity,
            price=price
        ) if action == "buy" else client.order_limit_sell(
            symbol=symbol,
            quantity=quantity,
            price=price
        )
        logger.info(f"{action.upper()} order placed: {order}")
        return order
    except Exception as e:
        logger.error(f"Order failed: {e}")
        return None

def check_risk_management(current_price, entry_price, sl_pct, tp_pct):
    """Check stop-loss and take-profit triggers."""
    sl_price = entry_price * (1 - sl_pct)
    tp_price = entry_price * (1 + tp_pct)
    status = []
    if current_price <= sl_price:
        status.append(f"STOP-LOSS triggered at ${current_price:.2f} (entry ${entry_price:.2f}, SL ${sl_price:.2f})")
    elif current_price >= tp_price:
        status.append(f"TAKE-PROFIT triggered at ${current_price:.2f} (entry ${entry_price:.2f}, TP ${tp_price:.2f})")
    return status

def analyze_signal(df):
    """Generate buy/sell signals based on RSI, SMA, and MACD."""
    rsi = calc_rsi(df, RSI_PERIOD)
    sma = calc_sma(df, SMA_PERIOD)
    current_close = df["close"].iloc[-1]

    if not POSITION["in_position"]:
        # Buy: RSI < 30 (oversold) + Price > SMA (uptrend)
        if rsi < 30 and current_close > sma:
            return "buy", f"RSI={rsi:.1f} (oversold), Price>SMA: {current_close > sma}"
    else:
        # Sell: RSI > 70 (overbought) + Price < SMA (downtrend)
        if rsi > 70 and current_close < sma:
            return "sell", f"RSI={rsi:.1f} (overbought), Price<SMA: {current_close < sma}"
    return None, None

def main():
    logger.info("Starting paper-trading bot for USDT/BTC (testnet)")
    logger.info(f"RSI: {RSI_PERIOD}, SMA: {SMA_PERIOD}")
    logger.info(f"Stop-loss: {SL_PCT*100:.2f}%, Take-profit: {TP_PCT*100:.2f}%")
    logger.info(f"Order size: ${QUANTITY_USD:.2f} USD per order")

    previous_price = get_price(SYMBOL)
    logger.info(f"Initial price: ${previous_price:.2f}")

    while True:
        try:
            df = get_candles(SYMBOL, TIMEFRAME, limit=50)
            rsi = calc_rsi(df, RSI_PERIOD)
            sma = calc_sma(df, SMA_PERIOD)
            current_close = df["close"].iloc[-1]

            signal, detail = analyze_signal(df)

            if not POSITION["in_position"] and signal == "buy":
                logger.info(f"BUY signal: {detail}")
                entry_price = current_close
                place_order("buy", SYMBOL, QUANTITY_USD, entry_price)
                POSITION["in_position"] = True
                POSITION["entry_price"] = entry_price
                POSITION["sl_price"] = entry_price * (1 - SL_PCT)
                POSITION["tp_price"] = entry_price * (1 + TP_PCT)
                logger.info(f"Position opened. SL: ${POSITION['sl_price']:.2f}, TP: ${POSITION['tp_price']:.2f}")

            elif POSITION["in_position"] and signal == "sell":
                logger.info(f"SELL signal: {detail}")
                place_order("sell", SYMBOL, QUANTITY_USD, current_close)
                POSITION["in_position"] = False
                logger.info("Position closed")

            # Risk management check
            if POSITION["in_position"]:
                risk_status = check_risk_management(
                    current_close,
                    POSITION["entry_price"],
                    SL_PCT,
                    TP_PCT
                )
                for status in risk_status:
                    logger.warning(f"Risk event: {status}")

            logger.info(f"Price: ${current_close:.2f} | RSI: {rsi:.1f} | SMA: ${sma:.2f}")

        except Exception as e:
            logger.error(f"Error: {e}")

        time.sleep(10)

if __name__ == "__main__":
    main()
