"""Fetch completed ESPN scoreboard games into a reviewable historical CSV.
Public ESPN endpoints are unofficial; audit coverage before using for predictions.
"""
import argparse,csv,datetime as dt,json,time,urllib.parse
from pathlib import Path
from data_sources import BASE,get_json
FIELDS=['league','season','date','away_id','home_id','away_score','home_score']

def score(x):
    z=x.get('score')
    if isinstance(z,dict):z=z.get('value') or z.get('displayValue')
    return int(float(z))

def parse_events(payload,league,season):
    result=[]
    for ev in payload.get('events',[]):
        try:
            comp=ev['competitions'][0]
            status=comp.get('status',ev.get('status',{})).get('type',{})
            if not status.get('completed',False):continue
            teams=comp['competitors']
            if len(teams)!=2:continue
            home=next(x for x in teams if x.get('homeAway')=='home')
            away=next(x for x in teams if x.get('homeAway')=='away')
            date=ev['date']
            if dt.datetime.fromisoformat(date.replace('Z','+00:00'))>dt.datetime.now(dt.timezone.utc):continue
            result.append(dict(league=league,season=season,date=date,away_id=str(away['team']['id']),home_id=str(home['team']['id']),away_score=score(away),home_score=score(home)))
        except (KeyError,IndexError,TypeError,ValueError,StopIteration):continue
    return result

def collect(league,season,delay=.25):
    code='nfl' if league=='NFL' else 'college-football'
    # ESPN scoreboard supports season and week parameters. Use weekly endpoints
    # instead of guessing a calendar range; collect both regular and postseason.
    rows=[];fail=[]
    weeks=range(1,24) if league=='NFL' else range(1,19)
    for season_type in (2,3):
        for week in weeks:
            query=urllib.parse.urlencode({'dates':season,'seasontype':season_type,'week':week,'limit':500,'groups':80 if league!='NFL' else 0})
            url=f'{BASE}{code}/scoreboard?{query}'
            try:
                payload=get_json(url)
                rows.extend(parse_events(payload,league,season))
            except Exception as exc:fail.append(f'{season_type}/{week}: {exc}')
            time.sleep(delay)
    unique={ (r['league'],r['date'],r['away_id'],r['home_id']):r for r in rows }
    return sorted(unique.values(),key=lambda r:r['date']),fail

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--league',required=True,choices=['NFL','College Football'])
    p.add_argument('--seasons',nargs='+',type=int,required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args();rows=[];fail=[]
    for season in a.seasons:
        found,errors=collect(a.league,season);rows+=found;fail += [f'{season}: {e}' for e in errors]
        print(f'{a.league} {season}: {len(found)} completed games')
    if not rows:raise SystemExit('No completed games retrieved; no CSV written')
    dest=Path(a.output)
    with dest.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    print(f'Wrote {len(rows)} games to {dest}. REVIEW COVERAGE BEFORE TRAINING.')
    if fail:
        err=dest.with_suffix('.errors.txt');err.write_text('\n'.join(fail),encoding='utf-8')
        print(f'{len(fail)} failed requests: {err}; dataset may be incomplete')
if __name__=='__main__':main()
