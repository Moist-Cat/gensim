import logging
from functools import wraps
from glob import glob
from pathlib import Path
import time
import shutil

try:
    import yaml
except ImportError:
    yaml = None

from gensim.data import models, events
from gensim.data.player import make_player
from gensim.api import Client
from gensim.db import (
    create_db,
    Area,
    Location,
    Event,
    db_schema_modified,
    EFFECT_CLASSES,
)
from gensim.conf import settings


ENGINE = settings.DATABASES["default"]["engine"]
SAVES = settings.SAVES
DB_FILE = Path(ENGINE.split("///")[1])

logger = logging.getLogger("user_info." + __name__)
logger.info("Engine: %s. Saves: %s. DB file: %s", ENGINE, SAVES, DB_FILE)


def yml_data(yfile):
    def inner(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with open(settings.DATA_DIR / yfile, encoding="utf8") as file:
                data = yaml.safe_load(file)
            return func(data, *args, **kwargs)

        return wrapper

    return inner


def _areas(c, names, **kwargs):
    return (c._get_or_create(Area, name=name) for name in names)


def _events(c, names, **kwargs):
    return (c._get_or_create(Event, name=name) for name in names)


def _locations(c, names, **kwargs):
    for _, v in kwargs.items():
        if isinstance(v, Area):
            area = v
    return (c._get_or_create(Location, name=name, area=area) for name in names)


def _setup_declarative(c, module):
    for cls in module.__dir__():
        if cls.startswith("_"):
            continue
        cls = getattr(module, cls)
        if "_is_data" in cls.__dict__.keys() and cls._is_data:
            cls(c)
            print("Created " + cls.name)
            # murder it afterwards since we create a shitton of objects
            del cls


def setup_characters(c):
    _setup_declarative(c, models)


def setup_player(c, **kwargs):
    make_player(c, **kwargs)


def setup_events(c):
    _setup_declarative(c, events)


def _inerit_terrain(data, current):
    return data.pop("terrain") if "terrain" in data else current


def _rec_search(c, data, functions, inerit=None, inerited=None, prev=None):
    """
    Recursive search algo to get all the params we need along the way from a dict. Supports
    ineriting params from parents and overriding them with their own.
    :param data: Dict
    :param functions: List[Callable]
        Will be passed to the dict keys to make the object.
    :param inerit: Dict[String, Callable]
        Dict with name and function to override the key from the parent if the children defines it.
        To support generalized params for a set of objects that have a model in common.
        # name:
            terrain: 1
            name:
                terrain: 2
    :param inerited:
        Params already inerited from upper levels
    :param objects: Dict[name, MappedClass]
        Dict of objects that will be returned
    :param prev: previous objects. required by children
    :return: Tuple[Dict, Dict, Dict]
    """
    inerited = inerited or {}
    inerit = inerit or {}
    prev = prev or {}
    param = next(iter(functions.keys()))
    function = functions.pop(param)

    logger.debug("Aquiring param '%s' from yaml file", param)

    logger.debug("Current paramers (parents) %s", prev)
    results = []
    for obj in function(c, data.keys(), **prev):
        prev[param] = obj
        new = data[obj.name]
        for inr_param, inr_fun in inerit.items():
            curr = new.get(inr_param, None)
            _res = inr_fun(new, curr)
            # remember the key is XXX PRUNED XXX after ineritance to avoid duplication
            # if the last child defines his own param
            if _res:
                logger.debug("Inerited %s from %s key", inr_param, param)
                inerited[inr_param] = _res
        if functions:
            logger.debug("Thinking recursively...")
            # we overwrite our data with the kwargs from the child
            results.extend(
                _rec_search(c, new, functions.copy(), inerit, inerited, prev)
            )
            # prev.update(parent_kw)
            # iparams.update(inrt)
        else:
            logger.info(
                "Reached the end of the tree. Coming back with data "
                "(kwargs=%s, parent_kw=%s, inerited_kw=%s)",
                new,
                prev,
                inerited,
            )
            results.append((new.copy(), prev.copy(), inerited.copy()))
    return results


@yml_data("paths.yaml")
def setup_paths(data, c):
    # for kwargs, objects, inerited in _rec_search(
    results = _rec_search(
        c,
        data,
        {"area": _areas, "origin": _locations, "destination": _locations},
        {"terrain": _inerit_terrain},
    )
    for kwargs, parent_kw, inerited_kw in results:
        if "area" in parent_kw:
            del parent_kw["area"]
        c.create_path(**kwargs, **parent_kw, **inerited_kw)


@yml_data("relationships.yaml")
def setup_relationships(data, c):
    all_charas = c.get_character()

    already = []
    for chara in data.keys():
        already.append(chara)
        names = []
        for name, strength in data[chara].items():
            c.create_relationship(from_=chara, to=name, strength=strength)
            logger.info(f"Created relationship: %s -> %s", chara, name)
            names.append(name)
        # initialize relationship
        for not_rel in all_charas:
            if not_rel.name not in names and not not_rel.name in already:
                c.create_relationship(from_=chara, to=not_rel.name)
                logger.debug(f"Init relationship %s -> %s", chara, not_rel.name)

    orphaned = list(set(map(lambda c: c.name, all_charas)).difference(set(already)))
    for index, ch_a in enumerate(orphaned):
        for ch_b in orphaned[index:]:
            if ch_a != ch_b:
                c.create_relationship(from_=ch_a, to=ch_b)
                logger.debug(f"Init relationship %s -> %s", ch_a, ch_b)


@yml_data("globals.yaml")
def setup_globals(data, c):
    """
    time, flags and commands
    """
    # to make global stat management easier
    home = c.create_area(name="Wonderland")
    location = c.create_location(name="Dream Library", area=home)
    alice = c.create_character(
        name="Alice Liddell", home=home, energy=9999, location=location
    )
    for label, value in data.items():
        c.create_stat(label=label, value=value, character=alice)

    # cmds
    game = [c.create_command("chat"), c.create_command("move")]
    c.create_command_map("game", game)

    fish = [c.create_command("fish")]
    # h20-based terrain
    c.create_command_map("water", fish)

    cook = [c.create_command("cook")]
    c.create_command_map("kitchen", cook)


def grep_dialog(client, old_name, new_name):
    # O(n^3)
    for cls in EFFECT_CLASSES.values():
        for effect in client._get(cls).all():
            for dialog in effect.available_dialog:
                dialog.text = dialog.text.replace(old_name, new_name)


def setup_database(**kwargs):
    """
    Wraps the functions that create every single object required to start a gaem.
    The order of execution is important.
    """
    assert yaml, "Can't create a new database without pyaml installed"
    player_name = kwargs["name"]
    if DB_FILE.exists():
        # if any file in the data directory has beed modified
        # then we see if it is the same player as before
        # this speeds up testing a lot
        if (
            not db_schema_modified("data")
            and not db_schema_modified("db.py")
            and not db_schema_modified("serializers.py")
        ):
            ccheck = Client(url=ENGINE)
            p = ccheck.get_player()
            if len(p.all()) == 1:
                player_obj = p.one()
                if player_obj.name == player_name:
                    # nothing to do here
                    logger.info(
                        "DB has not changed since last time it has built,"
                        "the data havent changed either and the player is the"
                        "same (%s)... nothing to do",
                        player_name,
                    )
                else:
                    # not the same name, we change it
                    grep_dialog(ccheck, player_obj.name, player_name)
                    ccheck.update(player_obj, name=player_name)

                    ccheck.session.commit()
                    logger.info(
                        "DB has not changed since last time it has built,"
                        "the data havent changed either. We only changed the name of"
                        "the player (and all references to him) to %s",
                        player_name,
                    )
                return
        logger.warning("db file exists. moving it")
        shutil.move(DB_FILE, DB_FILE.parent / "db-bk.sqlite3")
    create_db(ENGINE)
    c = Client(url=ENGINE)

    # timer
    start = time.time()

    # First, we create God and Law
    setup_globals(c)
    logger.info("########## Created globals ##########")

    # Then create the world
    setup_paths(c)
    logger.info("######### Created paths #########")

    # We create the player and give him a home after the
    # world is created
    player = c.get_character(name=player_name).all()
    if not player:
        setup_player(c, **kwargs)
    else:
        player = player[0]
    logger.info("######### Created player #########")

    # We populate the world
    setup_characters(c)
    logger.info("########## Created characters ##########")

    # We define the relationships among characters
    setup_relationships(c)
    logger.info("########## Created relationships ##########")

    # We create a script
    setup_events(c)
    logger.info("########## Created events ##########")

    logger.info("DB populated in %d seconds", time.time() - start)


def get_save(num="current"):
    assert DB_FILE.exists(), f"main db file {DB_FILE} doesn't exist"
    url = settings.DATABASES["play"]["engine"].format(num=num)
    save_file = Path(url.split("///")[1])
    return "sqlite:///" + str(save_file)


def total_saves():
    return len(glob(str(SAVES / "*.gsav")))


def new_game(**kwargs):
    logger.info("Setting up new game")

    setup_database(**kwargs)
    shutil.copy(DB_FILE, get_save("current").split("///")[-1])


def load_game(num):
    logger.info("Loading game #%d", num)

    save_file = get_save(num)
    shutil.copy(save_file.split("///")[-1], get_save().split("///")[-1])


def save_game(num):
    logger.info("Saving game #%d", num)

    save_file = Path(get_save(num).split("///")[-1])
    if save_file.exists():
        logger.warning("Save file %s exists. Replacing...", save_file)
    shutil.copy(get_save().split("///")[-1], save_file)
