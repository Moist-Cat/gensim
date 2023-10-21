"""
Serializers for creating populated data models declaratively. (Using Python classes to
put data in the DB)
"""
from logging import getLogger

# from functools import lru_cache
from uuid import uuid4

from gensim.db import (
    # Terrain,
    Path,
    Event,
    Character,
    Location,
    Number,
    Area,
    #    Relationship,
    EventLock,
    Effect,
    Requirement,
    Schedule,
    Stat,
)
from gensim import api
from gensim.conf import settings
from gensim.cronie import from_date
from gensim.log import logged

DATA_DIR = settings.BASE_DIR / "data"

logger = getLogger("user-info." + __name__)


#
@logged
class TextDescriptor:
    """
    Replaces text {between braces} with a variable with str.format
    The value is an attribute or property of the class with the same name as
    the values of the list
    """

    _text = ""

    def __get__(self, instance, owner=None):
        return self._text

    def __set__(self, instance, value):
        self._text = value
        try:
            var_dict = {var: getattr(instance, var) for var in instance._variables}
        except KeyError as exc:
            self.logger.error("Unable to parse text for %s. %s", instance._effect, exc)
        self._text = self._text.format(**var_dict).strip()


#
class Serializer:
    """
    Serializer class for models.
    Inerit from this class, set model and populate the fields.
    Parent serializers are expected to add a private attribute (_attribute) with the name of the model
    to their children to keep a back reference.

    :method _get_kw:
        Returns all the data from attributes of this class that have the same name as the Model's columns
        Override this if you want to modify it.

    :method make:
        Add the object to the DB. Usually, you don't want to touch this unless you want to
        defer its execution

    :data model:
        The sqlalchemy model
    :data _is_data:
        True if the client should be passd to this class to execute Serializer.make()
    """

    # XXX maybe these for loops to create related models can be changed by nice functions

    model = None
    # False if it is a mixin
    _is_data = False

    def __init__(self, client):
        """
        The data is added to the database the moment the class is instantiated.
        Override "make" to alter this behavior.
        Columns are also fetched from the model here.

        :param client:
            The DB client with an active connection

        """
        self.client = client
        self.columns = self.model.__table__._columns.keys()
        # add name
        self.make()

    def _get_kw(self) -> dict:
        """
        Get the values from attributes that match column names.
        Override to add more stuff if you want but remember this data is passed directly
        to the model.
        """
        return {
            key: getattr(self, key) for key in self.__dir__() if key in self.columns
        }

    def make(self) -> None:
        """
        Simply create an object after passing the data to the model and persist it
        in the database
        """
        self.obj = self.model(**self._get_kw())  # pylint: --disable=not-callable
        self.client.session.add(self.obj)


class GenericTableSerializer(Serializer):
    """
    Generic tables need their own special serializer to add data from the other columns

    :property target:
        Override this property or add the target beforehand to get the target instance.
        You can (and should) use the client here to fetch data from other models since
        the class will be in the process of instantiation by that time.

    :data target_property:
        A string with the name of the name of a table of target
    """

    target_property = None

    def __init__(self, client, event):
        """
        We get the proper model for the generic table here.

        :param event: Most likely an Event; maybe a Buff; works the same
        """
        self.event = event
        self.client = client

        self.model = api._get_generic_table(
            self.model.__name__, self.event, self.target, self.target_property
        )
        super().__init__(client)

    def _get_kw(self):
        """
        Overriden to add target, target_property, and event
        """
        kw = super()._get_kw()
        kw.update(
            {key: getattr(self, key) for key in ("target", "target_property", "event")}
        )
        return kw

    @property
    def target(self):
        raise NotImplementedError


class GenericStat(Serializer):
    model = Stat


class GenericLocation(Serializer):
    model = Location


class GenericPath(Serializer):
    model = Path


class GenericArea(Serializer):
    model = Area


class GenericRequirement(GenericTableSerializer):
    model = Requirement


