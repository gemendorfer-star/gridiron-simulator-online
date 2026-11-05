"""Hosted Gridiron Simulator companion; public access with basic resource limits."""
import json, socket, threading, urllib.parse, os, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from data_sources import BASE,LEAGUES,get_json,extract_teams,fetch_team
from season_player_db import season_player_summary,season_starter_impact
from model import strength,monte_carlo
from simulated_player_stats import project_box_score
from matchup_engine import defensive_impact,matchup_adjustment
from accuracy_tracker import evaluate
from weekly_updates import snapshot
from team_quality import assess
from elo_live import load_pair

PAGE=Path(__file__).with_name('index.html').read_bytes()
TEAM_CACHE={}
LOCK=threading.Lock()
SIM_SLOTS=threading.BoundedSemaphore(2)
REQUEST_TIMES={}
RATE_LOCK=threading.Lock()
BACKTEST_CACHE={}
BACKTEST_LOCK=threading.Lock()

def teams(league):
    if league not in LEAGUES: raise ValueError('Unknown league')
    with LOCK:
        if league in TEAM_CACHE:return TEAM_CACHE[league]
    # College football is split across ESPN group listings. Merge the default,
    # FBS (80), and FCS (81) feeds instead of relying on the default list alone.
    code = LEAGUES[league]
    groups = (None, '80', '81') if league == 'College Football' else (None,)
    data = {}
    errors = []
    for group in groups:
        url = f'{BASE}{code}/teams?limit=1000'
        if group is not None:
            url += f'&groups={group}'
        try:
            data.update(extract_teams(get_json(url)))
        except Exception as exc:
            errors.append(str(exc))
    if not data:
        raise RuntimeError('Could not load team listings: ' + '; '.join(errors)[:180])
    with LOCK:
        TEAM_CACHE[league] = data
    return data

def simulate(q):
    league=q.get('league',['NFL'])[0]; away=q.get('away',[''])[0];home=q.get('home',[''])[0]
    season=int(q.get('season',['2026'])[0]);n=int(q.get('runs',['1000'])[0]); refresh=q.get('refresh',['1'])[0]=='1'
    if season<2020 or season>2030 or n not in (10,25,50,100,250,500,1000,2000,5000):raise ValueError('Invalid season or simulations')
    t=teams(league)
    if away not in t or home not in t or away==home:raise ValueError('Choose two different teams')
    td={};hist={};quality={};warnings=[]
    for name in (away,home):
        if refresh:
            try:td[name]=fetch_team(league,t[name])
            except Exception as e:td[name]={};warnings.append(f'{name}: injury and starter data unavailable ({str(e)[:90]})')
            try:hist[name]=season_player_summary(LEAGUES[league],t[name]['id'],season)
            except Exception as e:hist[name]={};warnings.append(f'{name}: player history unavailable ({str(e)[:90]})')
        else:td[name]={};hist[name]={}
        try:
            quality[name]=assess(league,t[name]['id'],season)
            if not quality[name].get('available'):warnings.append(f'{name}: no completed season games available for team-strength rating')
        except Exception as e:
            quality[name]={'available':False,'games':0,'adjustment':0,'notice':'Team record unavailable'}
            warnings.append(f'{name}: team strength data unavailable ({str(e)[:90]})')
    values={};detail={}
    if not all(quality[name].get('available') and quality[name].get('games',0)>=3 for name in (away,home)):
        warnings.append('LOW CONFIDENCE: one or both teams have fewer than 3 verified completed games. Do not rely on the predicted winner or score.')
    if not refresh:
        warnings.append('Player and injury refresh is OFF; current roster data is not used.')
    for name in (away,home):
        if refresh and (td[name].get('starter') in (None,'Unknown') or td[name].get('injury_state')=='Unknown'):
            warnings.append(f'{name}: starting quarterback or injury availability is unverified; do not treat player projections as current.')
    for name in (away,home):
        s,parts=strength(td[name],league)
        if refresh and hist[name].get('players'):
            imp,used=season_starter_impact(hist[name],td[name].get('starters',{}),td[name].get('injuries',[]))
            defense=defensive_impact(hist[name],td[name].get('starters',{}),td[name].get('injuries',[]))
            # These are heuristic, overlapping measures of the same season performance.
            # Shrink their combined influence to reduce double counting.
            s+=max(-3.0,min(3.0,0.25*(imp+defense['points'])))
            other=home if name==away else away
            if hist[other].get('players'):
                s+=max(-1.5,min(1.5,0.25*matchup_adjustment(hist[name],td[name].get('starters',{}),hist[other],td[other].get('starters',{}),td[name].get('injuries',[]),td[other].get('injuries',[]))['points']))
        s+=quality[name].get('adjustment',0)
        values[name]=s
        detail[name]={'starter':td[name].get('starter','Unknown'), 'injuries':td[name].get('injuries',[])[:20], 'player_count':len(hist[name].get('players',[])), 'strength':round(s,2),'components':parts,'team_quality':quality[name],'starters':td[name].get('starters',{})}
    # Prefer a recent, date-stamped Elo rating when a trained historical snapshot
    # has been explicitly installed. Do not add it to the old strength rating:
    # doing so would double-count team form and record.
    elo,elo_warning=load_pair(league,t[away]['id'],t[home]['id'],season)
    if elo:
        # Elo difference is converted to a conservative expected-point margin.
        # Retain a small injury adjustment; no claim of calibrated score accuracy.
        margin=max(-21,min(21,(elo['home']-elo['away'])/28.0))
        values[away]=-margin/2 - min(3,detail[away]['components']['injury_penalty']*.25)
        values[home]=margin/2 - min(3,detail[home]['components']['injury_penalty']*.25)
        warnings.append('Elo baseline used (snapshot '+elo['as_of']+'). Win probabilities and scores are still unvalidated for this simulator.')
    elif elo_warning:
        warnings.append(elo_warning)
    result=monte_carlo(values[away],values[home],league,n)
    player={}
    for idx,name in enumerate((away,home)):
        side='Away' if idx==0 else 'Home'
        drives=[d for d in result['sample_drives'] if d[1]==side]
        player[name]=project_box_score(hist[name],td[name],sum(d[5] for d in drives),drives,seed=41+idx)
    warnings.append('Player box scores describe ONE illustrative sampled game, not the average predicted score. They are not verified individual player forecasts.')
    return {'away':away,'home':home,'result':result,'details':detail,'players':player,'warnings':warnings,'refresh':refresh}

