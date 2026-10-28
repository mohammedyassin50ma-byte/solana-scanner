

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

st.set_page_config(
    page_title="Solana Scanner",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Solana Scanner")
st.caption("Live Solana token screening | Paper trading only")

MIN_LIQUIDITY = 20_000
MIN_VOLUME_24H = 10_000
MAX_AGE_HOURS = 168

@st.cache_data(ttl=60)
def scan_tokens():
    api = "https://api.dexscreener.com/token-profiles/latest/v1"
    response = requests.get(api, timeout=20)
    response.raise_for_status()

    profiles = response.json()
    tokens = [
        item for item in profiles
        if item.get("chainId") == "solana"
        and item.get("tokenAddress")
    ]

    rows = []
    for token in tokens:
        try:
            url = (
                "https://api.dexscreener.com/token-pairs/v1/solana/"
                + token["tokenAddress"]
            )
            r = requests.get(url, timeout=15)

            if r.status_code != 200:
                continue

            pairs = r.json()
            if not isinstance(pairs, list):
                continue

            pairs = [
                p for p in pairs
                if p.get("liquidity", {}).get("usd") is not None
            ]
            if not pairs:
                continue

            pair = max(
                pairs,
                key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0)
            )

            liquidity = float(pair.get("liquidity", {}).get("usd", 0) or 0)
            volume = float(pair.get("volume", {}).get("h24", 0) or 0)
            created = pair.get("pairCreatedAt")

            if not created:
                continue

            age = (
                datetime.now(timezone.utc).timestamp() - created / 1000
            ) / 3600

            if not (0 <= age <= MAX_AGE_HOURS):
                continue
            if liquidity < MIN_LIQUIDITY or volume < MIN_VOLUME_24H:
                continue

            txns = pair.get("txns", {}).get("m5", {})
            change = pair.get("priceChange", {}).get("m5")

            rows.append({
                "Token": pair.get("baseToken", {}).get("symbol", "?"),
                "Price ($)": float(pair["priceUsd"])
                    if pair.get("priceUsd") else None,
                "Market Cap ($)": pair.get("marketCap"),
                "Liquidity ($)": round(liquidity, 2),
                "Volume 24h ($)": round(volume, 2),
                "Change 5m (%)": change,
                "Buys 5m": txns.get("buys", 0),
                "Sells 5m": txns.get("sells", 0),
                "Age (hours)": round(age, 1),
                "Chart": pair.get("url", "")
            })

        except (requests.RequestException, ValueError, TypeError, KeyError):
            continue

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(
            "Volume 24h ($)", ascending=False
        ).reset_index(drop=True)
    return df

if st.button("🔄 Refresh scan"):
    st.cache_data.clear()

st.caption(
    "Filters: liquidity ≥ $20,000 | 24h volume ≥ $10,000 | pair age ≤ 7 days"
)

try:
    df = scan_tokens()

    a, b, c = st.columns(3)
    a.metric("Candidates", len(df))
    b.metric("Minimum liquidity", "$20,000")
    c.metric("Maximum pair age", "7 days")

    if df.empty:
        st.warning("No tokens passed the filters. Try again later.")
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Chart": st.column_config.LinkColumn("Open chart"),
                "Price ($)": st.column_config.NumberColumn(
                    format="$%.8f"
                ),
                "Market Cap ($)": st.column_config.NumberColumn(
                    format="$%,.0f"
                ),
                "Liquidity ($)": st.column_config.NumberColumn(
                    format="$%,.2f"
                ),
                "Volume 24h ($)": st.column_config.NumberColumn(
                    format="$%,.2f"
                ),
                "Change 5m (%)": st.column_config.NumberColumn(
                    format="%.2f%%"
                )
            }
        )

    st.caption(
        "Source: DexScreener. Screening results are not buy signals. "
        "Liquidity and volume do not guarantee token safety."
    )

except Exception as e:
    st.error(f"Could not load market data: {e}")
