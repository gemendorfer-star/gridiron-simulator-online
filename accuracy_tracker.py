"""Historical, walk-forward TEAM-FORM BASELINE evaluation (not validation of full simulator).
Only games completed before each kickoff contribute to team form. No current injuries
or player data are used, to avoid historical leakage.
"""
from collections import defaultdict
from datetime import datetime, timezone
import math
from data_sources import BASE, LEAGUES, get_json


def _games(payload):
    out=[]
    for event in payload.get('events',[]):
        comp=(event.get('competitions') or [{}])[0]
        status=comp.get('status') or event.get('status') or {}
        typ=status.get('type') or {}
        if not typ.get('completed'): continue
        sides={}
        for c in comp.get('competitors',[]):
            side=c.get('homeAway')
            try: score=int(c.get('score'))
            except (TypeError,ValueError):continue
            if side in ('home','away') and c.get('team',{}).get('id'):
                sides[side]=(str(c['team']['id']),c['team'].get('displayName','Team'),score)
        if len(sides)!=2:continue
        date=comp.get('date') or event.get('date') or ''
        try: kickoff=datetime.fromisoformat(date.replace('Z','+00:00'))
        except ValueError:continue
        out.append((kickoff,str(event.get('id')),sides['away'],sides['home']))
    return out


def evaluate(league='NFL',season=2024,weeks=10):
    if league not in LEAGUES:raise ValueError('Invalid league')
    if not 2020<=season<=2025:raise ValueError('Choose a completed historical season (2020–2025)')
    if weeks not in (6,10,14):raise ValueError('Choose 6, 10, or 14 weeks')
    code=LEAGUES[league]
    all_games={}; failed=0
    for week in range(1,weeks+1):
        url=f'{BASE}{code}/scoreboard?dates={season}&seasontype=2&week={week}&limit=400'
        try:
            for g in _games(get_json(url)):all_games[g[1]]=g
        except Exception:failed+=1
    if not all_games:raise RuntimeError('No completed historical games could be retrieved from ESPN')
    history=defaultdict(list);evaluated=[];skipped=0
    for kickoff,gid,away,home in sorted(all_games.values(),key=lambda g:(g[0],g[1])):
        aid,an,asc=away;hid,hn,hsc=home
        a=history[aid];h=history[hid]
        # Require at least 3 prior games for each team. No future information.
        if len(a)>=3 and len(h)>=3:
            # Shrunk recent scoring margin; +2.2 point home advantage is an assumption.
            am=sum(x for x in a[-5:])/len(a[-5:]);hm=sum(x for x in h[-5:])/len(h[-5:])
            projected_margin=(hm-am)*.55+2.2
            # Illustrative probability transform, not calibrated.
            p_home=1/(1+math.exp(-projected_margin/11))
            predicted='home' if p_home>=.5 else 'away'
            winner='home' if hsc>asc else 'away' if asc>hsc else 'tie'
            evaluated.append({'date':kickoff.date().isoformat(),'away':an,'home':hn,'score':f'{asc}–{hsc}',
                              'predicted':hn if predicted=='home' else an,
                              'winner':hn if winner=='home' else an if winner=='away' else 'Tie',
                              'correct':predicted==winner,'home_probability':round(p_home*100,1)})
        else:skipped+=1
        # Same-kickoff results aren't used for each other's forecasts.
        history[aid].append(asc-hsc);history[hid].append(hsc-asc)
    decisive=[g for g in evaluated if g['winner']!='Tie']
    correct=sum(g['correct'] for g in decisive)
    return {'league':league,'season':season,'weeks_requested':weeks,'games_retrieved':len(all_games),
            'games_evaluated':len(decisive),'correct':correct,'incorrect':len(decisive)-correct,
            'accuracy_pct':round(100*correct/len(decisive),1) if decisive else None,
            'skipped_insufficient_history':skipped,'weeks_unavailable':failed,
            'recent_games':evaluated[-20:][::-1],
            'method':'Historical walk-forward team scoring-margin baseline, NOT the full simulator. At least 3 prior games per team; last 5 scoring margins, 2.2-point assumed home advantage. No player/injury history, schedule strength, or calibrated probabilities. Results may differ from current app predictions.'}
