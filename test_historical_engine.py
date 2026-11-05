import unittest
from datetime import datetime,timezone,timedelta
from historical_engine import walk_forward,metrics,build_snapshot,probability

class HistoricalEngineTests(unittest.TestCase):
    def test_no_prediction_without_history(self):
        d=datetime(2024,1,1,tzinfo=timezone.utc)
        games=[dict(league='NFL',season=2024,date=d+timedelta(days=i),away='A',home='B',a=14,h=21) for i in range(5)]
        preds,ratings,counts=walk_forward(games,'NFL')
        self.assertEqual(len(preds),2)
        self.assertEqual(counts['A'],5)
        self.assertEqual(metrics(preds)['games'],2)
    def test_future_games_not_in_snapshot(self):
        d=datetime(2024,1,1,tzinfo=timezone.utc)
        games=[dict(league='NFL',season=2024,date=d+timedelta(days=i),away='A',home='B',a=14,h=21) for i in range(5)]
        snap=build_snapshot(games,'NFL',d+timedelta(days=3),400)
        self.assertEqual(snap['games_played']['A'],3)
    def test_same_kickoff_no_leakage(self):
        d=datetime(2024,1,1,tzinfo=timezone.utc)
        g=[dict(league='NFL',season=2024,date=d,away='A',home='B',a=10,h=20),dict(league='NFL',season=2024,date=d,away='A',home='C',a=40,h=10)]
        preds,ratings,counts=walk_forward(g,'NFL',min_games=0)
        self.assertEqual(preds[0]['p'],preds[1]['p'])
    def test_probability_bounds(self):
        self.assertGreater(probability(100),.5)
        self.assertLess(probability(-100),.5)
if __name__=='__main__':unittest.main()
