"""Past player boxscore summaries. No estimated stats when source is missing."""
from data_sources import BASE,get_json
from model import POSITION_VALUE

CATEGORIES={'passing':'QB','rushing':'RB','receiving':'WR','defensive':'DEF'}
def parse_num(x):
    try:return float(str(x).replace(',',''))
    except (ValueError,TypeError):return None

def extract_boxscore_players(data,team_id):
    out=[]
    for team in (data.get('boxscore') or {}).get('players',[]):
        team_meta=team.get('team') or {}
        if str(team_meta.get('id'))!=str(team_id):continue
        for cat in team.get('statistics',[]):
            cname=str(cat.get('name','')).lower();labels=[str(s).lower() for s in cat.get('labels',[])]
            for item in cat.get('athletes',[]):
                athlete=item.get('athlete') or {};name=athlete.get('displayName')
                if not name:continue
                position=(athlete.get('position') or {}).get('abbreviation','')
                stats=dict(zip(labels,item.get('stats',[])))
                out.append({'name':name,'position':position,'category':cname,'stats':stats})
    return out

def summarize_player_history(code,team_id,games,limit=5):
    player_games={};checked=0;failures=0
    for date,_,_,event_id in games[:limit]:
        if not event_id:continue
        try: data=get_json(f'{BASE}{code}/summary?event={event_id}')
        except Exception:failures+=1;continue
        checked+=1
        for row in extract_boxscore_players(data,team_id):
            key=(row['name'],row['category'])
            player_games.setdefault(key,[]).append((date,row))
    players=[]
    for (name,category),games_rows in player_games.items():
        labels={k for _,r in games_rows for k in r['stats']}
        relevant=('pass' in category or 'rush' in category or 'receiv' in category)
        if not relevant:continue
        def mean(keys):
            vals=[parse_num(r['stats'][k]) for _,r in games_rows for k in keys if k in r['stats']]
            vals=[x for x in vals if x is not None]
            return round(sum(vals)/len(vals),1) if vals else None
        yards=mean(('yds','yards'));td=mean(('td',));ints=mean(('int',)) if 'pass' in category else None
        if yards is None:continue
        position=games_rows[0][1]['position'] or ('QB' if 'pass' in category else 'RB' if 'rush' in category else 'WR')
        players.append({'name':name,'position':position,'category':category,'games':len(games_rows),'yards':yards,'td':td,'int':ints})
    return {'players':sorted(players,key=lambda p:(-p['games'],-p['yards'],p['name'])),'checked':checked,'failed':failures}

def historical_player_impact(history,starters,injuries):
    """Small capped additive signal, starter-only, conservative due to team form overlap."""
    names={n.casefold():pos for pos,n in starters.items()}
    injured={x['name'].casefold():x['status'].lower() for x in injuries}
    impact=0.;used=[]
    for p in history.get('players',[]):
        key=p['name'].casefold()
        if key not in names:continue
        pos=names[key];cat=p['category']
        if (pos=='QB' and 'pass' not in cat) or (pos=='RB' and 'rush' not in cat) or (pos in ('WR','TE') and 'receiv' not in cat):continue
        expected=220 if pos=='QB' else 65 if pos=='RB' else 55
        # Illustrative scaling, not empirically trained; shrink small samples.
        diff=max(-1,min(1,(p['yards']-expected)/(expected*.85)))
        raw=diff*POSITION_VALUE.get(pos,1)*.40*min(1,p['games']/5)
        if any(x in injured.get(key,'') for x in ('out','inactive','injured reserve','suspended')):raw=0
        impact+=raw;used.append((p,round(raw,2)))
    return max(-3,min(3,impact)),used
