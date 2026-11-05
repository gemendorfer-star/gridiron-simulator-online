"""Illustrative single-game box score, NOT a player-by-player play simulation."""
import random

def _allocate(total,players,weights):
    if not players:return []
    weights=[max(0.1,float(w)) for w in weights]
    shares=[total*w/sum(weights) for w in weights]
    rounded=[int(v) for v in shares]
    for i in sorted(range(len(shares)),key=lambda k:shares[k]-rounded[k],reverse=True)[:max(0,total-sum(rounded))]:rounded[i]+=1
    return rounded

def project_box_score(history,team_data,score,drives,seed=7):
    """Assign illustrative yards/TDs using historical shares of available players.
    Does not claim play-level statistical consistency or verified game-day rosters.
    """
    rng=random.Random(seed)
    players=history.get('players',[])
    unavailable={x.get('name','').casefold() for x in team_data.get('injuries',[]) if any(t in x.get('status','').lower() for t in ('out','inactive','injured reserve','suspended'))}
    starters={v.casefold() for v in team_data.get('starters',{}).values()}
    def choose(kind):
        candidates=[p for p in players if kind in p.get('category','').lower() and p['name'].casefold() not in unavailable]
        if starters:candidates=[p for p in candidates if p['name'].casefold() in starters]
        return sorted(candidates,key=lambda p:-p.get('yards',0))[:8]
    qb=choose('pass')[:1];rush=choose('rush');recv=choose('receiv');defense=choose('defen')
    total_yards=max(90,round(sum(max(0,d[3]) for d in drives)*rng.uniform(.85,1.15)))
    passing=int(total_yards*rng.uniform(.48,.72)) if qb else 0
    rushing=max(0,total_yards-passing) if rush else 0
    if not qb and not rush:total_yards=passing=rushing=0
    touchdowns=sum(1 for d in drives if d[4]=='Touchdown')
    lines=[f'Illustrative simulated team score: {score}',f'Illustrative offensive yards: {total_yards} (passing {passing}, rushing {rushing})', 'Based on season box-score shares and one sample simulated game; NOT observed game statistics.','']
    if qb:
        q=qb[0];td=min(touchdowns,round(touchdowns*.65));ints=rng.choices([0,1,2],[.68,.27,.05])[0]
        lines.append(f'PASSING: {q["name"]}: {passing} yards, {td} TD, {ints} INT')
    else:lines.append('PASSING: unavailable — no matched projected QB with box-score history')
    if rush:
        lines.append('RUSHING:')
        for p,y in zip(rush,_allocate(rushing,rush,[p.get('yards',0) for p in rush])):lines.append(f'  {p["name"]}: {y} yards')
    else:lines.append('RUSHING: unavailable — no matched players')
    if recv and passing:
        lines.append('RECEIVING:')
        for p,y in zip(recv,_allocate(passing,recv,[p.get('yards',0) for p in recv])):lines.append(f'  {p["name"]}: {y} yards')
    else:lines.append('RECEIVING: unavailable — no matched players')
    if defense:
        lines.append('DEFENSE (illustrative; not derived from simulated plays):')
        for p in defense[:6]:
            tackles=max(0,round((p.get('tackles') or 0)*rng.uniform(.65,1.4)))
            sacks=max(0,round((p.get('sacks') or 0)*rng.uniform(.5,1.6)))
            ints=max(0,round((p.get('def_int') or 0)*rng.uniform(.5,1.6)))
            lines.append(f'  {p["name"]}: {tackles} tackles, {sacks} sacks, {ints} INT')
    else:lines.append('DEFENSE: unavailable — no matched defenders')
    if not players:lines.append('NO PLAYER HISTORY: stats unavailable, not invented.')
    return '\n'.join(lines)
