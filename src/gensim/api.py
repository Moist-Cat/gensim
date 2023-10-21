"""API"""
import base64
from datetime import datetime
from functools import wraps, lru_cache
import inspect
import logging
import pathlib
import pickle
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gensim.conf import settings
from gensim.db import (
    TERR_TYPE,
    GENERIC_CLASSES,
    Base,
    Calendar,
    Character,
    Event,
    Terrain,
    Path,
    Schedule,
    Number,
    Location,
    Stat,
    Area,
    Relationship,
    Dialog,
    Buff,
    Command,
    CommandMap,
)
from gensim.log import logged

log = logging.getLogger("global")

DB = settings.DATABASES["default"]
URL = DB["engine"]
# cache kwargs
CACHE = {}


def benchmark(method):
    @wraps(method)
    def wrapper(*args, **kwargs):
        start = time.time()

        result = method(*args, **kwargs)

        end = time.time() - start
        log.info("benchmarked method %s %s", method.__name__, end)
        return result

    return wrapper


def loggedmethod(method):
    """
    Log a CRUD method and confirm its successful execution
    version: 1.0.1
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        method_data = inspect.getfullargspec(method)
        mname = method.__name__.lstrip("_")  # ignore encapsulation
        method_type = mname.split("_")[0].upper()
        # + 1 because of self
        try:
            self.logger.info(
                "_%s_ %s %s",
                method_type,
                [
                    f"{method_data.args[index + 1]}={value}"
                    for index, value in enumerate(args)
                ],
                kwargs,
            )
        except IndexError as exc:
            raise IndexError(
                f"Too many arguments for {mname}. Maybe you used positional arguments intead of key-value arguments?"
            )

        res = method(self, *args, **kwargs)

        self.logger.debug("_%s_ --success--", method_type)
        return res

    return wrapper


# XXX CAUTION CAUTION XXX
# wrappers for the effect and requirement generic tables
def _get_buff_table(cls):
    return cls + "Buff"


def _get_generic_table(cls_name, event, target, target_property):
    assert not isinstance(
        target, str
    ), f"You are passing a string as the target. Pass the class instead. ({target} is a string)"
    # we specify __bool__ in event :^)
    assert target and event is not None and cls_name, (target, event, cls_name)
    assert (
        target.__class__.__name__ != "Query"
    ), f"You are passing a as the target, you must supply an ORM object instead. (hint: add '.one()' to your query). {target}"
    qualname = (
        target.__class__.__name__
        + target_property.capitalize().replace("_", "")
        + event.__class__.__name__
        + cls_name
    )
    cls = GENERIC_CLASSES[qualname]

    return cls


@logged
class Client:
    def __init__(self, url=URL, config=None):
        config = config or {}
        self.logger.info("Started %s. Engine: %s", self.__class__.__name__, URL)

        db_file = pathlib.Path(url.split("///")[-1])
        assert db_file.exists(), f"DB file doesn't exist! {db_file}"
        assert db_file.stat().st_size > 0, "DB file is just an empty file!"

        engine = create_engine(url, isolation_level="AUTOCOMMIT")
        Session = sessionmaker(bind=engine, **config)  # pylint: --disable=C0103
        self.session = Session()

    def __delete__(self, obj):
        self.session.close()

    # low level
    @loggedmethod
    def _get(self, Obj, /, **kwargs):
        """Low level GET implementation"""
        query = self.session.query(Obj)
        for k, v in kwargs.items():
            query = query.filter(getattr(Obj, k) == v)

        return query

    @loggedmethod
    def _create(self, Obj, /, **kwargs):
        """Low level insert implementation"""
        obj = Obj(**kwargs)
        self.session.add(obj)
        # self.session.commit()

        return obj

    @loggedmethod
    def update(self, obj, /, **kwargs):
        """Update implementation. Feel free to use this directly"""

        if isinstance(obj, Base):
            for k, v in kwargs.items():
                setattr(obj, k, v)
            # self.session.add(obj)
            # self.session.commit()
        elif getattr(obj, "__name__"):
            # model class
            query = self.session.query(obj)
            obj = query.update(**kwargs).one()
        else:
            raise AssertionError(f"{obj} is not update-able")

        return obj

    def _get_or_create(self, Obj, /, **kwargs):
        """Low level select or insert  implementation"""
        obj = self._get(Obj, **kwargs).all()
        if not obj:
            return self._create(Obj, **kwargs)
        obj = obj[0]
        return obj

    def create_location(self, /, **kwargs):
        return self._create(Location, **kwargs)

    def get_location(self, /, **kwargs):
        return self._get(Location, **kwargs)

    def create_area(self, /, **kwargs):
        return self._create(Area, **kwargs)

    def get_area(self, /, **kwargs):
        return self._get(Area, **kwargs)

    # crud api
    # path
    def get_path(self, /, **kwargs):
        kwargs = self._get_name(kwargs, "origin", "destination")
        p = self._get(Path, **kwargs)
        kwargs = self._switch(kwargs, "origin", "destination")

        p = p.union(self._get(Path, **kwargs))
        return p

    def create_path(self, /, **kwargs):
        terrain_type = kwargs.get("terrain", "URBAN")
        terrain = self._get_or_create(
            Terrain, type_=terrain_type, quality=TERR_TYPE[terrain_type]
        )
        kwargs["terrain"] = terrain

        if not isinstance(kwargs["origin"], str):
            kwargs = self._get_name(kwargs, "origin", "destination")

        return self._create(Path, **kwargs)

    # event
    def create_event(self, /, **kwargs):
        return self._create(Event, **kwargs)

    def get_event(self, /, **kwargs):
        return self._get(Event, **kwargs)

    def get_events(self, ids):
        if any(ids):
            return self.session.query(Event).filter(Event.id.in_(ids)).all()
        return []

    # character
    def create_character(self, /, **kwargs):
        return self._create(Character, **kwargs)

    def get_character(self, /, **kwargs):
        return self._get(Character, **kwargs)

    def get_player(self):
        return self._get(Character, is_player=True)

    # stat
    def create_stat(self, /, **kwargs):
        return self._create(Stat, **kwargs)

    def get_stat(self, /, **kwargs):
        return self._get(Stat, **kwargs)

    def get_global(self, /, **kwargs):
        return self._get(Stat, chara_name="Alice Liddell", **kwargs)

    # relationship
    @staticmethod
    def _get_name(kw, *args):
        for arg in args:
            if arg in kw and isinstance(kw[arg], Base):
                kw[arg] = kw[arg].name
        return kw

    @staticmethod
    def _switch(kw, a="from_", b="to"):
        if a in kw and b in kw:
            if a in kw:
                temp = kw[a]
            if b in kw:
                kw[a] = kw[b]
            if a in kw:
                kw[b] = temp
        elif a in kw:
            kw[b] = kw[a]
            del kw[a]
        elif b in kw:
            kw[a] = kw[b]
            del kw[b]
        return kw

    def create_relationship(self, /, **kwargs):
        return self._create(Relationship, **kwargs)

    def get_relationship(self, /, **kwargs):
        kwargs = self._get_name(kwargs, "from_", "to")
        r = self._get(Relationship, **kwargs)
        kwargs = self._switch(kwargs, "from_", "to")

        r = r.union(self._get(Relationship, **kwargs))
        return r

    # text
    def create_dialog(self, /, **kwargs):
        return self._create(Dialog, **kwargs)

    def get_dialog(self, /, **kwargs):
        return self._get(Dialog, **kwargs)

    def create_buff(self, /, **kwargs):
        return self._create(Buff, **kwargs)

    def create_effect(self, event, target, target_property, /, **kwargs):
        Effect = _get_generic_table("Effect", event, target, target_property)
        effect = self._create(
            Effect,
            event=event,
            target=target,
            target_property=target_property,
            **kwargs,
        )
        return effect

    def get_requirement(self, event, target, target_property, /, **kwargs):
        Requirement = _get_generic_table("Requirement", event, target, target_property)
        requirement = self._get(
            Requirement,
            event=event,
            target=target,
            target_property=target_property,
            **kwargs,
        )
        return requirement

    def create_requirement(self, event, target, target_property, /, **kwargs):
        Requirement = _get_generic_table("Requirement", event, target, target_property)
        requirement = self._create(
            Requirement,
            event=event,
            target=target,
            target_property=target_property,
            **kwargs,
        )
        return requirement

    def get_date_requirement(self, event, /, **kwargs):
        time_stat = self.get_global(label="time").one()
        return self.get_requirement(event, time_stat, "value", **kwargs)

    def create_date_requirement(self, event, /, **kwargs):
        time_stat = self.get_global(label="time").one()
        return self.create_requirement(event, time_stat, "value", **kwargs)

    def flush_date_requirements(self, event):
        reqs = self.get_date_requirement(event).all()
        for req in reqs:
            self.session.delete(req)

    @lru_cache(maxsize=10000)
    @benchmark
    @loggedmethod
    def walk(self, origin, destination, visited=None, time=0, energy=0):
        """
        version: 2.0
        """
        visited = visited or ()
        paths = self.get_path(origin=origin)

        reserve = []
        for path in paths:
            cost = path.traverse()
            location = path.destination if path.destination != origin else path.origin
            if location in visited:
                self.logger.warning("Already visited %s", location)
                continue

            nu_time = time + cost["time"]
            nu_energy = energy + cost["energy"]

            if location == destination:
                self.logger.info("Found path %s -> %s", visited, destination)
                return {
                    "time": nu_time,
                    "energy": nu_energy,
                    "visited": visited + cost["visited"],
                }

            reserve.append(
                (
                    (
                        location,
                        destination,
                    ),
                    {
                        "time": nu_time,
                        "energy": nu_energy,
                        "visited": visited + cost["visited"],
                    },
                )
            )
        shortest = {"time": 9999}
        for args, kwargs in reserve:
            c = self.walk(*args, **kwargs)
            if c and c["time"] < shortest["time"]:
                shortest = c
        return shortest

    def get_time(self):
        """
        Year, Month, Day, Hour, Minute
        """
        return datetime.fromtimestamp(self.get_global(label="time").one().value)

    def get_schedule(self, /, **kwargs):
        return self._get(Schedule, **kwargs)

    @loggedmethod
    def get_today_schedule(self, today):
        """
        Not messing around with APIs this method just gives today's schedule
        """
        daily = self.session.query(Schedule).filter(Schedule.type_ == "DAILY")
        weekly = (
            self.session.query(Schedule)
            .filter(Schedule.type_ == "WEEKLY")
            .join(Number, Number.number == today.weekday())
        )
        monthly = (
            self.session.query(Schedule)
            .filter(Schedule.type_ == "MONTHLY")
            .join(Number, Number.number == today.day)
        )
        yearly = (
            self.session.query(Schedule)
            .filter(Schedule.type_ == "MONTHLY")
            .join(Number, Number.number == today.month)
        )
        # unique = (
        #    self.session.query(Schedule)
        #    .filter(Schedule.type_ == "UNIQUE", Schedule.date == today)
        # )

        return yearly.union(monthly).union(weekly).union(daily).all()

    def create_calendar(self, calendar):
        obj = self._create(Calendar, calendar=base64.b64encode(pickle.dumps(calendar)))

        return obj

    def get_calendar(self):
        obj = self._get(Calendar).one()

        return pickle.loads(base64.b64decode(obj.calendar))

    def update_calendar(self, calendar):
        obj = self._get(Calendar).one()

        self.update(obj, calendar=base64.b64encode(pickle.dumps(calendar)))
        # obj.calendar = base64.b64encode(pickle.dumps(calendar))

        # self.session.add(obj)
        # self.session.commit()

    # cmd
    def create_command(self, name):
        return self._create(Command, name=name)

    def get_command(self, name):
        return self._get(Command, name=name)

    def create_command_map(self, key, cmds=None):
        cmds = cmds or []
        obj = self._create(CommandMap, key=key.upper())
        obj.commands = cmds

        return obj

    def get_command_map(self, key):
        return self._get(CommandMap, key=key.upper())