class GenericDialog(Serializer):
    """
    Generic dialog serializer.
    If you add a variable make sure you add a method to fetch the data
    for it.

    :data text:
        TextDesriptor instance to manage variables in text
    :data _varaibles:
        List with all the variables we will use
    """

    text = TextDescriptor()
    _variables = []

    @property
    def model(self):
        """
        One dialog model for each effect table
        """
        return self._effect.obj.dialog

    def __init__(self, text, *args, **kwargs):
        make_fn = self.make
        # defer because the descriptor requires a
        # initialized instance
        self.make = lambda: None
        super().__init__(*args, **kwargs)
        self.text = text

        make_fn()


#
class DialogWPlayer(GenericDialog):
    _variables = ["player"]

    @property
    def player(self):
        return self.client.get_player().one().name


class GenericEffect(GenericTableSerializer):
    """
    Generic effect serializer.
    The constructor accepts 4 arguments.
    :param client: The client, like all other Serializers
    :param event: The event, like all other GenericTableSerializers
    :param chunk: Text for the dialog model,
    """

    model = Effect
    # _dialog = GenericDialog
    _dialog = DialogWPlayer
    buffs = []
    score = 5
    filename = None
    _no_dialog = False

    def __init__(self, client, event, default_path=None):
        # here is the thing: we want to be able to
        # write multiple chunks of text for the same event
        # but the chunks can't have all the same :data score:
        # therefore we have to (slightly) modify it programatically to
        # make them not trigger all at the same time
        filename = (
            default_path.parent / (self.filename + ".txt")
            if self.filename
            else default_path
        )

        super().__init__(client, event)

        for buff in self.buffs:
            if isinstance(buff, str):
                buff = globals()[buff]

            buff._effect = self
            buff._target = self.obj
            self.obj.buffs.append(buff(client).obj)

        if self._no_dialog:
            return
        self._dialog._effect = self
        for chunk in _get_dialog_chunks(filename):
            self.obj.available_dialog.append(
                self._dialog(text=chunk, client=client).obj
            )


class TimeEffect(GenericEffect):
    """
    To modify the time stat. Maybe we want to add buffs to this
    (character is tired; everything takes longer) based on the type.
    I should work on refining buffs to work only with certain type of events...
    """

    target_property = "value"

    @property
    def target(self):
        return self.client.get_global(label="time").one()


class NoEffect(GenericEffect):
    """
    Wow, it's fucking nothing!

    This is used to bloat the events and make other effects
    trigger less often.
    """

    target_property = "energy"
    change = 0

    @property
    def target(self):
        return self.client.get_player().one()


class GenericBuff(Serializer):
    requirements = None

    @property
    def model(self):
        """
        Buffs are also special
        """
        return self._target.buff

    def __init__(self, client):
        super().__init__(client)
        for requirement in self.requirements:
            requirement._buff = self
            requirement(client, self.obj)


def _get_dialog_chunks(path):
    try:
        with open(path, encoding="utf-8") as file:
            data = file.read()
        return data.split("***")
    except FileNotFoundError as e:
        logger.warning(str(e))
        return [""]


@logged
class GenericEvent(Serializer):
    model = Event
    requirements = []
    effects = []
    name = ""
    type_ = "GLOBAL"

    character_name = None
    location_name = None
    locks = []
    locked_by = []
    children = []

    def __init__(self, client):
        super().__init__(client)
        for requirement in self.requirements:
            requirement._event = self
            requirement(client, self.obj)

        for effect in self.effects:
            effect._event = self

            # resolve the path where this type of event
            # should have its text stored
            base_path = DATA_DIR / "dialog"
            data_file = self.name + ".txt"
            data_path = None

            if hasattr(self, "_parent") and self._parent:
                # subevents
                data_path = (
                    base_path / "subevents" / self._parent.type_ / self._parent.name
                )
            elif self.character_name:
                # character events
                data_path = base_path / "characters" / self.character_name / self.type_
            else:
                data_path = base_path / "generic" / self.type_

            # give the path with the name of the event to provide a default
            # and create the effect
            effect(client=client, event=self.obj, default_path=data_path / data_file)
            # filename attribute to know if we should default to event name
            # if hasattr(effect, "filename"):
            #    effect(
            #        client=client,
            #        event=self.obj,
            #        score=effect.score,
            #        data_path=data_path,
            #    )
            # else:
            #    for index, chunk in enumerate(
            #        _get_dialog_chunks(data_path / data_file)
            #    ):
            #        effect(
            #            client=client,
            #            event=self.obj,
            #            chunk=chunk,
            #            score=effect.score + index / 10000,
            #        )

        for child in self.children:
            child.type_ = "SUBEVENT"
            child._parent = self
            subevent = child(client).obj
            self.obj.children.append(subevent)

        for event in self.locks:
            if isinstance(event, str):
                name = event
            else:
                name = event.name

            event_lock = EventLock(key=self.name, lock=name)
            self.client.session.add(event_lock)

        for event in self.locked_by:
            if isinstance(event, str):
                name = event
            else:
                name = event.name

            event_lock = EventLock(key=name, lock=self.name)
            self.client.session.add(event_lock)
        self.client.session.commit()


