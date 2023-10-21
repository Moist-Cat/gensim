import unittest
import unittest.mock
import time

from gensim.db import TERR_TYPE, create_db
from gensim.api import Client
from gensim import serializers
from gensim.test import ENGINE, settings

TEST_FILES = settings.SAVES
TEST_DIR = settings.TEST_DIR


class TestDB(unittest.TestCase):
    def setUp(self):
        self.client = Client(url=create_db(ENGINE))

    def tearDown(self):
        self.client.session.close()


class TestAPI(TestDB):
    def test_walk(self):
        area = self.client.create_area(name="SDM")
        _places = (
            "a",
            "b",
            "c",
            "d",
            #
            "e",
            "f",
            "g",
            "h",
            "i",
            "j",
        )
        places = [self.client.create_location(name=name, area=area) for name in _places]

        terr = ["URBAN", "FOREST", "RIVER"]
        dist = 10

        total = sum(map(lambda a: TERR_TYPE[a] * dist, terr))

        # aliases
        p = lambda o, d: {"origin": o, "destination": d, "distance": 10}
        cp = lambda o, d, terrain="URBAN": self.client.create_path(
            **p(o, d), terrain=terrain
        )

        cp("a", "b", terr[0])
        cp("b", "c", terr[1])
        cp("c", "d", terr[2])
        cp("a", "e")
        cp("e", "b")
        cp("f", "i")
        cp("i", "j")
        cp("i", "j")
        cp("f", "g")
        cp("g", "h")
        cp("h", "c")
        #  e - -
        #  |   |
        #  a - b - c - d
        #  |       |
        #  f - g - h
        #  |
        #  i
        #  |
        #  j

        # we set the cache
        # we could do this too to compute some paths eagerly
        # self.client.walk("c", "d")
        start = time.time()
        cost = self.client.walk(_places[0], _places[3])
        end = time.time() - start

        self.assertEqual(total, cost["time"])
        self.assertEqual(_places[1:4], cost["visited"])

        # walk is cached and optimized; I think it won't give us trouble for
        # a while
        #
        # $lscpu
        # i3
        # Thread(s) per core:  1
        # Core(s) per socket:  4
        # Socket(s):           1
        # Stepping:            1
        # CPU max MHz:         1800.0000
        # CPU min MHz:         1000.0000
        #
        # NOTE: formerly 0.05 -- fixed
        # NOTE: formerly 0.26 -- cached
        # NOTE: formerly 0.025 -- added more paths
        # NOTE: formerly 0.2 -- gave it some flexibility
        self.assertLess(end, 0.3)

    def test_event(self):
        area = self.client.create_area(name="SDM")
        event = self.client.create_event(name="Execution", type_="GLOBAL")
        assert event.available

        location = self.client.create_location(name="Hakurei Shrine")
        character = self.client.create_character(
            name="Yamato", energy=2000, location=location, home=area
        )

        stat = self.client.create_stat(character=character, label="alive", value=True)

        # the last field is the field=value
        # it makes more sense in the third
        effect = self.client.create_effect(
            event,
            stat,
            "value",
            change=-1,
            score=100,
        )
        effect.available_dialog.append(effect.dialog(text="...Execution"))

        self.assertEqual(effect.text, "...Execution")

        self.client.create_requirement(event, stat, "value", value=True)
        self.client.create_requirement(
            event, character, "location_name", value="Hakurei Shrine"
        )

        self.client.session.commit()
        assert event.available

        event.complete()
        assert not event.available

        effect = event.effects[0]
        effect.buffs.append(effect.buff(mod=10))

        event.complete()
        self.assertEqual(stat.value, -10)

        # omnipresent effect
        self.client.create_location(name="Nowhere")
        self.client.create_effect(
            event, character, "location_name", change="Nowhere", score=-1
        )
        event.complete()

        self.assertEqual(character.location.name, "Nowhere")

        lock = self.client.create_event(name="lock", type_="GLOBAL")

        event.locked_by.append(lock)

        del event.requirements[0]
        del event.requirements[0]

        assert not event.available


def override_make(model, fn=lambda args: None):
    """
    Helper method to mock Serializer.make
    (do not override the instance's method)
    """
    model.make = fn
    return model


class TestPopulate(TestDB):

    # all other models should "just werk"
    def test_characters(self):
        chara = override_make(serializers.GenericCharacter)
        chara.stats = []
        chara.character = "Hong"
        cinst = chara(None)
        # character is not a column of Character
        self.assertEqual({}, cinst._get_kw())
        chara.name = "Hong"
        cinst = chara(None)

        self.assertEqual({"name": "Hong"}, cinst._get_kw())

    def test_text_descriptor(self):
        desc = serializers.TextDescriptor

        class mock_dialog:

            player = "Anon"
            text = desc()
            _variables = ["player"]

        dinst = mock_dialog()
        dinst.text = "{player}"

        self.assertEqual("Anon", dinst.text)

    def test_generic_table(self):
        # sadly generic tables are a special case
        gen = serializers.GenericTableSerializer
        gen.columns = []
        gen.__init__ = lambda *args: None
        gen.event = "event"
        gen.target_property = "target_property"
        gen.target = "target"
        geninst = gen(None)

        self.assertEqual(
            {
                "event": "event",
                "target_property": "target_property",
                "target": "target",
            },
            geninst._get_kw(),
        )

    def test_child_event(self):
        mock_client = unittest.mock.Mock()

        class Child(serializers.GenericEvent):
            name = "child"

        class Parent(serializers.GenericEvent):
            name = "parent"
            children = [
                Child,
            ]

        par = Parent(mock_client)
        self.assertEqual(par.obj.children[0].name, "child")

    def test_cmd_map(self):
        cmd = self.client.create_command("fish")
        self.client.create_command_map("WATER", [cmd])

        self.assertEqual(cmd, self.client.get_command_map("WATER").one().commands[0])


def main_suite() -> unittest.TestSuite:
    s = unittest.TestSuite()
    load_from = unittest.defaultTestLoader.loadTestsFromTestCase
    s.addTests(load_from(TestAPI))
    s.addTests(load_from(TestPopulate))

    return s


def run():
    t = unittest.TextTestRunner()
    t.run(main_suite())


if __name__ == "__main__":
    run()
