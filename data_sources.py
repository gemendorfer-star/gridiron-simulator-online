import urllib.request, json, random, math, threading, datetime

BASE='https://site.api.espn.com/apis/site/v2/sports/football/'
LEAGUES={'NFL':'nfl','College Football':'college-football'}
HEAD={'User-Agent':'Mozilla/5.0 (compatible; GridironSimulator/2.0)'}

def get_json(url):
    req=urllib.request.Request(url,headers=HEAD)
    with urllib.request.urlopen(req,timeout=12) as r: return json.load(r)

def extract_teams(data):
    result={}
    for sport in data.get('sports',[]):
        for league in sport.get('leagues',[]):
            for entry in league.get('teams',[]):
                t=entry.get('team',entry)
                if t.get('id') and t.get('displayName'): result[t['displayName']]=t
    return result

def find_injuries(data):
    # ESPN injury endpoint structures vary across sports and seasons.
    found=[]
    entries=data.get('injuries',[]) if isinstance(data,dict) else []
    for item in entries:
        if not isinstance(item,dict): continue
        athlete=item.get('athlete') or item.get('player') or {}
        if not isinstance(athlete,dict): athlete={}
        name=athlete.get('displayName') or item.get('displayName') or 'Unidentified player'
        position=athlete.get('position') or {}
        if isinstance(position,dict): position=position.get('abbreviation','')
        status=item.get('status') or item.get('type') or 'Reported injury'
        if isinstance(status,dict): status=status.get('description') or status.get('name') or 'Reported injury'
        found.append({'name':name,'position':str(position),'status':str(status)})
    return found

def extract_depth_starters(data):
    """Parse ESPN depth-chart structures conservatively; never infer from roster order."""
    starters={}
    charts=data.get('depthchart') or data.get('depthcharts') or []
    if isinstance(charts,dict): charts=list(charts.values())
    if not isinstance(charts,list): return starters
    for chart in charts:
        if not isinstance(chart,dict): continue
        positions=chart.get('positions') or chart.get('depth') or {}
        if isinstance(positions,list):
            positions={str(p.get('abbreviation') or p.get('position') or ''):p for p in positions if isinstance(p,dict)}
        if not isinstance(positions,dict): continue
        for key,entry in positions.items():
            if not isinstance(entry,dict): continue
            pos=entry.get('abbreviation') or (entry.get('position') or {}).get('abbreviation') if isinstance(entry.get('position'),dict) else entry.get('abbreviation')
            pos=str(pos or key).upper()
            athletes=entry.get('athletes') or entry.get('players') or []
            if not isinstance(athletes,list) or not athletes: continue
            # Only a clearly ranked first depth-chart entry is treated as projected starter.
            first=athletes[0]
            if not isinstance(first,dict): continue
            rank=first.get('rank',first.get('depth',1))
            if str(rank) not in ('1','1.0'): continue
            athlete=first.get('athlete') or first.get('player') or first
            if not isinstance(athlete,dict): continue
            name=athlete.get('displayName') or athlete.get('fullName')
            if name and pos and pos not in starters: starters[pos]=name
    return starters

def fetch_depthchart(code,tid):
    urls=[f'{BASE}{code}/teams/{tid}/depthchart',f'{BASE}{code}/teams/{tid}/depthcharts']
    for url in urls:
        try:
            d=get_json(url)
            result=extract_depth_starters(d)
            if result: return result,url
        except Exception: pass
    return {},None

def fetch_team(league,team):
    code=LEAGUES[league]; tid=team['id']; result={'injuries':[],'injury_state':'Unknown','starter':'Unknown','starter_state':'Not verified','starters':{},'depth_source':None,'notes':[]}
    url=f'{BASE}{code}/teams/{tid}/injuries'
    try:
        d=get_json(url); result['injuries']=find_injuries(d)
        if isinstance(d.get('injuries'),list): result['injury_state']='Reported list (may be incomplete)'
        else: result['notes'].append('Injury response has no recognized injury list')
    except Exception as e: result['notes'].append('Injury feed unavailable: '+str(e)[:95])
    starters,source=fetch_depthchart(code,tid)
    result['starters']=starters
    result['depth_source']=source
    result['starter']=starters.get('QB','Unknown')
    result['starter_state']='Projected from depth chart (not game-day confirmed)' if starters.get('QB') else 'Not verified'
    if not starters: result['notes'].append('No usable depth chart; starters remain unknown')
    try:
        result['form']=recent_team_form(code,tid)
    except Exception as e:
        result['form']={'count':0};result['notes'].append('Recent team stats unavailable: '+str(e)[:80])
    try:
        result['qb_form']=qb_recent_form(code,result['starter'],result['form'].get('games',[]))
    except Exception as e:
        result['qb_form']={'count':0};result['notes'].append('QB game stats unavailable: '+str(e)[:80])
    return result

