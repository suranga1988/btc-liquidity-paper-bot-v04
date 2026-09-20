from flask import Flask, request, render_template_string
from analyzer import setup
import sqlite3
from pathlib import Path
app=Flask(__name__); DB=Path('data/binance_market_data.db')
COINS=['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT']
HTML='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Liquidity Paper Analyzer v0.4</title><style>body{font-family:Arial,sans-serif;max-width:850px;margin:30px auto;padding:0 16px}select,button{padding:10px;font-size:16px}.card{border:1px solid #ccc;border-radius:12px;padding:18px;margin-top:18px}table{border-collapse:collapse;width:100%}td{padding:8px;border-bottom:1px solid #eee}.note{font-size:13px;color:#666}</style></head><body><h2>Liquidity Paper Analyzer v0.4</h2><form><select name="symbol">{% for c in coins %}<option {% if c==symbol %}selected{% endif %}>{{c}}</option>{% endfor %}</select> <button>ANALYZE</button></form>{% if s %}<div class="card"><h3>{{s.symbol}} — {{s.side}}</h3>{% if s.status=='OK' %}<table><tr><td>Current price</td><td>{{'%.4f'|format(s.price)}}</td></tr><tr><td>Entry zone</td><td>{{'%.4f'|format(s.entry_low) if s.entry_low else '-'}} → {{'%.4f'|format(s.entry_high) if s.entry_high else '-'}}</td></tr><tr><td>TP</td><td>{{'%.4f'|format(s.take_profit) if s.take_profit else '-'}}</td></tr><tr><td>SL</td><td>{{'%.4f'|format(s.stop_loss) if s.stop_loss else '-'}}</td></tr><tr><td>R/R</td><td>1 : {{'%.2f'|format(s.risk_reward)}}</td></tr><tr><td>Experimental confidence</td><td>{{'%.0f'|format(s.confidence)}}/100</td></tr><tr><td>DOM bid / ask</td><td>{{'%.2f'|format(s.dom_bid_pct)}}% / {{'%.2f'|format(s.dom_ask_pct)}}%</td></tr><tr><td>Aggressive buy / sell 60s</td><td>${{'%.0f'|format(s.aggressive_buy_60s)}} / ${{'%.0f'|format(s.aggressive_sell_60s)}}</td></tr><tr><td>Saved snapshots used</td><td>{{s.rows}}</td></tr></table>{% else %}<p>Not enough saved data yet. Keep the cloud collector running.</p>{% endif %}</div>{% endif %}<p class="note">Paper/experimental analysis only. No orders or account keys are used.</p></body></html>'''
@app.route('/')
def index():
    symbol=request.args.get('symbol','BTCUSDT').upper(); symbol=symbol if symbol in COINS else 'BTCUSDT'; s=setup(symbol); return render_template_string(HTML,coins=COINS,symbol=symbol,s=s)
@app.route('/health')
def health(): return 'OK',200
if __name__=='__main__': app.run(host='0.0.0.0',port=8080)
