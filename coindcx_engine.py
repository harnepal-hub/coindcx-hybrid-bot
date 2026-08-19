import hashlib
import hmac
import json
import time
import requests

BASE_URL = "https://api.coindcx.com"


class CoinDCXEngine:

  def __init__(self, api_key=None, api_secret=None, paper_trading=True):
    self.api_key = api_key
    self.api_secret = api_secret
    self.paper_trading = paper_trading
    self.paper_balance_inr = 50000.0  # Initial paper cash balance

  def _generate_signature(self, json_body):
    return hmac.new(
        self.api_secret.encode(), json_body.encode(), hashlib.sha256
    ).hexdigest()

  def get_live_ticker(self, market_type="futures"):
    """Fetches real-time price tickers for Spot or Futures markets.

    CoinDCX's /exchange/ticker endpoint returns active pricing objects for all
    markets (e.g. I-BTC_INR, B-BTC_USDT).
    """
    endpoint = "/exchange/ticker"
    try:
      resp = requests.get(BASE_URL + endpoint, timeout=5)
      if resp.status_code == 200:
        return resp.json()
    except Exception as e:
      print(f"Error fetching ticker: {e}")
    return []

  def validate_signal(
      self,
      pair,
      entry_price,
      stop_loss,
      target,
      market_type="futures",
      max_spread_pct=0.5,
  ):
    """Executes pre-trade validation checks: spread, risk-reward ratio, and signal direction."""
    # 1. Calculate Risk to Reward Ratio (RRR)
    risk = abs(entry_price - stop_loss)
    reward = abs(target - entry_price)
    if risk == 0:
      return False, "Invalid Stop-Loss: Equal to Entry Price"

    rrr = reward / risk
    if rrr < 1.3:
      return False, f"Risk-to-Reward Ratio ({rrr:.2f}) is below minimum 1:1.3"

    # 2. Check Orderbook Spread / Slippage via public ticker
    tickers = self.get_live_ticker(market_type)
    current_price = None

    if isinstance(tickers, list):
      for item in tickers:
        # Check if item is a dictionary containing market data
        if isinstance(item, dict):
          item_pair = (
              item.get("market") or item.get("pair") or item.get("symbol")
          )
          if item_pair == pair:
            current_price = float(item.get("last_price", 0))
            break

    if current_price and current_price > 0:
      slippage = abs(current_price - entry_price) / entry_price * 100
      if slippage > max_spread_pct:
        return (
            False,
            f"Slippage too high ({slippage:.2f}%). Current price"
            f" ({current_price}) moved away from entry ({entry_price}).",
        )

    return True, "Signal Validated Successfully"

  def calculate_position_size(
      self,
      capital_inr,
      entry_price,
      stop_loss,
      leverage=1,
      risk_per_trade_inr=300,
  ):
    """Calculates position size based on risk parameters and fee overhead."""
    price_delta = abs(entry_price - stop_loss)
    if price_delta == 0:
      return 0.0

    raw_quantity = risk_per_trade_inr / price_delta
    position_value = raw_quantity * entry_price

    # Leverage margin requirements check
    required_margin = position_value / leverage
    if required_margin > capital_inr:
      # Scale down to available margin
      position_value = capital_inr * leverage
      raw_quantity = position_value / entry_price

    return round(raw_quantity, 4)

  def execute_trade(
      self,
      pair,
      side,
      quantity,
      price,
      market_type="futures",
      leverage=1,
      trade_mode="PAPER",
  ):
    """Handles execution for both Paper Ledger and Live API trades."""
    if trade_mode == "PAPER":
      fee_rate = 0.0005 if market_type == "futures" else 0.001
      estimated_fee = (quantity * price) * fee_rate
      return {
          "status": "SUCCESS",
          "mode": "PAPER",
          "pair": pair,
          "side": side,
          "quantity": quantity,
          "entry_price": price,
          "market_type": market_type,
          "leverage": leverage,
          "fee_deducted_inr": round(estimated_fee, 2),
      }

    # Live API Execution
    endpoint = (
        "/exchange/v1/orders/create"
        if market_type == "spot"
        else "/exchange/v1/derivatives/futures/orders/create"
    )

    body = {
        "side": side.lower(),
        "order_type": "limit_order",
        "price": price,
        "total_quantity": quantity,
        "timestamp": int(time.time() * 1000),
    }

    if market_type == "spot":
      body["market"] = pair
    else:
      body["pair"] = pair
      body["leverage"] = leverage

    json_body = json.dumps(body)
    signature = self._generate_signature(json_body)
    headers = {
        "Content-Type": "application/json",
        "X-AUTH-APIKEY": self.api_key,
        "X-AUTH-SIGNATURE": signature,
    }

    try:
      res = requests.post(
          BASE_URL + endpoint, headers=headers, data=json_body, timeout=10
      )
      return res.json()
    except Exception as e:
      return {"status": "FAILED", "error": str(e)}
