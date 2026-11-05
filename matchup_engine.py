"""Conservative, auditable experimental position matchup effects.
Not trained or calibrated. Missing stats yield neutral adjustments.
"""
from math import isfinite

def missing(status):
    status=(status or '').lower()
    return any(x in status for x in ('out','inactive','injured reserve','suspended','doubtful'))

def active_names(starters,injuries):
    excluded={str(x.get('name','')).strip().casefold() for x in injuries if missing(x.get('status'))}
    return {str(name).strip().casefold():pos.upper() for pos,name in starters.items() if str(name).strip().casefold() not in excluded}

def defensive_impact(history,starters,injuries):
    active=active_names(starters,injuries);impact=0.;notes=[];matched=0
    for p in history.get('players',[]):
        name=p.get('name','').strip().casefold();pos=active.get(name)
        if not pos or 'defen' not in p.get('category','').lower():continue
        if pos not in ('DE','EDGE','DT','NT','LB','MLB','OLB','ILB','CB','S','FS','SS','DB'):continue
        games=int(p.get('games') or 0)
        if games<2:continue
        sacks=p.get('sacks');ints=p.get('def_int');tackles=p.get('tackles')
        if all(v is None for v in (sacks,ints,tackles)):continue
        def num(v):return float(v or 0)
        # Boxscore proxies, deliberately small and sample-size shrunk.
        val=(num(sacks)*.17+num(ints)*.22+num(tackles)*.012)*min(1.,games/8.)
        val=max(0.,min(.42,val))
        impact+=val;matched+=1
        notes.append(f'{p["name"]} ({pos}): {games} appearances, sacks {sacks}, INT {ints}, tackles {tackles}; +{val:.2f}')
    # Center on modest reference to avoid stacking large positive bonuses for deep rosters.
    points=max(-1.5,min(1.5,impact-min(matched,8)*.12)) if matched else 0.
    return {'points':round(points,3),'matched':matched,'notes':notes,'confidence':'low: tackles/sacks/INT are incomplete defensive value proxies'}

def matchup_adjustment(offense,off_starters,defense,def_starters,off_injuries,def_injuries):
    """Only computes line matchup with explicit line metrics, not inferred from unrelated yards/tackles."""
    oa=active_names(off_starters,off_injuries);da=active_names(def_starters,def_injuries)
    ol={'LT','RT','OT','LG','RG','G','C','OL'};dl={'DE','EDGE','DT','NT','DL'}
    def metric(players,active,positions,key):
        found=[]
        for p in players:
            if active.get(p.get('name','').strip().casefold()) not in positions:continue
            v=p.get(key)
            if v is None:continue
            try:v=float(v)
            except (TypeError,ValueError):continue
            if isfinite(v) and int(p.get('games') or 0)>=3:found.append(v)
        return sum(found)/len(found) if found else None
    # These fields can be provided via a future licensed charting provider or imported data.
    protection=metric(offense.get('players',[]),oa,ol,'pass_block_win_rate')
    rush=metric(defense.get('players',[]),da,dl,'pass_rush_win_rate')
    if protection is None or rush is None:
        return {'points':0.,'notes':['Line matchup neutral: pass-block and pass-rush win-rate data unavailable. Boxscore tackles are not substituted.'],'coverage':False}
    # Values must be fractions 0..1; coefficients are unvalidated and intentionally bounded.
    if not (0<=protection<=1 and 0<=rush<=1):return {'points':0.,'notes':['Invalid line metrics; neutral matchup.'],'coverage':False}
    points=max(-1.5,min(1.5,(protection-rush)*3.))
    return {'points':round(points,3),'notes':[f'OL pass-block win rate {protection:.1%} vs DL pass-rush win rate {rush:.1%}; heuristic {points:+.2f}'], 'coverage':True}
