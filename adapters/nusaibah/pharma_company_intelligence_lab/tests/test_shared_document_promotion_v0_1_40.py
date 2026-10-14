"""Published shared documents must not change during additive promotion."""
import hashlib,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class SharedDocumentPromotionTests(unittest.TestCase):
    def test_shared_documents_keep_published_canonical_bytes(self):
        expected={
            'README.md':'9b8d82849dcb51c699b0b8a27f6bcf387d147b964a9e3819d88d2eab95a0f411',
            'DEVELOPER_GUIDE.md':'cdd2b4f6cbc7eeca75ae6343f2bea6352d2c1aa4b30d16399c64bf3c60f51816',
        }
        for name,digest in expected.items():
            with self.subTest(name=name):
                canonical=(ROOT/name).read_text(encoding='utf-8').replace('\r\n','\n').encode('utf-8')
                self.assertEqual(digest,hashlib.sha256(canonical).hexdigest())
        self.assertTrue((ROOT/'ENRICHMENT_V040_GUIDE.md').is_file())

if __name__=='__main__':unittest.main()
