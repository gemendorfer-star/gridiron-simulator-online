"""Optional precomputed Elo snapshot. Never silently use stale or future ratings."""
import json
from datetime import datetime,timezone
from pathlib import Path

def load_pair(league,away_id,home_id,season):
    name='elo_snapshot_nfl.json' if league=='NFL' else 'elo_snapshot_college.json'
    path=Path(__file__).with_name(name)
    if not path.exists():return None,'Historical Elo snapshot not installed; using experimental heuristic ratings.'
    try:
        d=json.loads(path.read_text(encoding='utf-8'))
        stamp=datetime.fromisoformat(d['as_of'].replace('Z','+00:00'))
        if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
        age=(datetime.now(timezone.utc)-stamp).total_seconds()/86400
        if age<0 or age>14:return None,'Historical Elo snapshot is future-dated or over 14 days old; ignored.'
        if d['league']!=league:return None,'Historical Elo league mismatch; ignored.'
        if int(season)!=datetime.now(timezone.utc).year:return None,'Selected season is not current; live Elo snapshot ignored.'
        ids=(str(away_id),str(home_id));ratings=d['ratings'];counts=d['games_played']
        if any(x not in ratings or counts.get(x,0)<3 for x in ids):return None,'Historical Elo lacks 3 games per team; ignored.'
        return {'away':float(ratings[ids[0]]),'home':float(ratings[ids[1]]),'as_of':d['as_of'],'scale':float(d['scale'])},None
    except (ValueError,KeyError,TypeError,OSError) as e:return None,'Invalid Elo snapshot; ignored: '+str(e)[:80]
