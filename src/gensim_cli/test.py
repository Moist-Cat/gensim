import unittest

from client.client import Client
from client import settings

"""
class ClientTest(unittest.TestCase):
    def setUp(self):
        self.session = Client()
        self.shelve_pl = settings.SHELVE_PAYLOAD
        self.product_pl = settings.PRODUCT_PAYLOAD
        self.for_sale = settings.FOR_SALE
        self.out_of_stock = settings.OUT_OF_STOCK
        res = self.session.store.shelve.list()
        for sh in res:
            self.session.store.shelve.delete(sh["id"])

    def tearDown(self):
        self.session.close()
        res = self.session.store.shelve.list()
        for sh in res:
            self.session.store.shelve.delete(sh["id"])

    def test_main(self):
        res = self.session.store.shelve.list()
        self.assertEqual(res, [])

        shelve_pl = self.shelve_pl
        shelve_pl.update({"classification": "k-32", "area": "a-12", "manager": "dummy"})
        res = self.session.store.shelve.create(shelve_pl)
        del res["date_created"]
        id = res.pop("id")
        self.assertEqual(res, shelve_pl)

        res = self.session.store.shelve.get(id)
        del res["id"]
        del res["date_created"]
        self.assertEqual(res, shelve_pl)

        shelve_pl.update({"classification": "k-31"})
        res = self.session.store.shelve.update(id, shelve_pl)
        del res["id"]
        del res["date_created"]
        self.assertEqual(res, shelve_pl)

        self.session.store.shelve.delete(id)
        res = self.session.store.shelve.list()
        self.assertEqual(res, [])
"""

if __name__ == "__main__":
    unittest.main()
