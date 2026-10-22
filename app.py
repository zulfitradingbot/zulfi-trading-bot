import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

st.set_page_config(page_title="Zulfi Trading Bot", page_icon="📈", layout="wide")

st.markdown("""<style>
.stApp, [data-testid="stAppViewContainer"] {background: #080c0b; color: #eaf7f0;}
[data-testid="stSidebar"] {background: #101a16; border-right: 1px solid #1c3b2d;}
[data-testid="stHeader"] {background: rgba(8,12,11,.95);}
h1,h2,h3 {color:#f1fff6 !important;}
h1 {letter-spacing: .06em; text-shadow: 0 0 22px rgba(0,210,115,.16);}
[data-testid="stMetric"] {background:#111c17; padding:16px; border:1px solid #214531; border-radius:12px;}
[data-testid="stMetricValue"] {color:#29e087 !important;}
[data-testid="stMetricLabel"] {color:#b6d2c0 !important;}
.stButton > button[kind="primary"], .stButton > button {background:#087c45; color:#fff; border:1px solid #16c774; border-radius:9px;}
.stButton > button:hover {background:#0b9d59; color:white; border-color:#32f29b;}
[data-baseweb="select"] > div, [data-baseweb="input"] > div {background:#16241d !important; border-color:#27543a !important; color:#f4fff7 !important;}
[data-testid="stAlert"] {border-radius:10px;}
[data-testid="stDataFrame"] {border:1px solid #254332; border-radius:10px;}
hr {border-color:#244734 !important;}
.zulfi-brand {border-left:5px solid #21d87c; background:linear-gradient(90deg,#122b1e,#141615); padding:14px 18px; border-radius:8px; margin-bottom:18px;}
.zulfi-green {color:#2ae486;font-weight:700;} .zulfi-red {color:#ff525c;font-weight:700;}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="zulfi-brand"><span class="zulfi-green">▲ UP</span> &nbsp; / &nbsp; <span class="zulfi-red">▼ DOWN</span> &nbsp; • &nbsp; Signal-only research dashboard</div>', unsafe_allow_html=True)

st.title("⚡ ZULFI TRADING BOT")
st.caption("Signals only • No automatic trade execution • Prototype")

st.warning(
    "This prototype does not log in to Quotex or receive live Quotex prices. "
    "Use it to configure pairs and timings and test signals with data you are authorized to use. "
    "OTC prices must match the actual Quotex OTC instrument; ordinary FX data is not a substitute."
)

# Starter catalogue: expandable/editable; not claimed to be a complete current Quotex list.
DEFAULT_PAIRS = [
    ("USD/PKR", "OTC"),
    ("EUR/USD", "Regular"),
    ("GBP/USD", "Regular"),
    ("USD/JPY", "Regular"),
    ("AUD/USD", "Regular"),
    ("EUR/JPY", "Regular"),
    ("AUD/JPY", "Regular"),
    ("USD/INR", "OTC"),
    ("USD/ZAR", "OTC"),
    ("USD/BRL", "OTC"),
    ("NZD/JPY", "OTC"),
    ("NZD/CAD", "OTC"),
    ("USD/MXN", "OTC"),
]
pairs_df = pd.DataFrame(DEFAULT_PAIRS, columns=["Pair", "Market type"])

with st.sidebar:
    st.header("Configuration")
    query = st.text_input("Search pairs", placeholder="e.g. USD/PKR")
    market_filter = st.selectbox("Market filter", ["All", "Regular", "OTC"])
    filtered = pairs_df.copy()
    if market_filter != "All":
        filtered = filtered[filtered["Market type"] == market_filter]
    if query.strip():
        filtered = filtered[filtered["Pair"].str.contains(query.strip(), case=False, regex=False)]
    if filtered.empty:
        st.info("No matching pair in starter list.")
        pair = st.selectbox("Pair", ["No pair found"], disabled=True)
    else:
        pair = st.selectbox("Select pair", filtered["Pair"].tolist(), index=0)

    check_interval = st.selectbox("Signal-check interval", ["5 seconds", "10 seconds", "15 seconds", "1 minute"])
    expiry = st.selectbox("Trade expiry", ["5 seconds", "10 seconds", "15 seconds", "1 minute"])
    st.markdown("---")
    st.subheader("Optional CSV candles")
    uploaded = st.file_uploader("Upload authorized OHLC CSV", type=["csv"])
    st.caption("Expected columns: timestamp, open, high, low, close. Use timestamps in chronological order.")

left, right = st.columns([1, 1])
with left:
    st.subheader("Selected setup")
    st.metric("Pair", pair)
    st.metric("Signal check", check_interval)
    st.metric("Trade expiry", expiry)
    st.metric("Mode", "Signals only")

with right:
    st.subheader("Payout")
    st.metric("Current payout", "Unavailable")
    st.caption("No verified permitted live payout source is connected. Do not use screenshot values as live data.")

def calculate_signal(df):
    required = {"open", "high", "low", "close"}
    if not required.issubset(set(df.columns)):
        return "NO TRADE", "CSV must include open, high, low, close columns."
    x = df.copy()
    for col in ["open", "high", "low", "close"]:
        x[col] = pd.to_numeric(x[col], errors="coerce")
    x = x.dropna(subset=["open", "high", "low", "close"])
    if len(x) < 30:
        return "NO TRADE", "At least 30 valid candles are required."
    close = x["close"]
    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean().replace(0, np.nan)
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    last = x.iloc[-1]
    # Conservative candle confirmation: use the latest fully closed candle supplied by the user.
    bullish = ema9.iloc[-1] > ema21.iloc[-1] and rsi.iloc[-1] > 50 and last["close"] > last["open"]
    bearish = ema9.iloc[-1] < ema21.iloc[-1] and rsi.iloc[-1] < 50 and last["close"] < last["open"]
    if bullish:
        return "SIGNAL 1 — UP", f"EMA9 > EMA21; RSI {rsi.iloc[-1]:.1f}; latest candle bullish."
    if bearish:
        return "SIGNAL 2 — DOWN", f"EMA9 < EMA21; RSI {rsi.iloc[-1]:.1f}; latest candle bearish."
    return "NO TRADE", f"Conditions not aligned. Latest RSI: {rsi.iloc[-1]:.1f}."

st.subheader("Signal engine (prototype)")
if uploaded is None:
    st.info("Upload a CSV of authorized, matching instrument candles to test the signal logic. No live signal is generated without verified data.")
else:
    try:
        candles = pd.read_csv(uploaded)
        signal, reason = calculate_signal(candles)
        st.write(f"**Instrument:** {pair}")
        st.write(f"**Timestamp:** {datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")
        st.write(f"**Check interval:** {check_interval} • **Expiry:** {expiry}")
        if signal == "SIGNAL 1 — UP":
            st.success(signal)
        elif signal == "SIGNAL 2 — DOWN":
            st.error(signal)
        else:
            st.warning(signal)
        st.caption(reason)
        st.caption("CSV output is only a prototype calculation, not a guarantee or a live Quotex prediction.")
        st.dataframe(candles.tail(10), use_container_width=True)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")

st.subheader("Historical signal evaluation")
st.caption("This is a simple historical test on uploaded, completed candles—not a live Quotex prediction. The next candle is used as a proxy for expiry only when your CSV candle duration matches the selected expiry.")
if uploaded is not None:
    try:
        test = candles.copy()
        test.columns = [str(c).lower().strip() for c in test.columns]
        required = {"open", "high", "low", "close"}
        if required.issubset(test.columns):
            for col in required:
                test[col] = pd.to_numeric(test[col], errors="coerce")
            test = test.dropna(subset=list(required)).reset_index(drop=True)
            if len(test) >= 32:
                if "timestamp" in test.columns:
                    times = pd.to_datetime(test["timestamp"], errors="coerce", utc=True)
                    durations = times.diff().dt.total_seconds().dropna()
                    typical_seconds = float(durations.median()) if not durations.empty else None
                else:
                    typical_seconds = None
                expiry_seconds = {"5 seconds": 5, "10 seconds": 10, "15 seconds": 15, "1 minute": 60}[expiry]
                st.write(f"**CSV candle interval:** {typical_seconds:g} seconds" if typical_seconds else "**CSV candle interval:** Unknown")
                if typical_seconds is None or abs(typical_seconds - expiry_seconds) > 0.01:
                    st.warning("Expiry does not match a verified CSV candle interval. Win-rate test disabled to avoid misleading results. Upload candles with timestamps and matching expiry interval.")
                else:
                    # Signal on candle i; compare the close of the next completed candle to entry at candle i close.
                    records = []
                    for i in range(29, len(test)-1):
                        sig, why = calculate_signal(test.iloc[:i+1])
                        if sig == "NO TRADE":
                            continue
                        entry = float(test.loc[i, "close"])
                        end = float(test.loc[i+1, "close"])
                        direction = "UP" if "UP" in sig else "DOWN"
                        outcome = "TIE" if end == entry else ("WIN" if (end > entry) == (direction == "UP") else "LOSS")
                        records.append({"Candle": i, "Signal": direction, "Entry close": entry, "Next close": end, "Outcome": outcome})
                    if records:
                        history = pd.DataFrame(records)
                        wins = int((history["Outcome"] == "WIN").sum())
                        losses = int((history["Outcome"] == "LOSS").sum())
                        evaluated = wins + losses
                        a,b,c = st.columns(3)
                        a.metric("Signals", len(history))
                        b.metric("Wins / Losses", f"{wins} / {losses}")
                        c.metric("Historical win rate", f"{100*wins/evaluated:.1f}%" if evaluated else "N/A")
                        st.dataframe(history.tail(100), use_container_width=True)
                        st.download_button("Download historical signal history", history.to_csv(index=False).encode(), file_name="signal_history.csv", mime="text/csv")
                        st.caption("Illustrative backtest only. It excludes spread, execution delays, payouts, fees, and live quote differences. Results are not predictive.")
                    else:
                        st.info("No UP or DOWN signals appeared in the supplied candle history.")
            else:
                st.info("Upload at least 32 valid candles to evaluate signal history.")
    except Exception as exc:
        st.error(f"Historical evaluation unavailable: {exc}")
else:
    st.info("Upload an OHLC CSV to generate historical signals and download their results.")

st.markdown("**Security:** No Quotex login, account access, automated trading, or verified live payout is implemented. Do not share passwords or OTPs. Test on demo data before risking money.")
