"""Regression checks for labels leaking past the forecast information boundary."""
import sys
import unittest
from pathlib import Path
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from analyze import available_training

class LabelAvailability(unittest.TestCase):
    def test_two_month_delay_rejects_previous_month(self):
        rows=pd.DataFrame({'month':['2024-04-01','2024-05-01','2024-06-01','2024-07-01']})
        self.assertEqual(available_training(rows,'2024-07-01',2).month.tolist(),
                         ['2024-04-01','2024-05-01'])

    def test_three_month_delay_and_year_boundary(self):
        rows=pd.DataFrame({'month':['2022-10-01','2022-11-01','2022-12-01','2023-01-01']})
        self.assertEqual(available_training(rows,'2023-01-01',3).month.tolist(),['2022-10-01'])

    def test_boundary_label_is_retained(self):
        rows=pd.DataFrame({'month':['2024-05-01','2024-06-01']})
        self.assertEqual(len(available_training(rows,'2024-07-01',2)),1)

if __name__=='__main__': unittest.main()