#
class ScheduleMixin:
    """
        For scheduling recurrent events so they can be handled by cronie.
        This mixin is use            Fix and schedule hong_hungry. Fix Library Dream (should not be
                accessed). Test schedule.
    d with Event, so the API supports adding the date declaratively.

        :data date:
            This is used along with the date mask to get the full date each time (in seconds)
        :data schedule_type:
            type_ field in the database (check cronie.py for details)
        :data date_index:
            array with numbers for whatever index we are using to indentify a valid date to add
            the event to the schedule
    """

    # we obviously can't add this as "type_" because it would override the one from
    # the event
    schedule_type = None
    date = None
    duration = None
    date_index = []

    def make(self):
        """
        Override make to add the event to the schedule.
        The logic behind not doing the usual and adding this to __init__ is that
        not all events need to be scheduled.
        """
        super().make()

        date_indexes = [Number(number=index) for index in self.date_index]
        obj = Schedule(
            event=self.obj,
            date=self.date,
            duration=self.duration,
            date_indexes=date_indexes,
            type_=self.schedule_type,
        )
        self.client.session.add(obj)


class ScheduleWork(ScheduleMixin):
    schedule_type = "WEEKLY"
    date_index = [0, 1, 2, 3, 4]


class ScheduleDaily(ScheduleMixin):
    schedule_type = "DAILY"


# mixins
class PlayerMixin:
    @property
    def player(self):
        return self.client.get_player().one()


class CharacterMixin:
    """
    To inerith the character from the event.
    """

    @property
    def character_name(self):
        if hasattr(self, "_event"):
            return self._event.character_name
        elif hasattr(self, "_effect"):
            return self._effect.character_name
        elif hasattr(self, "_requirement"):
            return self._requirement.character_name
        elif hasattr(self, "_buff"):
            return self._buff._effect.character_name
        else:
            raise AttributeError(f"{self} has no attribute character_name")

    @property
    def character_obj(self):
        return self.client.get_character(name=self.character_name).one()


class PlayerRelationshipMixin(PlayerMixin, CharacterMixin):
    target_property = "strength"
    buffs = [
        "FriendBuff",
    ]

    @property
    def target(self):
        return self.client.get_relationship(
            from_=self.player.name, to=self.character_name
        ).one()


class PlayerStatEffect(GenericEffect, PlayerMixin):
    target_property = "value"
    label = None

    @property
    def target(self):
        return self.client.get_stat(chara_name=self.player.name, label=self.label).one()


class MoveEffect(GenericEffect, CharacterMixin):

    target_property = "location_name"
    location = None

    @property
    def change(self):
        return self.location

    @property
    def target(self):
        return self.character_obj


# req
class TimeRequirement(GenericRequirement):
    target_property = "value"

    @property
    def target(self):
        return self.client.get_global(label="time").one()


# API
def make_cls(*mixins, **kwargs):
    name = ""
    for mix in mixins:
        name += mix.__name__.replace("Mixin", "")
    name += str(uuid4())
    return type(name, mixins, kwargs)


