from datetime import datetime
from json.encoder import JSONEncoder
import re

from flask import Blueprint, Flask, request, make_response
from flask_classful import FlaskView, route
from werkzeug.exceptions import HTTPException

from gensim.api import Client
from gensim.conf import settings
from gensim.db import Base, Event
from gensim.management import db as man_db
from gensim.cronie import Notice


api = Blueprint("api", __name__)

app = Flask(__name__)
api = Blueprint("api", __name__, url_prefix="/api")

try:
    app.client = Client(man_db.get_save("current"))
except AssertionError:
    app.client = None  # maybe point to the master db?


class ModelSerializer(JSONEncoder):
    def default(self, o):
        if isinstance(o, Base):
            return o.as_dict()
        return super().default(o)


encoder = ModelSerializer()


# REST API
def output_json(data, code, headers=None):
    content_type = "application/json"
    dumped = encoder.encode(data)
    if headers:
        headers.update({"Content-Type": content_type})
    else:
        headers = {"Content-Type": content_type}
    response = make_response(dumped, code, headers)
    return response


class APIView(FlaskView):
    representations = {"application/json": output_json}
    model = None
    pk_field = "name"
    excluded_methods = ["get_queryset"]
    route_base = None

    def __new__(cls, *args, **kwargs):
        name = re.sub("APIView", "", cls.__name__).lower()
        cls.model = cls.model or name
        cls.route_base = cls.route_base or f"/{name}"

        return FlaskView.__new__(cls, *args, **kwargs)

    def get_queryset(self, method, *args, **kwargs):
        cli = app.client
        return getattr(cli, f"{method}_{self.model}")(*args, **kwargs)

    def post(self):
        # it returns the event object
        return self.get_queryset("create", **request.json).as_dict()

    def index(self):
        return self.get_queryset("get").all()

    def get(self, id):
        return self.get_queryset("get", **{self.pk_field: id}).one()

    def update(self, id):
        # here I would get the post data and update stuff
        kwargs = request.json

        obj = self.get_queryset("get", **{self.pk_field: id}).one()
        nu_obj = app.client.update(obj, **kwargs)

        return nu_obj.as_dict()

    def delete(self, id):
        obj = self.get_queryset("get", **{self.pk_field: id}).one()

        app.client.session.remove(obj)

        return {}


class APIException(HTTPException):
    code = 400
    description = "bad request"

    def get_description(
        self,
        environ=None,
        scope=None,
    ) -> str:
        """Get the description."""
        if self.description is None:
            description = ""
        elif not isinstance(self.description, str):
            description = str(self.description)
        else:
            description = self.description
        return description

    def get_body(
        self,
        environ=None,
        scope=None,
    ) -> str:
        """Get the HTML body."""
        return encoder.encode(
            {"status_code": self.code, "errors": self.get_description}
        )

    def get_headers(
        self,
        environ=None,
        scope=None,
    ):
        """Get a list of headers."""
        return [("Content-Type", "application/json")]


class GameAPIView(APIView):
    def post(self):
        post_data = request.json
        if not "name" in post_data:
            raise APIException("field 'name' is required")

        man_db.new_game(**post_data)
        current_save = man_db.get_save("current")
        app.client = Client(current_save)
        # get today to keep a schedule
        # NOTE not just the day because it will break at the end
        # of the month and that would be silly
        app.today = app.client.get_time()
        # XXX reset calendar
        # make it so we trigger from a date to another
        app.calendar = None
        app.client.create_calendar(app.calendar)

        app.logger.info("Created newge.")
        app.client.session.commit()
        return {}

    def index(self):
        """
        List saves
        """
        # XXX make them save objects in man_db to add timestamp, player, etc
        return {"num": man_db.total_saves()}

    @route("/load/<int:num>/")
    def load_game(self, num: int):
        if num > 0:
            # if 0 we just give the current save
            man_db.load_game(num)

        current_save = man_db.get_save("current")
        app.client = Client(current_save)
        app.calendar = app.client.get_calendar()
        app.today = app.client.get_time()

        return {}

    @route("/save/<int:num>/")
    def save_game(self, num: int):
        man_db.save_game(num)

        return {}


def _trigger(events):
    completed_events = []
    player_location = app.client.get_player().one().location
    for event in events:
        if event.available:
            app.logger.info("The event %s is currently available.", event)
            effects = event.complete()
            # prune the text if the player is not in the location
            # of the event
            if (
                (event.type_ != "GLOBAL")
                and (event.character and event.character.location != player_location)
                or (event.location and event.location != player_location)
            ):
                for effect in effects:
                    app.logger.debug(
                        "The event %s is happening in other location. Text will not be shown",
                        event.name,
                    )
                    # this deletes the text of the effect inside of the array
                    effect["text"] = ""

            # add metadata for the event
            event_info = event.as_dict()
            event_info["effects"] = effects

            completed_events.append(event_info)

            if event.prune:
                app.logger.warning("Pruning %s", event)
                for effect in event.effects:
                    app.client.session.delete(effect)
                for req in event.requirements:
                    app.client.session.delete(req)
                app.client.session.delete(event)
    app.client.session.commit()
    return completed_events


