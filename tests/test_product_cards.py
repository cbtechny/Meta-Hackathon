"""Catalog presentation contracts; no network or credentials required."""
import tempfile
import unittest
from pathlib import Path
from counterpilot.catalog_io import (PART_COLUMNS, VERIFIED_COLUMNS, PRICE_COLUMNS, PART_TYPES,
    VEHICLE_COLUMNS, ALIAS_COLUMNS, read_sources, validate_rows, demo_price)
from counterpilot.domain import CATALOG, load_catalog
from scripts.generate_demo_catalog import csv_bytes


class ProductCardTests(unittest.TestCase):
    def test_every_sample_has_deterministic_price_and_registered_photo(self):
        for part in CATALOG['parts']:
            self.assertEqual(part['price']['amount'], demo_price(part['part_type'])['price_amount'])
            self.assertTrue(part['price']['is_sample'])
            self.assertEqual(part['price']['currency'], 'USD')
            self.assertTrue(part['image']['is_generic'])
        for kind in PART_TYPES:
            self.assertTrue((Path('counterpilot/static/parts') / (kind + '.jpg')).is_file(), kind)

    def test_invalid_prices_are_rejected(self):
        vehicles, parts, aliases, _ = read_sources()
        for changes in ({'price_amount': 'NaN'}, {'price_amount': 'Infinity'}, {'price_amount': '-1'},
                        {'price_amount': '0'}, {'price_amount': '1.005'}, {'price_amount': '1000000'},
                        {'currency': 'EUR'}, {'price_unit': ''}, {'price_amount': ''}):
            invalid = [{**parts[0], **changes}, *parts[1:]]
            self.assertTrue(any('price requires' in e for e in validate_rows(vehicles, invalid, aliases)), changes)

    def test_legacy_csv_and_verified_missing_price_never_inherit_demo(self):
        vehicles, parts, aliases, _ = read_sources()
        legacy = [{key: row[key] for key in PART_COLUMNS} for row in parts]
        verified = {**legacy[0], 'part_id': 'REAL-FIXTURE', 'part_number': '000001',
            'brand': 'Fixture', 'source': 'test fixture', 'data_status': 'verified',
            'source_reference': 'Test only', 'verification_date': '2026-11-03'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, columns, rows in [('vehicles.csv', VEHICLE_COLUMNS, vehicles), ('parts.csv', PART_COLUMNS, legacy),
                                       ('part_aliases.csv', ALIAS_COLUMNS, aliases), ('parts_verified.csv', VERIFIED_COLUMNS, [verified])]:
                (root / name).write_bytes(csv_bytes(columns, rows))
            catalog = load_catalog(root)
            self.assertTrue(all(p['price'] is None for p in catalog['parts']))
            real = next(p for p in catalog['parts'] if p['part_id'] == 'REAL-FIXTURE')
            self.assertEqual(real['part_number'], '000001')
            verified.update(price_amount='18.50', currency='USD', price_unit='each')
            (root / 'parts_verified.csv').write_bytes(csv_bytes(VERIFIED_COLUMNS, [verified]))
            real = next(p for p in load_catalog(root)['parts'] if p['part_id'] == 'REAL-FIXTURE')
            self.assertEqual(real['price'], {'amount': '18.50', 'currency': 'USD', 'unit': 'each', 'is_sample': False})


if __name__ == '__main__':
    unittest.main()