# stat
def make_stat(**kwargs):
    # lebel and value
    return make_cls(GenericStat, **kwargs)


def pstat_eff(**kwargs):
    # label
    return make_cls(PlayerStatEffect, **kwargs)


#
def no_effect(**kwargs):
    return make_cls(NoEffect, **kwargs)


# time stuff supports stuff like
# time_eff(hours=6)
# and regative times for our <= requirements
# time_req(minutes=-30)
def time_req(**kwargs):
    return make_cls(TimeRequirement, value=from_date(**kwargs))


def time_eff(days=0, hours=0, minutes=0, seconds=0, **kwargs):
    """
    Changing the date too much would be dumb.
    Maybe we should add some validation here.
    """
    return make_cls(
        TimeEffect,
        change=from_date(
            days=days,
            hours=hours,
            minutes=minutes,
            seconds=seconds
            # time effects don't have a filename
        ),
        _no_dialog=True,
        score=-1,
        **kwargs,
    )


def move_eff(location, **kwargs):
    return make_cls(MoveEffect, location=location, _no_dialog=True, **kwargs)


def prel_req(**kwargs):
    return make_cls(PlayerRelationshipMixin, GenericRequirement, **kwargs)


def prel_eff(**kwargs):
    return make_cls(PlayerRelationshipMixin, GenericEffect, **kwargs)


# buff
class FriendBuff(GenericBuff):
    mod = 1.2
    requirements = [
        prel_req(value=100),
    ]


class InfatuatedBuff(GenericBuff):
    mod = 1.5
    requirements = [
        prel_req(value=500),
    ]


# actions
""" # pylint: --disable=pointless-string-statement
To add a new action you need to:
    1. Add the endpoint to the API (ActionAPI @ server.py)
    2. Add the serializer here and create a sane default for the action
    3. Subclass the class @ data/event.py (follow the instructions to declare a DB object there)
    4. Write the text (@ data/dialog/generic/[TYPE]/[event.name|effect.filename].txt)
    5. Integrate it with the client (with gensim_cli you have to add the endpoint in the settings, declare the command, and add it)
"""


class Chat(GenericEvent):
    """
    Chat command
    """

    type_ = "CHAT"
    requirements = [
        prel_req(value=1),
    ]
    effects = [
        prel_eff(change=5),
        time_eff(minutes=30),
    ]


class Fish(GenericEvent):
    type_ = "FISH"
    requirements = [
        # energy
        # ...
    ]
    effects = [
        pstat_eff(label="fishing_skill", change=1, score=-1),  # ...
        # crit
        time_eff(minutes=30),
    ]


class Cook(GenericEvent):
    type_ = "COOK"
    requirements = [
        # energy
        # ...
    ]
    effects = [
        pstat_eff(label="cooking_skill", change=1, score=-1),  # ...
        # crit
        time_eff(minutes=30),
    ]


# event type
class Encounter(GenericEvent):
    """
    Trigger whenever we enter in a new location with a character
    """

    type_ = "ENCOUNTER"
    requirements = [
        prel_req(value=1),
    ]
    effects = [
        prel_eff(change=1),
    ]


class Flavor(GenericEvent):
    """
    Generic flavor text
    """

    type_ = "FLAVOR"
    requirements = [
        prel_req(value=1),
    ]
    effects = [
        no_effect(),
    ]


class Meet(GenericEvent):

    type_ = "ENCOUNTER"
    # requires relationship strength with the player to be less than 1
    # after completition, it goes from 0 -> 1 making it impossile to trigger the event twice
    # (make sure nothing makes rel.str 0, use %based effects or whatever)
    requirements = [
        prel_req(value=-1),
    ]
    effects = [
        prel_eff(change=1),
    ]


#
class GenericCharacter(Serializer):
    model = Character

    # you can add a default here with
    # value=[default]
    stats = [
        make_stat(label="cooking_skill"),
        make_stat(label="fishing_skill"),
    ]

    def __init__(self, client):
        super().__init__(client)

        for stat in self.stats:
            stat.chara_name = self.name
            stat(client)
