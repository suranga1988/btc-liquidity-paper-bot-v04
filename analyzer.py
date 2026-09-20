import sqlite3, statistics
from pathlib import Path
DB=Path('data/binance_market_data.db')


def setup(symbol='BTCUSDT', lookback=200):
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    rows=c.execute('SELECT * FROM snapshots WHERE symbol=? ORDER BY id DESC LIMIT ?', (symbol,lookback)).fetchall()
    c.close()
    if len(rows)<30: return {'status':'NOT_ENOUGH_DATA','symbol':symbol,'rows':len(rows)}
    rows=list(reversed(rows)); price=rows[-1]['mid']; prices=[r['mid'] for r in rows]; recent=prices[-30:]
    hi=max(recent); lo=min(recent); vol=statistics.pstdev(recent) if len(recent)>1 else price*.002
    r=rows[-1]; dom=r['dom_bid_pct']-r['dom_ask_pct']; flow=r['buy60']-r['sell60']
    entry=price
    if dom>=8 and flow>0:
        side='BUY'; sl=min(lo,price-1.5*vol); tp=price+2*(price-sl)
    elif dom<=-8 and flow<0:
        side='SELL'; sl=max(hi,price+1.5*vol); tp=price-2*(sl-price)
    else: side='WAIT'; sl=tp=None
    if side!='WAIT':
        risk=abs(entry-sl); rr=abs(tp-entry)/risk if risk else 0
        confidence=min(95,max(50,50+abs(dom)*1.5+min(20,abs(flow)/(max(1,r['buy60']+r['sell60']))*100)))
    else: rr=0; confidence=0
    return {'status':'OK','symbol':symbol,'price':price,'side':side,
      'entry_low':entry-vol*.25 if side in ('BUY','SELL') else None,'entry_high':entry+vol*.25 if side in ('BUY','SELL') else None,
      'take_profit':tp,'stop_loss':sl,'risk_reward':rr,'confidence':confidence,'liquidity_high':hi,'liquidity_low':lo,
      'dom_bid_pct':r['dom_bid_pct'],'dom_ask_pct':r['dom_ask_pct'],'aggressive_buy_60s':r['buy60'],'aggressive_sell_60s':r['sell60'], 'rows':len(rows)}
