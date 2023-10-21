"""
ORM layer for the DB
"""
import os
import random
import re
import logging
import pathlib
from warnings import warn
import shutil

from sqlalchemy import Column, create_engine
from sqlalchemy import (
    Integer,
    Float,
    String,
    Text,
    # DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, as_declarative
from sqlalchemy.schema import UniqueConstraint  # , CheckConstraint

from gensim.conf import settings
from gensim.log import logged

logger = logging.getLogger("user_info." + __name__)


@as_declarative()
class Base:
    """Automated table name, surrogate pk, and serializing"""

    @declared_attr
    def __tablename__(cls):  # pylint: --disable=no-self-argument
        cls_name = cls.__name__
        table_name = list(cls_name)
        for index, match in enumerate(re.finditer("[A-Z]", cls_name[1:])):
            table_name.insert(match.end() + index, "_")
        table_name = "".join(table_name).lower()
        return table_name

    def as_dict(self):
        return {
            column: getattr(self, column) for column in self.__table__.columns.keys()
        }

    def __str__(self):
        return f"[ {self.__class__.__name__} ] ({self.as_dict()})"

    def __repr__(self):
        return self.__str__()

    id = Column(Integer, primary_key=True, nullable=False)

class Has:
    """
    Geenric mixin for HasX classes

    https://github.com/zzzeek/sqlalchemy/blob/master/examples/generic_associations/table_per_related.py
    """

    def _related(cls, model):  # pylint: --disable=no-self-argument
        """
        You should make another method as a wraper for this one. Like an alias.
        """
        mname = model.__name__
        setattr(cls, mname.lower(), type(
            f"{cls.__name__}{mname.capitalize()}",
            (model, Base),
            dict(
                __tablename__=f"{cls.__tablename__}_{mname.lower()}",
                parent_id=Column(
                    Integer,
                    ForeignKey(f"{cls.__tablename__}.id"),
                    # this relationship causes trouble because sqlalch doesn't
                    # like when we make up our own names when it already
                    # made a relationship between tables
                    # so we just set the FK up there and call it a day
                    #
                    # parent=relationship(cls),
                ),
            ),
        ))  # pylint: --disable=attribute-defined-outside-init

        return relationship(getattr(cls, mname.lower()))



TERR_TYPE = {
    "RIVER": 5.0,
    "MOUNTAIN": 2.0,
    "FOREST": 3.0,
    "GRASSLANDS": 1.0,
    "URBAN": 0.7,
}


class Relationship(Base):
    from_ = Column(None, ForeignKey("character.name"), nullable=False)
    to = Column(None, ForeignKey("character.name"), nullable=False)
    strength = Column(Integer, nullable=False, default=0)


class EventLock(Base):
    """
    An events locks the activation of another, etc.
    """

    key = Column(None, ForeignKey("event.name", ondelete="CASCADE"))
    lock = Column(None, ForeignKey("event.name", ondelete="CASCADE"))


class Schedule(Base):
    """
    Types:

    YEARLY  - defines month, day, hour   ;
    MONTHLY - defines day, hour          ;
    WEEKLY  - day(s) of the week (0-6) M ; weekends,
    DAILY   - defines hour               ;

    XXX not required now but consider events scheduled to run every
    X days/hours/months

    Maybe adding them in side with a date should be fine
    UNIQUE if it's just at a specific date

    We need to use a mask to give the rest of the dates.
    ex.
    For a work day we would use a mask to get the year, month, and day;
    the hour and minute should be provided.
    MASK: 2022 12 31 0 0
    DATE: 0    0  0  6 30
    FINAL: 2022 12 31 6 30
    """

    event_name = Column(None, ForeignKey("event.name", ondelete="CASCADE"))
    event = relationship("Event", backref="due_date")
    type_ = Column(String, nullable=False, index=True)
    date = Column(Integer, nullable=False)
    duration = Column(Integer)


class Number(Base):
    """
    To provide indexes for dates so we don't have to
    scan the dates one by one.
    """

    number = Column(Integer)
    schedule_id = Column(None, ForeignKey("schedule.id"), nullable=False)
    schedule = relationship("Schedule", backref="date_indexes")


class Terrain(Base):

    type_ = Column(String, nullable=False, index=True)
    quality = Column(Float, nullable=False)


class Path(Base):

    origin = Column(None, ForeignKey("location.name"), nullable=False)

    destination = Column(None, ForeignKey("location.name"), nullable=False)

    distance = Column(Integer, nullable=False)

    terrain_type = Column(None, ForeignKey("terrain.type_"), nullable=False)
    terrain = relationship("Terrain", backref="paths")

    @property
    def seconds_taken(self):
        # rounded up
        return int(self.distance * self.terrain.quality)

    @property
    def energy_taken(self):
        # assuming 2K energy = 20KM
        return int((self.distance // 10) * self.terrain.quality)

    def traverse(self):
        return {
            "energy": self.energy_taken,
            "time": self.seconds_taken,
            "visited": (self.destination,),
        }


class Dialog:

    text = Column(Text, nullable=False)


class Area(Base):
    name = Column(String, nullable=False, index=True, unique=True)


class Tag:
    """
    Simple tags to keep track know if we should do X
    """
    name = Column(String, nullable=False)

class HasTag(Has):

    @declared_attr
    def tags(cls):
        return cls._related(cls, model=Tag)


class Location(Base, HasTag):

    name = Column(String, nullable=False, index=True, unique=True)
    area_name = Column(None, ForeignKey("area.name"), nullable=True)
    area = relationship("Area", backref="locations")
    paths = relationship(
        "Location",
        secondary="path",
        primaryjoin=name == Path.origin,
        secondaryjoin=name == Path.destination,
        backref="location",
    )

    def __str__(self):
        return f"[{self.__class__.__name__}] ({self.name} located in {self.area_name}) ({len(self.paths)} paths)"


class Character(Base):

    name = Column(String, nullable=False, index=True, unique=True)
    energy = Column(Integer, nullable=False)
    is_player = Column(Boolean, default=False)
    home_name = Column(None, ForeignKey("area.name"), nullable=False)
    home = relationship("Area")

    relation = relationship(
        "Character",
        secondary="relationship",
        primaryjoin=name == Relationship.from_,
        secondaryjoin=name == Relationship.to,
    )
    location_name = Column(None, ForeignKey("location.name"), nullable=False)
    location = relationship(Location, backref="characters")

    def __str__(self):
        return f"[{self.__class__.__name__}] ({self.name} resident of {self.home_name}) (Last seen at {self.location_name})"


@logged
class Event(Base):
    """The core of an event-driven game

    NOTE maybe we will want to make another table for type_ in the future

    :data children:
        an event triggers other, etc
        notice that this doesn't go in Effect because those are just for
        RNG-based stat changes, "crits" and whatnot.
        This is mostly to define a set of choices for an event.
        Notice that you trigger these on your own, they have a special type

        ex:
        Event_1... what do you do?
        [0] Event_1.1
        [1] Event_1.2

        All of these with their respective set of effects grouped by score; again, for RNG
        To add a subevent you can declare it as a standalone event
        and then add it to the serializers.GenericEvent.children array.

    The fact that an event is being executed is not defined by the DB
    we use cronie and scheduler objects handle execution times for events (including the duration)
    and set the necessary requirements.
    In case we decide to use the last method consider hashing.

    Notice that to manage time we do it via effects. We trigger the event, time changes,
    and we execute all the other events--checking the location to know if we should show the text or not.
    """

    name = Column(String, nullable=False, unique=True, index=True)
    # this is what should show up if it's a subevent and we need to show up choices
    verbose_name = Column(String, nullable=True)
    # this is to know WHEN should we try to trigger the event
    # ENCOUNTER events trigger when player_chara.location == other_chara.location
    # CHAT when we use the chat command
    # FLAVOR when we take an action and go back to the usual menu
    # [ ... ]
    type_ = Column(String, nullable=False, index=True)
    # to delete events that aren't going to be used again
    prune = Column(Boolean, default=False)
    # location where the event is active
    location_name = Column(None, ForeignKey("location.name"), nullable=True)
    location = relationship(Location, backref="active_events")

    character_name = Column(None, ForeignKey("character.name"), nullable=True)
    character = relationship("Character", backref="events")

    # locks
    locks = relationship(
        "Event",
        secondary="event_lock",
        primaryjoin=name == EventLock.key,
        secondaryjoin=name == EventLock.lock,
        backref="locked_by",
    )

    @property
    def requirements(self):
        # XXX pattern matching bullshit
        full_requirements = []
        for attr in self.__dir__():  # pylint: --disable=unnecessary-dunder-call
            if attr.endswith("_requirement"):
                full_requirements.extend(getattr(self, attr))
        return full_requirements

    @property
    def effects(self):
        # XXX 2/3 three strikes and you are out
        all_effects = []
        for attr in self.__dir__():  # pylint: --disable=unnecessary-dunder-call
            if attr.endswith("_effect"):
                all_effects.extend(getattr(self, attr))
        return all_effects

    @property
    def score(self):
        """Choose an appropriate score for the event"""
        # notice the singular
        volatile_effects = list(filter(lambda f: f.score != -1, self.effects))
        try:
            return random.choices(
                volatile_effects,
                weights=map(lambda e: e.score, volatile_effects),
                k=1,
            )[0].score
        except IndexError:
            self.logger.warning("No effects set for %s", self)
        return -1

    def complete(self):
        """Commit stat changes after the event"""
        score = self.score  # we only do it once, of course
        self.logger.info("Event %s marked as complete. Committing effects", self.name)

        return [
            effect.commit() for effect in self.effects if effect.score in (score, -1)
        ]

    @property
    def available(self):
        # we define __bool__ in Event
        # so don't use "if self.activator"
        if self.activator is not None:
            return self.activator.available
        if any(self.locked_by):
            return False
        return all((requirement.fulfilled for requirement in self.requirements))

    def __str__(self):
        return (
            f"[{self.__class__.__name__}] "
            f"({self.name}, available: {'YES' if self.available else 'NO'}, "
            f"{len(self.requirements)} requirements and {len(self.effects)} "
            "effects)"
        )

    def __bool__(self):
        return self.available

    def as_dict(self):
        base = super().as_dict()
        base["children"] = self.children

        return base


# monkey-patched since it's self-referential
# The event name is specially important here since we
# will use it as the text of the option
# im not making another table
Event.parent_name = Column(None, ForeignKey(Event.name, ondelete="CASCADE"))
Event.parent = relationship(
    Event, backref="children", remote_side=Event.name, foreign_keys=[Event.parent_name]
)
# events are triggered in series. This is the equivalent of multiple events having
# the same requirements. Not to be mistaken with child events
Event.activator_name = Column(None, ForeignKey(Event.name, ondelete="CASCADE"))
Event.activator = relationship(
    Event,
    backref="activates",
    remote_side=Event.name,
    foreign_keys=[Event.activator_name],
)

class Buff:

    mod = Column(Float, nullable=False)

    @property
    def available(self):
        return all((requirement.fulfilled for requirement in self.requirements))

    @property
    def requirements(self):
        # XXX pattern matching bullshit
        full_requirements = []
        for attr in self.__dir__():  # pylint: --disable=unnecessary-dunder-call
            if attr.endswith("_requirement"):
                full_requirements.extend(getattr(self, attr))
        return full_requirements

    def __str__(self):
        return (
            f"[{self.__class__.__name__}] "
            f"(available: {'YES' if self.available else 'NO'}, "
            f"{self.mod} modification, {len(self.requirements)} requirements)"
        )



class HasBuff(Has):
    """
    HasBuff mixin, creates a new Buff class
    for each parent.

    """

    @declared_attr
    def buffs(cls):
        return cls._related(cls, model=Buff)


class HasDialog(Has):
    """HasDialog mixin, creates a new Dialog class
    for each parent.
    """

    @declared_attr
    def available_dialog(cls):
        return cls._related(cls, model=Dialog)


# XXX move this up there if needed
CAN_BE_REQUIRED: dict = {
    "Character": ["location_name", "energy"],
    "Relationship": ["strength"],
    "Stat": ["value"],
}

CAN_BE_AFFECTED = CAN_BE_REQUIRED.copy()
CAN_BE_AFFECTED.update({})

CAN_BE_BUFF_REQ = CAN_BE_REQUIRED.copy()
CAN_BE_BUFF_REQ.update({})
# There is no God here. Just me.
class Requirement(HasBuff):

    value = Column(String, nullable=False)

    @property
    def fulfilled(self):
        tp = getattr(self.target, self.target_property)
        if (
            isinstance(self.value, int)
            or self.value.isnumeric()
            or self.value.startswith("-")
        ):
            val = int(self.value)
            tp = int(tp)
            if val >= 0:
                return tp >= val
            val = abs(val)
            return tp < val
        return tp == self.value


@logged
class Effect(HasBuff, HasDialog):

    # an effect can be affecting the global state (global.time)
    change = Column(String, nullable=False)
    # weights for random
    # higher score means higher probability
    score = Column(Integer, default=100, nullable=False, index=True)

    @property
    def text(self):
        if not self.available_dialog:
            return ""
        return random.choice(self.available_dialog).text

    def commit(self):
        attr = getattr(self.target, self.target_property)
        new_value = self.change
        if isinstance(attr, int) or attr.isnumeric():
            new_value = int(new_value)
            attr = int(attr)
            # buff/debuffs
            for buff in self.buffs:
                # I can't fathom why would someone would want to
                # add/substract here
                if buff.available:
                    new_value *= buff.mod
            new_value = new_value + attr
        setattr(self.target, self.target_property, new_value)

        self.logger.info(
            "Changing %s.%s to %s", self.target, self.target_property, new_value
        )
        self.logger.debug("Text: %s", self.text)
        return {
            "target": self.target.__class__.__name__,
            "property": self.target_property,
            "new_value": new_value,
            "text": self.text,
        }


def make_generic_table(main_fk, mixin, specs):
    """
    Create a set of tables with a set of foreign keys pointing to
    several models that can be reverse-acessed by Event
    :param main_fk: Parent table
    :param mixin: A mixin declaring all the other columns
    :param specs: The other foreign keys.
    """
    name = mixin.__name__
    classes = {}
    for type_, ppts in specs.items():
        for ppt in ppts:
            cls_name = (
                type_ + ppt.capitalize().replace("_", "") + main_fk.__name__ + name
            )
            table_name = list(cls_name)
            for index, match in enumerate(re.finditer("[A-Z]", cls_name[1:])):
                table_name.insert(match.end() + index, "_")
            table_name = "".join(table_name).lower()
            classes[cls_name] = globals()[cls_name] = type(
                cls_name,
                (
                    Base,
                    mixin,
                ),
                dict(
                    event_id=Column(
                        None,
                        ForeignKey(f"{main_fk.__tablename__}.id"),
                        nullable=False,
                    ),
                    event=relationship(main_fk, backref=table_name),
                    target_property=Column(
                        None, ForeignKey(f"{type_.lower()}.{ppt}"), nullable=False
                    ),
                    target_id=Column(
                        None,
                        ForeignKey(f"{type_.lower()}.id"),
                        nullable=False,
                    ),
                    target=relationship(
                        type_, primaryjoin=f"{table_name}.c.target_id=={type_}.id"
                    ),
                ),
            )
    return classes


REQUIREMENT_CLASSES = make_generic_table(
    Event,
    Requirement,
    CAN_BE_REQUIRED,
)
EFFECT_CLASSES = make_generic_table(
    Event,
    Effect,
    CAN_BE_AFFECTED,
)

GENERIC_CLASSES = REQUIREMENT_CLASSES.copy()
GENERIC_CLASSES.update(EFFECT_CLASSES)
# RelationshipStrengthRelationshipStrengthEventEffectBuffRequirement (prel buff requirement for a prel event effect)
GENERIC_CLASSES.update(
    make_generic_table(
        GENERIC_CLASSES["RelationshipStrengthEventEffect"].buff,
        Requirement,
        {"Relationship": ["strength"]},
    )
)
# NOTE no need to do this for now
#
# for name, cls in req.items():
#    # all of these have buffs...
#    GENERIC_CLASSES.update(
#        make_generic_table(cls.buff, Requirement, CAN_BE_REQUIRED)  # CAN_BE_BUFF_REQ
#    )


class Stat(Base):

    label = Column(String)
    verbose_name = Column(String)
    chara_name = Column(None, ForeignKey("character.name"), nullable=False, index=True)
    character = relationship("Character", backref="stats")

    value = Column(Integer, default=0)

    # avoid repeated stats
    __table_args__ = (UniqueConstraint("label", "chara_name"),)


class Calendar(Base):

    calendar = Column(String, nullable=False)

class Command(Base):

    cmd = relationship("CommandMap", backref="commands")
    cmd_id = Column(None, ForeignKey("command_map.id"), nullable=False)
    name = Column(String, nullable=False)

class CommandMap(Base):
    key = Column(String, nullable=False)

def create_db(name=settings.DATABASES["default"]["engine"]):
    """
    Create database and schema if and only if the schema was modified
    """
    file = name.split("/")[-1]
    master = "master_" + file
    master_name = name.replace(file, master)

    path = name.split("///")[-1].replace("(", "")
    master_path = pathlib.Path(path.replace(file, master))
    child_path = pathlib.Path(path)

    # Nuke everything and build it from scratch.
    if db_schema_modified("db.py") or not master_path.exists():
        master_engine = create_engine(master_name)
        Base.metadata.drop_all(master_engine)
        Base.metadata.create_all(master_engine)

    shutil.copy(master_path, child_path)
    print(child_path)

    engine = create_engine(name)

    return str(engine.url)


def drop_db(name=settings.DATABASES["default"]["engine"]):
    engine = create_engine(name)
    Base.metadata.drop_all(engine)


def db_schema_modified(filename):
    """
    Utility tool to know if a file was modified.
    :param file: Path object, file to watch
    """
    ts_file = settings.BASE_DIR / f"_last_mod_{filename}.timestamp"
    _last_schema_mod = os.stat(settings.BASE_DIR / filename).st_mtime
    try:
        with open(ts_file, encoding="utf-8") as file:
            _lst_reg_schema_mod = file.read()
    except FileNotFoundError as exc:
        _, error = exc.args
        warn(error)
        with open(ts_file, "w", encoding="utf-8") as file:
            file.write(str(_last_schema_mod))
            _lst_reg_schema_mod = 0

    SCHEMA_MODIFIED = float(_lst_reg_schema_mod) != _last_schema_mod
    if SCHEMA_MODIFIED:
        logger.info("Detected change in %s ... db will be rebuilt", filename)
        with open(ts_file, "w", encoding="utf-8") as file:
            file.write(str(_last_schema_mod))

    return SCHEMA_MODIFIED