class Handler(BaseHTTPRequestHandler):
    def send(self,status,data,ctype):
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
    def do_GET(self):
        path=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(path.query)
        if path.path=='/health':return self.json(200,{'status':'ok'})
        if path.path=='/':return self.send(200,PAGE,'text/html; charset=utf-8')
        if path.path=='/api/weekly':
            try:
                league=q.get('league',['NFL'])[0]
                return self.json(200,snapshot(league))
            except ValueError as e:return self.json(400,{'error':str(e)})
            except Exception as e:return self.json(502,{'error':'Weekly data unavailable: '+str(e)[:140]})
        if path.path=='/api/teams':
            try:
                league=q.get('league',['NFL'])[0];return self.json(200,{'teams':sorted(teams(league))})
            except Exception as e:return self.json(502,{'error':str(e)[:180]})
        if path.path=='/api/accuracy':
            try:
                league=q.get('league',['NFL'])[0]
                season=int(q.get('season',['2024'])[0])
                weeks=int(q.get('weeks',['10'])[0])
                key=(league,season,weeks)
                with BACKTEST_LOCK: cached=BACKTEST_CACHE.get(key)
                if cached is None:
                    if not SIM_SLOTS.acquire(blocking=False):return self.json(503,{'error':'Server busy; try again shortly.'})
                    try: cached=evaluate(league,season,weeks)
                    finally: SIM_SLOTS.release()
                    with BACKTEST_LOCK:BACKTEST_CACHE[key]=cached
                cached=dict(cached)
                cached['evaluation_scope']='Simple historical baseline only; NOT the live matchup simulator, player forecasts, or Elo held-out test.'
                return self.json(200,cached)
            except ValueError as e:return self.json(400,{'error':str(e)})
            except Exception as e:return self.json(502,{'error':'Accuracy test unavailable: '+str(e)[:150]})
        if path.path=='/api/simulate':
            client=self.client_address[0]
            now=time.monotonic()
            with RATE_LOCK:
                recent=[t for t in REQUEST_TIMES.get(client,[]) if now-t<60]
                if len(recent)>=3:return self.json(429,{'error':'Please wait one minute before running more simulations.'})
                recent.append(now);REQUEST_TIMES[client]=recent
                if len(REQUEST_TIMES)>500:REQUEST_TIMES.clear()
            if not SIM_SLOTS.acquire(blocking=False):return self.json(503,{'error':'Server busy; try again shortly.'})
            try:return self.json(200,simulate(q))
            except ValueError as e:return self.json(400,{'error':str(e)})
            except Exception as e:return self.json(502,{'error':'Data or simulation error: '+str(e)[:150]})
            finally:SIM_SLOTS.release()
        self.send(404,b'Not found','text/plain')
    def json(self,status,obj):self.send(status,json.dumps(obj,default=str).encode(),'application/json; charset=utf-8')
    def log_message(self,*args):pass

def local_ip():
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('192.0.2.1',1));ip=s.getsockname()[0];s.close();return ip
    except Exception:return 'YOUR-PC-IP'

if __name__=='__main__':
    print('\nGRIDIRON SIMULATOR — IPHONE COMPANION\n')
    port=int(os.environ.get('PORT','8765'))
    print(f'Starting hosted app on port {port}')
    try:ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
    except KeyboardInterrupt:print('Stopped.')
