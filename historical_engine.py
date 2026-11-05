"""Leakage-safe, dependency-free Elo baseline and walk-forward evaluation.

CSV schema: league,season,date,away_id,home_id,away_score,home_score
Dates are ISO 8601; one row per completed game. Do not use future results.
This is a *baseline*, not a trained player/injury model.
"""
import csv, json, math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

K=20.0
HOME_ELO=55.0
START=1500.0

def parse_date(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def load_games(path):
    games=[];seen=set()
    with open(path,newline='',encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            league=row['league'].strip();season=int(row['season']); date=parse_date(row['date'])
            away=row['away_id'].strip();home=row['home_id'].strip()
            if league not in ('NFL','College Football') or not away or not home or away==home:raise ValueError('Invalid team or league')
            if not (1990<=season<=datetime.now(timezone.utc).year):raise ValueError('Invalid season')
            if date>datetime.now(timezone.utc):raise ValueError('Future game cannot be historical data')
            a=int(row['away_score']);h=int(row['home_score'])
            if min(a,h)<0 or max(a,h)>150:raise ValueError('Invalid score')
            key=(league,season,date,away,home)
            if key in seen:raise ValueError('Duplicate game')
            seen.add(key);games.append(dict(league=league,season=season,date=date,away=away,home=home,a=a,h=h))
    return sorted(games,key=lambda g:(g['date'],g['league'],g['away'],g['home']))

def probability(rating_diff,scale=400):
    return 1/(1+10**(-max(-1600,min(1600,rating_diff))/scale))

def update(away,home,score_a,score_h):
    p=probability(home+HOME_ELO-away)
    outcome=1 if score_h>score_a else 0 if score_h<score_a else .5
    # Capped margin-of-victory multiplier; one blowout must not dominate.
    mov=1+min(abs(score_h-score_a),28)/28
    delta=K*mov*(outcome-p)
    return away-delta,home+delta

def walk_forward(games,league,scale=400, min_games=3, through=None):
    """Predict BEFORE updating. Same-time kickoffs are processed as one batch."""
    rows=[g for g in games if g['league']==league and (through is None or g['date']<through)]
    ratings=defaultdict(lambda:START);counts=defaultdict(int);pred=[]
    i=0
    while i<len(rows):
        j=i+1
        while j<len(rows) and rows[j]['date']==rows[i]['date']:j+=1
        batch=rows[i:j]
        for g in batch:
            if counts[g['away']]>=min_games and counts[g['home']]>=min_games:
                p=probability(ratings[g['home']]+HOME_ELO-ratings[g['away']],scale)
                y=1 if g['h']>g['a'] else 0 if g['h']<g['a'] else .5
                pred.append(dict(date=g['date'].isoformat(),season=g['season'],home=g['home'],away=g['away'],p=p,y=y))
        # Each team's ratings update after ALL games at same kickoff were predicted.
        for g in batch:
            a,h=update(ratings[g['away']],ratings[g['home']],g['a'],g['h'])
            ratings[g['away']]=a;ratings[g['home']]=h
            counts[g['away']]+=1;counts[g['home']]+=1
        i=j
    return pred,dict(ratings),dict(counts)

def metrics(pred):
    if not pred:return {'games':0,'accuracy':None,'brier':None,'log_loss':None}
    decisive=[r for r in pred if r['y']!=.5]
    accuracy=sum((r['p']>.5)==(r['y']==1) for r in decisive)/len(decisive) if decisive else None
    brier=sum((r['p']-r['y'])**2 for r in pred)/len(pred)
    logloss=-sum(r['y']*math.log(max(1e-12,r['p']))+(1-r['y'])*math.log(max(1e-12,1-r['p'])) for r in pred)/len(pred)
    return {'games':len(pred),'decisive_games':len(decisive),'accuracy':round(accuracy,4) if accuracy is not None else None,'brier':round(brier,4),'log_loss':round(logloss,4)}

def calibrate(games,league,train_through_season):
    """Choose scale using only earlier seasons; later seasons remain untouched."""
    training=[g for g in games if g['league']==league and g['season']<=train_through_season]
    if len(training)<30:raise ValueError('Need at least 30 training games')
    options=[]
    for scale in (250,300,350,400,450,500,600,750):
        preds,_,_=walk_forward(training,league,scale)
        if len(preds)<15:raise ValueError('Need at least 15 eligible training predictions')
        options.append((metrics(preds)['brier'],scale))
    return min(options)[1]

def evaluate_split(games,league,train_through_season,test_season):
    if test_season<=train_through_season:raise ValueError('Test season must be after training seasons')
    scale=calibrate(games,league,train_through_season)
    preds,ratings,counts=walk_forward([g for g in games if g['season']<=test_season],league,scale)
    train=[r for r in preds if r['season']<=train_through_season]
    test=[r for r in preds if r['season']==test_season]
    if not test:raise ValueError('No eligible test games; check CSV coverage')
    return {'league':league,'train_through_season':train_through_season,'test_season':test_season,'scale':scale,'training':metrics(train),'held_out_test':metrics(test),'warning':'Elo-only baseline. Does not validate injuries, players, exact scores, or the full simulator.'}

def build_snapshot(games,league,as_of,scale):
    preds,ratings,counts=walk_forward(games,league,scale,through=as_of)
    return {'league':league,'as_of':as_of.isoformat(),'scale':scale,'ratings':ratings,'games_played':counts,'source':'Historical completed games before as_of; Elo baseline only'}

def main():
    import argparse
    p=argparse.ArgumentParser(description='Historical Elo evaluation with a held-out season')
    p.add_argument('csv');p.add_argument('--league',choices=['NFL','College Football'],required=True)
    p.add_argument('--train-through',type=int,required=True);p.add_argument('--test-season',type=int,required=True)
    p.add_argument('--snapshot-as-of',help='Optional ISO date for an Elo ratings snapshot')
    p.add_argument('--output',default='historical_report.json')
    args=p.parse_args();games=load_games(args.csv)
    report=evaluate_split(games,args.league,args.train_through,args.test_season)
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    if args.snapshot_as_of:
        snapshot=build_snapshot(games,args.league,parse_date(args.snapshot_as_of),report['scale'])
        out=Path(args.output).with_name('elo_snapshot_'+('nfl' if args.league=='NFL' else 'college')+'.json')
        out.write_text(json.dumps(snapshot,indent=2)+'\n',encoding='utf-8')
        print('Wrote',out)
if __name__=='__main__':main()
