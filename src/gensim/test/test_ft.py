import signal
import glob
import os
import time
from multiprocessing import Process
import unittest
from unittest import skip

try:
    import requests
except ImportError:
    requests = None

from gensim.test import settings
from gensim.server import app

TEST_FILES = settings.SAVES
TEST_DIR = settings.TEST_DIR

PORT = 14548
HOST = "localhost"
LIVE_TEST = os.environ.get(
    "GENSIM_LIVE_TEST", True
)  # Whether use an active test server (manual) or create one on-the-go (automatic)


def run_test_server():
    app.run(port=PORT, threaded=False)
    # clean up

    delete_test_data()


def delete_test_data():
    saves = glob.glob(str(TEST_FILES) + "/*.gsav")
    # we don't want anything funny to happen while removing files
    for s in saves:
        os.remove(s)


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert settings.DEBUG is True, "You can't test with production settings"
        if not LIVE_TEST:
            cls.server = Process(target=run_test_server)
            cls.server.start()

            _flag = False
            while not _flag:
                try:
                    time.sleep(0.2)
                    res = requests.get(f"http://{HOST}:{PORT}/api/game/")
                    _flag = res.ok
                except:
                    pass

            res = requests.post(
                f"http://{HOST}:{PORT}/api/game/", json={"name": "anon"}
            )

    @classmethod
    def tearDownClass(cls):
        if not LIVE_TEST:
            s = f"kill -s {signal.SIGINT.value} {cls.server.pid}"
            os.system(s)
            # cls.server.terminate()

    def setUp(self):

        assert requests, "Install requests"

        self.session = requests.Session()
        self.url = f"http://{HOST}:{PORT}/api/"

    def tearDown(self):
        delete_test_data()
        self.session.close()

    def test_newge(self):
        res = self.session.post(self.url + "game/", json={"name": "anon"})

        self.assertEqual(res.status_code, 200, res.text)

        self.assertEqual(len(os.listdir(TEST_FILES)), 1 + 1)

    def test_savege(self):
        self.test_newge()

        res = self.session.get(self.url + "game/save/" + "1")

        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(len(os.listdir(TEST_FILES)), 2 + 1)

    def test_loadge(self):
        self.test_savege()

        res = self.session.get(self.url + "game/load/" + "1")

        self.assertEqual(res.status_code, 200, res.text)

    def test_chattr(self):
        self.test_newge()

        res = self.session.get(self.url + "character/anon/")
        self.assertEqual(res.json()["name"], "anon")

    def test_trigger(self):
        kwargs = {"name": "name", "type_": "GLOBAL"}
        self.test_newge()

        res = self.session.post(self.url + "event", json=kwargs)
        self.assertEqual(res.status_code, 200, res.text)

        res = self.session.get(self.url + "event/" + str(res.json()["name"]))
        self.assertEqual(res.json()["name"], kwargs["name"])


def main_suite() -> unittest.TestSuite:
    s = unittest.TestSuite()
    load_from = unittest.defaultTestLoader.loadTestsFromTestCase
    s.addTests(load_from(TestServer))

    return s


def run():
    t = unittest.TextTestRunner()
    t.run(main_suite())


if __name__ == "__main__":
    run()