def recent_team_form(code, tid):
    """Completed game score differentials from ESPN team schedule; no invented values."""
    url=f'{BASE}{code}/teams/{tid}/schedule'
    data=get_json(url)
    games=[]
    for ev in data.get('events',[]):
        comp=(ev.get('competitions') or [{}])[0]
        if not comp.get('status',{}).get('type',{}).get('completed',False) and not ev.get('status',{}).get('type',{}).get('completed',False):
            continue
        entries=comp.get('competitors',[])
        if len(entries)!=2: continue
        mine=next((x for x in entries if str(x.get('team',{}).get('id'))==str(tid)),None)
        other=next((x for x in entries if str(x.get('team',{}).get('id'))!=str(tid)),None)
        if not mine or not other: continue
        def score(x):
            z=x.get('score');return float(z.get('value')) if isinstance(z,dict) and z.get('value') is not None else float(z)
        try: games.append((ev.get('date',''),score(mine),score(other),str(ev.get('id',''))))
        except (TypeError,ValueError):continue
    games.sort(key=lambda g:g[0],reverse=True)
    games=games[:5]
    if not games:return {'count':0,'points':None,'margin':None,'games':[]}
    return {'count':len(games),'points':sum(g[1] for g in games)/len(games),'margin':sum(g[1]-g[2] for g in games)/len(games),'games':games}

def qb_recent_form(code, qb, games):
    """Look for named QB's passing line in ESPN recent game boxscores; no fallback to made-up ratings."""
    if not qb or qb=='Unknown':return {'count':0,'yards':None,'td':None,'int':None}
    found=[]
    for _,_,_,eid in games[:3]:
        if not eid:continue
        try: data=get_json(f'{BASE}{code}/summary?event={eid}')
        except Exception:continue
        for team in data.get('boxscore',{}).get('players',[]):
            for category in team.get('statistics',[]):
                if 'pass' not in str(category.get('name','')).lower():continue
                labels=[str(x).lower() for x in category.get('labels',[])]
                for entry in category.get('athletes',[]):
                    athlete=entry.get('athlete',{})
                    if athlete.get('displayName','').casefold()!=qb.casefold():continue
                    vals=entry.get('stats',[])
                    def val(keys):
                        for key in keys:
                            if key in labels:
                                try:return float(vals[labels.index(key)])
                                except (ValueError,IndexError,TypeError):return None
                        return None
                    yards=val(['yds','yards']);td=val(['td']);ints=val(['int'])
                    if yards is not None:found.append((yards,td or 0,ints or 0))
    if not found:return {'count':0,'yards':None,'td':None,'int':None}
    return {'count':len(found),'yards':sum(x[0] for x in found)/len(found),'td':sum(x[1] for x in found)/len(found),'int':sum(x[2] for x in found)/len(found)}

def evidence_adjustment(team_data, league):
    form=team_data.get('form') or {}
    n=form.get('count',0)
    if not n:return 0.,'No recent completed game statistics available'
    # Conservative regression to neutral; capped so opponent quality and schedule are not overclaimed.
    margin=form['margin'];adjust=max(-7.,min(7.,margin*0.18*min(n,5)/5))
    qb=team_data.get('qb_form') or {}
    if qb.get('count',0):
        # Modest contribution; QB production overlaps team results, so cap to avoid double counting.
        qadj=max(-2.,min(2.,((qb['yards']-220)/110 + (qb['td']-1.5)*0.8-qb['int']*0.6)*0.6))
        adjust+=qadj
        desc=f'{n} recent games, avg margin {margin:+.1f}; QB {qb["count"]} boxscores, {qb["yards"]:.0f} pass yds/game'
    else:desc=f'{n} recent games, avg margin {margin:+.1f}; QB performance unavailable'
    return adjust,desc

def injury_penalty(injuries):
    penalty=0.; counted=[]
    for x in injuries:
        s=x['status'].lower(); pos=x['position'].upper()
        if any(w in s for w in ('out','injured reserve','ir','suspended','inactive','doubtful')): factor=1.
        elif 'questionable' in s: factor=.35
        else: factor=0.
        if factor:
            weight=6 if pos=='QB' else 2.1 if pos in ('WR','RB','TE','LT','RT','OT','EDGE','DE','CB') else 1.2
            penalty+=weight*factor; counted.append(x['name']+' ('+pos+', '+x['status']+')')
    return min(18.,penalty),counted

