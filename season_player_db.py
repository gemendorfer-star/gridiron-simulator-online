"""Season boxscore collection with transparent opponent adjustment; experimental, not trained."""
import datetime
from data_sources import BASE, get_json
from player_history import extract_boxscore_players, parse_num

def season_games(code, team_id, season):
    data=get_json(f"{BASE}{code}/teams/{team_id}/schedule?season={int(season)}")
    result=[]
    for ev in data.get('events',[]):
        comp=(ev.get('competitions') or [{}])[0]
        if not (comp.get('status',{}).get('type',{}).get('completed') or ev.get('status',{}).get('type',{}).get('completed')):continue
        contestants=comp.get('competitors') or []
        own=next((c for c in contestants if str((c.get('team') or {}).get('id'))==str(team_id)),None)
        opp=next((c for c in contestants if str((c.get('team') or {}).get('id'))!=str(team_id)),None)
        if not own or not opp:continue
        date=ev.get('date','')
        if date and date[:10]>datetime.datetime.now(datetime.timezone.utc).date().isoformat():continue
        result.append({'id':str(ev.get('id','')),'date':date,'opponent_id':str((opp.get('team') or {}).get('id','')),'opponent':(opp.get('team') or {}).get('displayName','Unknown')})
    return sorted([g for g in result if g['id']],key=lambda g:g['date'])

def opponent_win_rates(code, games, season, fetch=get_json):
    """Retrospective opponent season record: never use this for historical pregame backtests."""
    cache={};rates={}
    for g in games:
        oid=g['opponent_id']
        if oid not in cache:
            try:
                d=fetch(f"{BASE}{code}/teams/{oid}/schedule?season={int(season)}")
                events=d.get('events',[]);w=0;n=0
                for ev in events:
                    c=(ev.get('competitions') or [{}])[0]
                    if not (c.get('status',{}).get('type',{}).get('completed') or ev.get('status',{}).get('type',{}).get('completed')):continue
                    if ev.get('date','')[:10]>datetime.datetime.now(datetime.timezone.utc).date().isoformat():continue
                    own=next((x for x in c.get('competitors',[]) if str((x.get('team') or {}).get('id'))==oid),None)
                    if not own:continue
                    result=str(own.get('winner','')).lower()
                    if result not in ('true','false'):continue
                    n+=1;w+=(result=='true')
                cache[oid]=(w/n if n else None)
            except Exception:cache[oid]=None
        rates[g['id']]=cache[oid]
    return rates

def season_player_summary(code,team_id,season,fetch=get_json, schedule=None, rates=None):
    games=season_games(code,team_id,season) if schedule is None else schedule
    if rates is None:rates=opponent_win_rates(code,games,season,fetch)
    rows={};failed=0;success=0
    for game in games:
        try:data=fetch(f"{BASE}{code}/summary?event={game['id']}")
        except Exception:failed+=1;continue
        success+=1
        for p in extract_boxscore_players(data,team_id):
            category=p['category'].lower()
            if not any(x in category for x in ('pass','rush','receiv','defen')):continue
            yards=parse_num(p['stats'].get('yds',p['stats'].get('yards')))
            if 'defen' in category:
                stats=p['stats']
                def pick(*keys):
                    for k in keys:
                        if k in stats:return parse_num(stats[k])
                    return None
                tackles=pick('tot','total','tackles','tkl','tack')
                sacks=pick('sacks','sack','sk')
                interceptions=pick('int','ints','interceptions')
                # ESPN defensive labels differ by competition; only use recognized labels.
                if all(v is None for v in (tackles,sacks,interceptions)):continue
                yards=0.0
            elif yards is None:continue
            key=(p['name'],category)
            rows.setdefault(key,[]).append({'yards':yards,'td':parse_num(p['stats'].get('td')),'int':parse_num(p['stats'].get('int')),'opponent_rate':rates.get(game['id']),'date':game['date'],'position':p['position'],'tackles':tackles if 'defen' in category else None,'sacks':sacks if 'defen' in category else None,'def_int':interceptions if 'defen' in category else None})
    players=[]
    for (name,category),appearances in rows.items():
        n=len(appearances);avg=sum(r['yards'] for r in appearances)/n
        known=[r for r in appearances if r['opponent_rate'] is not None]
        # An explicitly heuristic, small opponent-strength correction, not an EPA/player grade.
        adjusted=(sum(r['yards']*(1+0.20*(r['opponent_rate']-.5)) for r in known)/len(known)) if known else None
        players.append({'name':name,'position':appearances[0]['position'],'category':category,'games':n,'yards':round(avg,1),'adjusted_yards':round(adjusted,1) if adjusted is not None else None,'opponent_coverage':len(known),'td':round(sum(r['td'] or 0 for r in appearances)/n,2),'int':round(sum(r['int'] or 0 for r in appearances)/n,2) if 'pass' in category else None,'tackles':round(sum(r['tackles'] or 0 for r in appearances)/n,2) if 'defen' in category else None,'sacks':round(sum(r['sacks'] or 0 for r in appearances)/n,2) if 'defen' in category else None,'def_int':round(sum(r['def_int'] or 0 for r in appearances)/n,2) if 'defen' in category else None})
    return {'season':season,'games_scheduled':len(games),'checked':success,'failed':failed,'players':sorted(players,key=lambda p:(-p['games'],-p['yards'],p['name']))}

def season_starter_impact(history,starters,injuries):
    matched=[];impact=0.0
    names={v.casefold():k for k,v in starters.items()}
    unavailable={x.get('name','').casefold() for x in injuries if any(s in x.get('status','').lower() for s in ('out','inactive','injured reserve','suspended'))}
    for p in history.get('players',[]):
        key=p['name'].casefold()
        if key not in names or key in unavailable:continue
        pos=names[key].upper();cat=p['category']
        if 'defen' in cat:continue
        if not ((pos=='QB' and 'pass' in cat) or (pos=='RB' and 'rush' in cat) or (pos in ('WR','TE') and 'receiv' in cat)):continue
        base={'QB':220,'RB':65,'WR':55,'TE':40}[pos]
        value=p['adjusted_yards'] if p['adjusted_yards'] is not None else p['yards']
        shrink=min(1,p['games']/8)
        effect=max(-1,min(1,(value-base)/max(base,1)))*shrink*({'QB':1.2,'RB':.5,'WR':.4,'TE':.3}[pos])
        impact+=effect;matched.append((p,round(effect,2)))
    return max(-2.5,min(2.5,impact)),matched
