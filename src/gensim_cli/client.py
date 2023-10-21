"""HTTP client for testing purposes"""
import json

import yaml
from requests import Session

from gensim_cli.writelogs import logged
from gensim_cli import settings


@logged
class Client(Session):
    """HTTP client. Inherits from Session"""

    def __init__(self, *args, url: str = None, **kwargs):
        self.BASE_URL: str = url or settings.BASE_URL
        self.URLS: dict = settings.URLS  # DEBUGGING: all urls
        self.URL_PARAMS: set = settings.URL_PARAMS

        self._url = self.BASE_URL
        self._res = None  # DEBUG: last response

        super().__init__(*args, **kwargs)

    def __getattr__(self, name):
        """Takes any attribute that is placed in settings.py PARAMS and adds it to
        the _url attribute"""
        if name not in self.URL_PARAMS:
            raise AttributeError(name, "Did you register this url param?")
        self._url += f"{name}/"
        return self

    def kwarg(self, *args):
        """
        Add an url kwarg to the path for complex urls:

        >>> self.kwarg(1)
        >>> self._url
        :[BASE_URL]1/

        Made specially to cast numerical ids to str.
        """
        for value in args:
            self._url += f"{value}/"
        return self

    # --- helper methods ---
    def check_for_errors(self, res):  # pylint: disable=C0116
        if res.status_code > 399:
            # there is an error
            message = ""
            try:
                for key, value in res.json().items():
                    # since the response often comes as a list
                    error = key.capitalize()
                    message = "".join(value)
                    message += (
                        f"{error}: {message}\nHeaders: {res.headers}\n"
                        f"Client headers: {self.headers}. Url: {res.url}"
                    )

                self.logger.error(message)  # pylint: disable=E1101
                self.logger_file.error(message)  # pylint: disable=E1101
            except json.decoder.JSONDecodeError:
                self.logger.error(  # pylint: disable=E1101
                    f"Could't aqcuire JSON response. URL: {res.url}. \n"
                    f"Headers: {res.headers}. Code: {res.status_code}. Url: {res.url}"
                )
            return True
        return False

    def urlize_params(self, params: dict):
        """
        Transform a dict into its url-encoded equivalent

        >>> urlize_params({"key": "val", "foo": "bar"})
        ?key=val&foo=bar
        """
        url = "?"
        url += "&".join([f"{key}={val}" for key, val in params.items()])

        return url

    # --- core methods ---
    def request(self, method, url, data=None):
        """Base request function"""
        res = super().request(method=method, url=url, json=data)
        self._res = res

        self._url = self.BASE_URL  # clean up

        if not self.check_for_errors(res):
            if (
                res.status_code != 204
            ):  # XXX no way around it. DELETE doesn't send a JSON response
                return res.json()
        return None

    # --- overriden convenience methods ---
    # XXX should I have avoided overriding them?
    # and made alternative methods in its place
    # (make, edit)
    def create(self, data):  # pylint: disable=C0116
        return self.request("POST", self._url, data=data)

    def update(self, id_, data):  # pylint: disable=C0116
        return self.request("PUT", self._url + f"{id_}/", data)

    def get(self, id_):  # pylint: disable=C0116
        return self.request("GET", self._url + f"{id_}/")

    def list(self, params: dict = None):  # pylint: disable=C0116
        params = {} or params
        url_params = ""
        if params:
            url_params = self.urlize_params(params)
        self._url = self._url.rstrip(
            "/"
        )  # list accepts url kwargs. so we can't add the slash
        return self.request("GET", self._url + url_params)

    def delete(self, id_):  # pylint: disable=C0116
        return self.request("DELETE", self._url + f"{id_}/")

    def patch(self, id_, data):
        return NotImplemented

    # short-circuit other methods to avoid confusion
    def options(self, *args, **kwargs):
        raise NotImplementedError

    def head(self, *args, **kwargs):
        raise NotImplementedError


def shell():
    # no need to import this if we aren't testing
    # wich will be the case in prod
    import os
    import sys
    import traceback

    session = GensimClient()

    version = "0.1.0"

    print("HTTP client interactive shell.")
    print(f"{version=}")
    print('Use "session.param_1.param_2.method(data)" to make requests.')
    while True:
        print(">>> ", end="")
        try:
            # READ
            string = input()
            if "=" not in string and "import" not in string:
                # EVAL
                evaluated = eval(string)
                # PRINT
                print(evaluated)
            else:
                exec(string)
        except KeyboardInterrupt:
            os.system("clear")
        except EOFError:
            print("\nbye bye")
            break
        except Exception:
            cls, exc, tb = sys.exc_info()
            print("Traceback (most recent call last):")
            traceback.print_tb(tb)
            print(f"{cls.__name__}:", exc)


class GensimClient(Client):
    def new_game(self, **kwargs):
        return self.game.create(kwargs)

    def save_game(self, num):
        return self.game.save.get(num)

    def load_game(self, num):
        return self.game.load.get(num)

    def event_loop(self):
        return self.event.loop.list()

    def trigger_event(self, name):
        return self.event.trigger.get(name)

    def action_walk(self, character, destination):
        walk_data = settings.WALK_PAYLOAD.copy()
        walk_data["character"] = character
        walk_data["destination"] = destination

        return self.event.trigger.walk.create(walk_data)

    def action_chat(self, character):
        return self.event.trigger.chat.create({"character": character})

    def action_fish(self):
        return self.event.trigger.fish.list()

    def action_cook(self):
        return self.event.trigger.cook.list()

    def player_status(self, attr="name"):
        return self.character.get("player")

    def ls_saves(self):
        return self.game.list()


if __name__ == "__main__":
    shell()
