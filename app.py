import streamlit as st
from coindcx_engine import CoinDCXEngine

st.set_page_config(page_title="CoinDCX Signal Exec", page_icon="⚡", layout="wide")

st.title("⚡ CoinDCX Hybrid Signal Executor")
st.caption("Spot & Futures Automated Entry & Risk Control System")

# Initialize Session State Variables
if "engine" not in st.session_state:
  st.session_state.engine = CoinDCXEngine()
if "daily_pnl" not in st.session_state:
  st.session_state.daily_pnl = 0.0
if "trade_history" not in st.session_state:
  st.session_state.trade_history = []

# Sidebar Controls
st.sidebar.header("⚙️ Bot Configuration")
trade_mode = st.sidebar.radio("Execution Mode", ["PAPER", "LIVE API"])
net_target_inr = st.sidebar.number_input(
    "Daily Net Target (₹)", value=1000, step=100
)
max_daily_loss = st.sidebar.number_input(
    "Daily Max Loss Circuit Breaker (₹)", value=1000, step=100
)

# API Keys (Only required for Live API mode)
api_key = ""
api_secret = ""
if trade_mode == "LIVE API":
  api_key = st.sidebar.text_input("CoinDCX API Key", type="password")
  api_secret = st.sidebar.text_input("CoinDCX API Secret", type="password")
  st.session_state.engine = CoinDCXEngine(
      api_key=api_key, api_secret=api_secret, paper_trading=False
  )

# Live Status Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Today's Net P&L", f"₹{st.session_state.daily_pnl:.2f}")
col2.metric("Target Goal", f"₹{net_target_inr}")
col3.metric(
    "Status",
    "🟢 ACTIVE"
    if st.session_state.daily_pnl < net_target_inr
    else "🛑 TARGET REACHED",
)

st.divider()

# Daily Target Guardrail Check
if st.session_state.daily_pnl >= net_target_inr:
  st.success("🎉 Daily profit target of ₹1,000 hit! Trading locked for today.")
elif st.session_state.daily_pnl <= -max_daily_loss:
  st.error("🛑 Daily drawdown circuit breaker triggered. Trading disabled.")
else:
  # Main Signal Input Form
  st.subheader("📥 Signal Entry (Expert Pick Input)")

  with st.form("signal_form"):
    c1, c2 = st.columns(2)
    with c1:
      market_type = st.selectbox(
          "Market Type", ["futures", "spot"], index=0
      ).lower()
      pair = st.text_input(
          "Coin Pair (e.g., B-BTC_USDT or I-BTC_INR)", value="B-BTC_USDT"
      )
      side = st.selectbox("Direction", ["BUY_LONG", "SELL_SHORT"]).split("_")[0]
    with c2:
      entry_price = st.number_input(
          "Entry Price (₹ or USDT)", value=0.0, format="%.4f"
      )
      target_price = st.number_input(
          "Target Price (TP)", value=0.0, format="%.4f"
      )
      stop_loss = st.number_input(
          "Stop Loss (SL)", value=0.0, format="%.4f"
      )

    leverage = 1
    if market_type == "futures":
      leverage = st.slider("Futures Leverage", min_value=1, max_value=10, value=3)

    risk_per_trade = st.number_input(
        "Max Loss Risk for this Trade (₹)", value=300
    )
    submit = st.form_submit_button("🔍 Validate & Execute Signal")

  if submit:
    if entry_price <= 0 or target_price <= 0 or stop_loss <= 0:
      st.error("Please enter valid prices for Entry, Target, and Stop Loss.")
    else:
      # Step 1: Validate Signal
      is_valid, msg = st.session_state.engine.validate_signal(
          pair=pair,
          entry_price=entry_price,
          stop_loss=stop_loss,
          target=target_price,
          market_type=market_type,
      )

      if not is_valid:
        st.error(f"❌ Signal Rejected: {msg}")
      else:
        st.success(f"✅ {msg}")

        # Step 2: Calculate Size
        calc_qty = st.session_state.engine.calculate_position_size(
            capital_inr=15000,
            entry_price=entry_price,
            stop_loss=stop_loss,
            leverage=leverage,
            risk_per_trade_inr=risk_per_trade,
        )

        st.info(
            f"Calculated Position Size: **{calc_qty} units** @ {leverage}x"
            " Leverage"
        )

        # Step 3: Execute Order
        trade_res = st.session_state.engine.execute_trade(
            pair=pair,
            side=side,
            quantity=calc_qty,
            price=entry_price,
            market_type=market_type,
            leverage=leverage,
            trade_mode=trade_mode,
        )

        st.json(trade_res)
        st.session_state.trade_history.append(trade_res)

# Render Recent Logs
if st.session_state.trade_history:
  st.subheader("📋 Session Trade Logs")
  st.dataframe(st.session_state.trade_history)