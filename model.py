"""Transparent experimental football model; NOT a trained/validated betting model."""
import math,random,statistics
from data_sources import injury_penalty,evidence_adjustment

POSITION_VALUE={'QB':6.0,'WR':1.7,'RB':1.3,'TE':1.1,'LT':1.9,'RT':1.5,'OT':1.6,'G':1.0,'C':1.2,'DE':1.6,'DT':1.3,'EDGE':1.8,'LB':1.1,'CB':1.5,'S':1.0,'K':0.6}

def grade_player(position, qb_form=None, manual_grade=None):
    """0-100 heuristic grade. No grade is inferred from a player's name or depth rank."""
    if manual_grade is not None:return max(0,min(100,float(manual_grade))),'user-entered grade'
    if position=='QB' and qb_form and qb_form.get('count',0):
        yards=qb_form['yards'];td=qb_form['td'];ints=qb_form['int']
        raw=50+(yards-220)*.065+(td-1.5)*6-ints*5
        return round(max(25,min(85,raw)),1),f'heuristic: {qb_form["count"]} passing boxscores'
    return None,'unrated — no verified individual performance data'

def roster_report(d,overrides=None):
    overrides=overrides or {}; rows=[]
    injuries={x['name'].casefold():x for x in d.get('injuries',[])}
    for pos,name in sorted(d.get('starters',{}).items()):
        grade,source=grade_player(pos,d.get('qb_form') if pos=='QB' else None,overrides.get(name))
        injury=injuries.get(name.casefold(),{})
        rows.append({'pos':pos,'name':name,'grade':grade,'grade_source':source,'injury':injury.get('status','Unknown / not reported')})
    return rows

def unavailable(status):
    s=status.lower()
    if any(x in s for x in ('out','injured reserve','inactive','suspended','doubtful')):return 1.0
    if 'questionable' in s:return .35
    return 0

def player_adjustment(d, overrides=None):
    """Only project a player's rating when there is real QB production or explicit user input.
    An unavailable starter is replaced by an unknown-strength backup, not a fictitious named player.
    """
    rows=roster_report(d,overrides);effect=0; notes=[]
    for p in rows:
        if p['grade'] is None:continue
        position=p['pos'];value=POSITION_VALUE.get(position,0.7)
        # Relative to an average starter; uncertainty shrinkage for sparse QB samples.
        shrink=min(1,(d.get('qb_form') or {}).get('count',0)/5) if position=='QB' and p['grade_source'].startswith('heuristic') else 1
        availability=1-unavailable(p['injury'])
        contribution=(p['grade']-50)/50*value*shrink*availability
        effect+=contribution
        notes.append(f'{p["name"]} {position}: {p["grade"]:.0f}/100 ({p["grade_source"]}), {contribution:+.1f} points')
    return max(-8,min(8,effect)),notes

def strength(d,league,overrides=None):
    form,_=evidence_adjustment(d,league)
    # Avoid double counting the QB's boxscore contribution in evidence_adjustment:
    qb=d.get('qb_form') or {}
    if qb.get('count',0):
        qadj=max(-2,min(2,((qb['yards']-220)/110+(qb['td']-1.5)*.8-qb['int']*.6)*.6))
        form-=qadj
    penalty,_=injury_penalty(d.get('injuries',[]))
    individual,notes=player_adjustment(d,overrides)
    return form-penalty+individual,{'team_form':round(form,2),'injury_penalty':round(penalty,2),'individual':round(individual,2),'player_notes':notes}

def play_game(away_strength,home_strength,league='NFL',rng=None,record=False):
    """Simplified possession/play simulation; probabilities are illustrative, not fitted to play-by-play data."""
    rng=rng or random.Random(); base=24 if league=='NFL' else 29
    # Approximately 11 drives/team; drive success adjusts to team strength.
    scores=[0,0];drives=[]
    for drive in range(22):
        side=drive%2;adv=(away_strength if side==0 else home_strength)+(0 if side==0 else 2.2)
        expected=max(7,min(48,base+adv))
        p_score=max(.15,min(.7,expected/11/6.0))
        plays=rng.randint(3,12);yards=0;turnover=False;events=[]
        for play in range(plays):
            roll=rng.random()
            if roll<.018:events.append('turnover');turnover=True;break
            if roll<.095:gain=-rng.randint(1,8);events.append('loss')
            elif roll<.48:gain=rng.randint(0,4)
            elif roll<.88:gain=rng.randint(5,12)
            else:gain=rng.randint(13,32);events.append('explosive')
            yards+=gain
        if turnover:points=0;outcome='Turnover'
        elif rng.random()<p_score:
            if rng.random()<.68:points=7;outcome='Touchdown'
            else:points=3;outcome='Field goal'
        else:points=0;outcome='Punt / downs'
        scores[side]+=points
        if record:drives.append((drive+1,'Away' if side==0 else 'Home',plays,yards,outcome,points))
    # NFL regular-season ties possible; college football has overtime.
    if scores[0]==scores[1] and league!='NFL':
        for _ in range(10):
            a=rng.choice((3,6,7));h=rng.choice((3,6,7))
            scores[0]+=a;scores[1]+=h
            if a!=h:break
        if scores[0]==scores[1]:scores[rng.randrange(2)]+=2
    return scores,drives

def monte_carlo(a,h,league,n=2000,seed=None):
    rng=random.Random(seed);ascores=[];hscores=[];wins=[0,0,0]
    for _ in range(n):
        score,_=play_game(a,h,league,rng);ascores.append(score[0]);hscores.append(score[1]);wins[0 if score[0]>score[1] else 1 if score[1]>score[0] else 2]+=1
    sample_scores,sample_drives=play_game(a,h,league,rng,True)
    return {'away_pct':100*wins[0]/n,'home_pct':100*wins[1]/n,'tie_pct':100*wins[2]/n,'away_score':statistics.mean(ascores),'home_score':statistics.mean(hscores),'n':n,'sample_drives':sample_drives,'sample_score':{'away':sample_scores[0],'home':sample_scores[1]},'model_status':'Experimental; not calibrated or validated against held-out games'}

def backtest_schedule(games):
    """Chronological expanding-window, one-team baseline. No future results used for each forecast.
    Not a head-to-head backtest, and not a validation of the full player/injury model.
    """
    chron=sorted(games,key=lambda x:x[0]);errors=[];preds=[]
    for i in range(3,len(chron)):
        previous=chron[max(0,i-5):i]
        avg_for=statistics.mean(x[1] for x in previous)
        avg_against=statistics.mean(x[2] for x in previous)
        actual=chron[i][1];pred=.65*avg_for+.35*(24 if avg_for<28 else 29)
        errors.append(abs(pred-actual));preds.append((chron[i][0],round(pred,1),actual))
    return {'count':len(errors),'mae':round(statistics.mean(errors),2) if errors else None,'predictions':preds,'description':'Walk-forward one-team points MAE; does not validate matchup win probabilities or injury/player adjustments'}
