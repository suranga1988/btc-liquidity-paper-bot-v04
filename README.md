# BTC Liquidity Paper Bot v0.4 Cloud

This version is designed to run on an always-on Linux VPS/cloud server, so the data collector keeps running even when the user's Windows PC is off.

## What it does
- Collects public Binance USD-M Futures market data 24/7.
- Collects BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT and XRPUSDT.
- Saves depth events, aggregate trades and 1-second snapshots into SQLite.
- Provides a small web dashboard on port 8080.
- Produces PAPER BUY/SELL/WAIT analysis only.
- Does not use API keys and does not place orders.

## Docker (recommended)
On an Ubuntu VPS with Docker installed:

    cd /opt/btc_liquidity_paper_bot_v0_4_cloud
    docker compose up -d --build
    docker compose ps

Dashboard:

    http://SERVER_IP:8080

## systemd (alternative)
Copy this folder to /opt/btc_liquidity_paper_bot_v0_4_cloud, install requirements, then:

    sudo cp systemd/*.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now binance-paper-collector
    sudo systemctl enable --now binance-paper-dashboard

Logs:

    journalctl -u binance-paper-collector -f

## Important
The cloud server must have internet access. The Windows PC can be completely off; the server continues collecting. SQLite data is kept in the mounted `data/` directory.

The analysis is experimental/paper only and is not a trading recommendation.
