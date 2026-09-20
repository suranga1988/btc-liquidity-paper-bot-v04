import asyncio, json, sqlite3, time
from collections import deque
from datetime import datetime
from pathlib import Path
import aiohttp, websockets

DATA_DIR = Path('data')
DB_PATH = DATA_DIR / 'binance_market_data.db'
SYMBOLS = ['BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT']
REST = 'https://fapi.binance.com/fapi/v1/depth'


def db():
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('''CREATE TABLE IF NOT EXISTS depth_events(
      id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, ts REAL, event_time INTEGER,
      first_update_id INTEGER, final_update_id INTEGER, bids TEXT, asks TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS agg_trades(
      id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, ts REAL, event_time INTEGER,
      trade_id INTEGER, price REAL, qty REAL, buyer_is_maker INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS snapshots(
      id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, ts REAL, event_time INTEGER,
      last_update_id INTEGER, best_bid REAL, best_ask REAL, mid REAL,
      bid_qty REAL, ask_qty REAL, dom_bid_pct REAL, dom_ask_pct REAL,
      buy60 REAL, sell60 REAL)''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_snap_symbol_id ON snapshots(symbol,id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_trade_symbol_ts ON agg_trades(symbol,ts)')
    c.commit(); return c


async def get_snapshot(session, symbol):
    async with session.get(REST, params={'symbol': symbol, 'limit': 1000}) as r:
        r.raise_for_status(); return await r.json()


class Book:
    def __init__(self): self.bids={}; self.asks={}; self.last=None; self.ready=False
    def load(self, x):
        self.bids={float(p):float(q) for p,q in x['bids'] if float(q)>0}
        self.asks={float(p):float(q) for p,q in x['asks'] if float(q)>0}
        self.last=int(x['lastUpdateId']); self.ready=True
    def apply(self,e):
        U,u=int(e['U']),int(e['u'])
        if u <= self.last: return True
        if U > self.last + 1: self.ready=False; return False
        for p,q in e.get('b',[]):
            p,q=float(p),float(q)
            if q == 0: self.bids.pop(p,None)
            else: self.bids[p]=q
        for p,q in e.get('a',[]):
            p,q=float(p),float(q)
            if q == 0: self.asks.pop(p,None)
            else: self.asks[p]=q
        self.last=u; return True
    def top(self):
        if not self.bids or not self.asks: return None
        return max(self.bids), min(self.asks)
    def qty(self,pct=.005):
        t=self.top()
        if not t: return 0,0
        b,a=t; m=(b+a)/2; lo=m*(1-pct); hi=m*(1+pct)
        return (sum(q for p,q in self.bids.items() if lo<=p<=m),
                sum(q for p,q in self.asks.items() if m<=p<=hi))


class Flow:
    def __init__(self): self.q=deque()
    def add(self,ts,p,q,m):
        self.q.append((ts,p*q,'sell' if m else 'buy')); self.trim(ts)
    def trim(self,n):
        cut=n-60
        while self.q and self.q[0][0] < cut: self.q.popleft()
    def totals(self,n):
        self.trim(n)
        return (sum(v for _,v,s in self.q if s=='buy'), sum(v for _,v,s in self.q if s=='sell'))


async def run_symbol(symbol):
    stream = symbol.lower()
    ws_url = f'wss://fstream.binance.com/stream?streams={stream}@depth@100ms/{stream}@aggTrade'
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        while True:
            c = db(); book=Book(); flow=Flow(); pending=[]
            try:
                # Connect first so no depth events are missed while the REST snapshot is fetched.
                async with websockets.connect(ws_url,ping_interval=20,ping_timeout=20,max_size=None) as ws:
                    print(f'[{symbol}] connected')
                    snap_task=asyncio.create_task(get_snapshot(session,symbol))
                    lastsave=0
                    while True:
                        if not snap_task.done():
                            try:
                                msg=json.loads(await asyncio.wait_for(ws.recv(),0.5))
                            except asyncio.TimeoutError:
                                continue
                        else:
                            msg=json.loads(await asyncio.wait_for(ws.recv(),30))
                        d=msg.get('data',{}); st=msg.get('stream',''); now=time.time()
                        if '@depth' in st:
                            c.execute('INSERT INTO depth_events(symbol,ts,event_time,first_update_id,final_update_id,bids,asks) VALUES(?,?,?,?,?,?,?)',
                                      (symbol,now,d.get('E'),d.get('U'),d.get('u'),json.dumps(d.get('b',[])),json.dumps(d.get('a',[]))))
                            c.commit()
                            if book.ready:
                                if not book.apply(d): break
                            else: pending.append(d)
                        elif '@aggTrade' in st:
                            p=float(d['p']); q=float(d['q']); m=bool(d['m'])
                            c.execute('INSERT INTO agg_trades(symbol,ts,event_time,trade_id,price,qty,buyer_is_maker) VALUES(?,?,?,?,?,?,?)',
                                      (symbol,now,d.get('T'),d.get('a'),p,q,int(m)))
                            c.commit(); flow.add(now,p,q,m)
                        if snap_task.done() and not book.ready:
                            book.load(snap_task.result())
                            pending.sort(key=lambda x:int(x['U']))
                            for e in pending:
                                if int(e['u']) <= book.last: continue
                                if int(e['U']) <= book.last+1 <= int(e['u']):
                                    if not book.apply(e): break
                            pending=[]
                        if book.ready and now-lastsave>=1:
                            t=book.top()
                            if t:
                                b,a=t; mid=(b+a)/2; qb,qa=book.qty(); total=qb+qa
                                pb=100*qb/total if total else 50; pa=100-pb
                                buy,sell=flow.totals(now)
                                c.execute('''INSERT INTO snapshots(symbol,ts,event_time,last_update_id,best_bid,best_ask,mid,bid_qty,ask_qty,dom_bid_pct,dom_ask_pct,buy60,sell60)
                                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                                  (symbol,now,int(now*1000),book.last,b,a,mid,qb,qa,pb,pa,buy,sell))
                                c.commit(); lastsave=now
                                print(f"\r[{symbol}] {datetime.now().strftime('%H:%M:%S')} {mid:,.4f} DOM {pb:.1f}/{pa:.1f} FLOW ${buy:,.0f}/${sell:,.0f}",end='',flush=True)
            except Exception as e:
                print(f'\n[{symbol}] reconnect: {e}')
                await asyncio.sleep(3)
            finally:
                c.close()


async def main():
    db().close()
    await asyncio.gather(*(run_symbol(s) for s in SYMBOLS))

if __name__=='__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: print('\nStopped.')