def trigger(events: list) -> list:
    """
    Decide what events should be triggered and how.
    """
    date_start = app.client.get_time()
    completed_events = _trigger(events)
    date_end = app.client.get_time()
    # schedule

    MASKS = {
        "YEARLY": datetime(year=date_end.year, month=1, day=1).timestamp(),
        "MONTHLY": datetime(
            year=date_end.year, month=date_end.month, day=1
        ).timestamp(),
        "DAILY": datetime(
            year=date_end.year, month=date_end.month, day=date_end.day
        ).timestamp(),
        # WEEKLY uses DAILY mask
        "WEEKLY": datetime(
            year=date_end.year, month=date_end.month, day=date_end.day
        ).timestamp(),
    }

    # if this is ever refactored move it to a function
    if app.calendar is None or date_end.date() > app.today.date():
        app.today = date_end
        app.logger.info(
            "Resetting schedule. REASON: %s",
            "NO CALENDAR" if app.calendar is None else "DATE_CHANGE",
        )
        notices = app.client.get_today_schedule(date_end)
        for notice in notices:
            # we set up the date, and time requirements here
            event = notice.event
            date = int(MASKS[notice.type_] + notice.date)

            # flush old date requirements
            app.client.flush_date_requirements(event)

            # create date req
            app.client.create_date_requirement(event, value=date)
            app.logger.debug("Using date: %s", datetime.fromtimestamp(date))
            if notice.duration:
                # create aditional req
                app.logger.debug(
                    "Event %s is continuous, adding another requirement", event
                )
                # negative know how the req should be evaluated
                app.client.create_date_requirement(
                    event, value=-(date + notice.duration)
                )
            sched = Notice(event_id=event.id, date=date)

            if app.calendar:
                app.calendar.insert(sched)
                # update head
                app.calendar = app.calendar.next()
            else:
                app.calendar = sched

        # save today's schedule calendar
        app.client.update_calendar(app.calendar)
        app.logger.info("Calendar updated: %s", app.calendar)

    # get all the events to the date
    if isinstance(app.calendar, Notice):
        sched_events = app.calendar.event_ids(
            date_start=int(date_start.timestamp()), date_end=int(date_end.timestamp())
        )
        # update head
        app.calendar = sched_events["notice"]
        if app.calendar is None:
            app.logger.warning("No more events for today at %s", date_end)
            # to make "app.calendar is None" fail to force
            # it to wait to tomorrow
            app.calendar = True

        # add events
        completed_events.extend(
            _trigger(app.client.get_events(sched_events["event_ids"]))
        )

    return completed_events


class EventAPIView(APIView):
    """
    CRUD for Events and endpoint to trigger globals
    """

    # action
    @route("/trigger/walk/", methods=["POST"])
    def walk(self):
        character = app.client.get_character(name=request.json["character"]).one()
        destination = request.json["destination"]

        walked: dict = app.client.walk(
            origin=character.location.name, destination=destination
        )

        time_stat = app.client.get_global(label="time").one()
        time_stat.value += walked["time"]
        character.location = app.client.get_location(name=destination).one()

        app.client.session.add(time_stat)
        app.client.session.commit()

        # trigger events
        events = []
        characters = list(map(lambda c: c.name, character.location.characters))
        # NOTE add random events; trigger for every location
        events.extend(
            app.client.get_event(type_="ENCOUNTER")
            # event
            .filter(Event.character_name.in_(characters)).all()
        )

        completed_events = trigger(events)

        walked["events"] = completed_events

        return walked

    @route("/trigger/chat/", methods=["POST"])
    def chat(self):
        character = app.client.get_character(name=request.json["character"]).one()
        if character.location_name != app.client.get_player().one().location_name:
            # fuck off retard
            raise APIException(
                description="You can not chat with a character in another location!",
                code=400,
            )
        # chat event
        chat = app.client.get_event(type_="CHAT").filter(Event.character == character)
        return trigger(chat)

    @route("/trigger/fish/", methods=["GET"])
    def fish(self):
        fish = app.client.get_event(type_="FISH")

        return trigger(fish)

    @route("/trigger/cook/", methods=["GET"])
    def cook(self):
        cook = app.client.get_event(type_="COOK")

        return trigger(cook)
    #
    @route("/trigger/<name>/")
    def trigger_event(self, name: str):
        event = app.client.get_event(name=name)

        return trigger(event)

    @route("/loop")
    def loop(self):
        """
        Procedure to trigger events in a location. It's used often so I wrapped
        them in a single endpoint rather than let the fron-end implement it.

        2. Get global events
        3. Get location events (flavor text for work, maybe)
        4. Get character FLAVOR events
        5. Trigger them all and send them
        """
        # app.client.session.commit()

        location = app.client.get_player().one().location
        events = app.client.get_event(type_="GLOBAL").all()
        characters = list(map(lambda c: c.name, location.characters))

        #
        events.extend(location.active_events)
        # maybe one encounter event per character, yes?
        events.extend(
            app.client.get_event(type_="FLAVOR")
            # event
            .filter(Event.character_name.in_(characters)).all()
        )

        return {
            "time": str(app.client.get_time()),
            "location": location.name,
            "characters": characters,
            "events": trigger(events),
        }


# character
class CharacterAPIView(APIView):
    """
    Character CRUD view
    """

    def get(self, id):
        if id == "player":
            return self.get_queryset("get", **{"is_player": True}).one()
        return super().get(id)


class LocationAPIView(APIView):
    @route("/<location>/characters")
    def characters(self, location):
        location = app.client.get_location(name=location).one()
        return location.characters


class AreaAPIView(APIView):
    @route("close_locations")
    def close_locations(self):
        return app.client.get_player().one().location.area.locations

    @route("<area>/locations")
    def locations(self, area):
        area = app.client.get_area(name=area).one()
        return area.locations

class CommandAPIView(APIView):
    pass

class CommandMapAPIView(APIView):
    pass

_loc = locals().copy()
_keys = _loc.keys()
for namespace in _keys:
    if namespace.endswith("APIView") and namespace != "APIView":
        if issubclass(_loc[namespace], APIView):
            view = _loc[namespace]
            view.register(api)

app.register_blueprint(api)


def runserver():
    app.run(port=settings.PORT, threaded=False)
