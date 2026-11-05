"""Heuristic team-quality summary from completed ESPN schedule games.
Not a calibrated rating; never substitute missing stats with invented records.
"""
from data_sources import BASE, LEAGUES, get_json

def _score(entry):
    v=entry.get('score')
    if isinstance(v,dict): v=v.get('value',v.get('displayValue'))
    try: return float(v)
    except (ValueError,TypeError): return None

def _opponent_win_rate(entry):
    for rec in entry.get('records',[]):
        if rec.get('type') in ('total','overall') or rec.get('name') in ('total','overall'):
            summary=rec.get('summary','')
            try:
                parts=summary.split('-'); wins=float(parts[0]); losses=float(parts[1]); ties=float(parts[2]) if len(parts)>2 else 0
                if wins+losses+ties: return (wins+ties/2)/(wins+losses+ties)
            except (ValueError,IndexError,AttributeError): pass
    return None

def assess(league,team_id,season):
    if league not in LEAGUES: raise ValueError('Unknown league')
    url=f'{BASE}{LEAGUES[league]}/teams/{team_id}/schedule?season={season}'
    events=get_json(url).get('events',[])
    games=[]
    for event in events:
        competition=(event.get('competitions') or [{}])[0]
        status=(competition.get('status') or event.get('status') or {}).get('type') or {}
        if not status.get('completed'):continue
        competitors=competition.get('competitors') or []
        mine=next((x for x in competitors if str(x.get('team',{}).get('id'))==str(team_id)),None)
        other=next((x for x in competitors if str(x.get('team',{}).get('id'))!=str(team_id)),None)
        if mine is None or other is None:continue
        a,b=_score(mine),_score(other)
        if a is None or b is None:continue
        games.append({'date':event.get('date',''),'for':a,'against':b,'home':mine.get('homeAway')=='home','opp_rate':_opponent_win_rate(other)})
    games.sort(key=lambda x:x['date'])
    n=len(games)
    if not n:return {'available':False,'games':0,'adjustment':0,'notice':'No completed games available for this season'}
    wins=sum(g['for']>g['against'] for g in games); ties=sum(g['for']==g['against'] for g in games); losses=n-wins-ties
    win_pct=(wins+ties*.5)/n
    avg_for=sum(g['for'] for g in games)/n; avg_against=sum(g['against'] for g in games)/n
    last=games[-5:]; recent_pct=(sum(g['for']>g['against'] for g in last)+.5*sum(g['for']==g['against'] for g in last))/len(last)
    opp=[g['opp_rate'] for g in games if g['opp_rate'] is not None]
    schedule=sum(opp)/len(opp) if opp else None
    # Limited additional impact: the existing model already accounts for recent scoring margin.
    record_component=max(-3,min(3,(win_pct-.5)*5)) * min(1,n/5)
    schedule_component=max(-1.5,min(1.5,(schedule-.5)*4)) if schedule is not None else 0
    # No extra recent-form or margin adjustment: they are already part of model.strength.
    adjustment=round(record_component+schedule_component,2)
    return {'available':True,'games':n,'wins':wins,'losses':losses,'ties':ties,'win_pct':round(win_pct,3),
      'points_for':round(avg_for,1),'points_against':round(avg_against,1),'recent_games':len(last),
      'recent_win_pct':round(recent_pct,3),'opponent_win_pct':round(schedule,3) if schedule is not None else None,
      'adjustment':adjustment,'notice':'Heuristic, not validated. Opponent records may reflect current records rather than their record at game time.'}
