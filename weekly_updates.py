"""On-demand ESPN scoreboard snapshot with bounded in-memory caching.

Free hosting sleeps; this refreshes when visited, not while the service sleeps.
"""
import datetime as dt
import threading
import time
from data_sources import BASE, LEAGUES, get_json

_CACHE = {}
_LOCK = threading.Lock()
_TTL = 60 * 60  # Refresh at most hourly while active.

def _number(value):
    if isinstance(value, dict):
        value = value.get('value', value.get('displayValue'))
    try: return int(float(value))
    except (ValueError, TypeError): return None

def _record(competitor):
    for rec in competitor.get('records', []):
        if rec.get('type') in ('total', 'overall') or rec.get('name') in ('overall', 'total'):
            return rec.get('summary')
    return None

def snapshot(league, force=False):
    if league not in LEAGUES: raise ValueError('Unknown league')
    now = time.monotonic()
    with _LOCK:
        cached = _CACHE.get(league)
        if cached and not force and now - cached[0] < _TTL:
            return dict(cached[1], cached=True)
    code = LEAGUES[league]
    # ESPN's current scoreboard determines the displayed week; no guessed week numbers.
    data = get_json(f'{BASE}{code}/scoreboard?limit=300')
    info = data.get('week', {})
    season = data.get('season', {})
    if not isinstance(info, dict): info = {}
    if not isinstance(season, dict): season = {}
    league_info = data.get('leagues', [])
    if not info and league_info and isinstance(league_info[0], dict):
        info = league_info[0].get('calendar', {}) if isinstance(league_info[0].get('calendar'),dict) else {}
    games=[]
    for event in data.get('events', []):
        comp = (event.get('competitions') or [{}])[0]
        teams = comp.get('competitors') or []
        if len(teams) != 2: continue
        home = next((x for x in teams if x.get('homeAway')=='home'), None)
        away = next((x for x in teams if x.get('homeAway')=='away'), None)
        if not home or not away: continue
        status = (comp.get('status') or event.get('status') or {}).get('type', {})
        finished = bool(status.get('completed'))
        games.append({'date':event.get('date'), 'home':home.get('team',{}).get('displayName','Home'),
            'away':away.get('team',{}).get('displayName','Away'),
            'home_score':_number(home.get('score')) if finished else None,
            'away_score':_number(away.get('score')) if finished else None,
            'home_record':_record(home), 'away_record':_record(away),
            'completed':finished})
    games.sort(key=lambda x:x.get('date') or '', reverse=True)
    result={'league':league,'season':season.get('year'), 'season_type':season.get('type'),
        'week':info.get('number'), 'week_label':info.get('text') or info.get('name'),
        'fetched_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'completed_games':[g for g in games if g['completed']][:15],
        'upcoming_games':[g for g in reversed(games) if not g['completed']][:15],
        'games_in_feed':len(games), 'cached':False,
        'notice':'Current ESPN scoreboard snapshot; records may be absent. Not a complete season database.'}
    with _LOCK: _CACHE[league]=(time.monotonic(),result)
    return result
