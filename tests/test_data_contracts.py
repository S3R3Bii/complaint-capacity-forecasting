"""Exercise rejection paths with disposable copies of the aggregate snapshots."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import json
import shutil
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import analyze


class SourceContracts(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT/'data/monthly-aggregates', self.root/'data/monthly-aggregates')
        shutil.copy2(ROOT/'data/manifest.json', self.root/'data/manifest.json')
        self.patch = patch.object(analyze, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)

    def manifest(self):
        return json.loads((self.root/'data/manifest.json').read_text())

    def save_manifest(self, rows):
        (self.root/'data/manifest.json').write_text(json.dumps(rows))

    def test_changed_source_bytes_are_rejected(self):
        path = self.root/self.manifest()[0]['file']
        path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(AssertionError):
            analyze.build_database()

    def test_negative_count_is_rejected_even_with_updated_hash(self):
        manifest = self.manifest()
        path = self.root/manifest[0]['file']
        source = json.loads(path.read_text())
        source['product_counts']['Debt collection'] = -1
        source['total_complaints'] = sum(source['product_counts'].values())
        path.write_text(json.dumps(source))
        manifest[0]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save_manifest(manifest)
        with self.assertRaises(sqlite3.IntegrityError):
            analyze.build_database()

    def test_missing_month_is_rejected(self):
        self.save_manifest(self.manifest()[1:])
        with self.assertRaises(AssertionError):
            analyze.build_database()

    def test_duplicate_snapshot_is_rejected(self):
        manifest = self.manifest()
        self.save_manifest(manifest+[manifest[0]])
        with self.assertRaises(sqlite3.IntegrityError):
            analyze.build_database()

    def test_feature_uses_two_month_old_source(self):
        db = analyze.build_database()
        self.addCleanup(db.close)
        frame, lags, scales = analyze.feature_frame(db, 2)
        row = frame[(frame.month=='2019-01-01') & (frame['product']=='Mortgage')].iloc[0]
        expected = db.execute('SELECT complaints FROM product_counts WHERE month=? AND product=?',
                              ('2018-11-01', 'Mortgage')).fetchone()[0]
        self.assertEqual(row.source_month_2, '2018-11-01')
        self.assertEqual(row.lag_2, expected)
        self.assertEqual(len(frame), 540)


if __name__ == '__main__':
    unittest.main()
