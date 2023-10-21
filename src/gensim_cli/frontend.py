"""
Here goes the presentation layer
"""
from enum import Enum, EnumMeta
from functools import lru_cache
import logging
from types import DynamicClassAttribute
from typing import Dict, Tuple, List

from gensim_cli.writelogs import logged
from gensim_cli.client import GensimClient
from gensim_cli import settings

log = logging.getLogger("audit." + __name__)


def print(*args, **kwargs):
    __builtins__["print"](*args, **kwargs, end="")


def input(*args, **kwargs):
    res = __builtins__["input"](*args, **kwargs)
    if not res.isdecimal():
        return CEnum.nothing
    try:
        return CEnum[int(res)]
    except KeyError:
        return CEnum.nothing


def sinput(*args, **kwargs):
    return __builtins__["input"](*args, **kwargs)


class EnumContainer(EnumMeta):
    """
    Enum that supports "in" operations with the enum names
    """

    def __contains__(self, other):
        return other in self._member_map_.keys()


class Command:
    def __init__(self, cmd_name, cmd_id, cmd_verbose):
        self.name = cmd_name
        self.value = cmd_id
        self.verbose_name = cmd_verbose

    def __str__(self):
        return f"([{self.value}] {self.verbose_name})"

    def as_dict(self):
        return {self.verbose_name: self.value}


# to change range of cmds change the validator
@logged
class CEnum:
    """
    Enum for commands
    """

    # game
    chat = (300, "")
    action_walk = (301, "Move")
    action_chat = (302, "Chat")
    action_fish = (303, "Fish")
    action_cook = (304, "Cook")

    # system
    new_game = (0, "New game")
    load_game = (1, "Load game")
    save_game = (2, "Save game")

    # internal
    # don't be misleaded
    # some game commands have to be handled internally
    # and are not here. those usually require input from the
    # user
    back = (9999, "Back")
    # literally nothing
    nothing = (10000, "")

    def __init__(self):
        self.cmd_ids = {}
        for name in self.__dir__():
            val = getattr(self, name)
            if not (
                isinstance(val, tuple)
                and len(val) == 2
                and isinstance(val[0], int)
                and isinstance(val[1], str)
            ):
                continue
            cmd, verbose_name = val
            enum = Command(name, cmd, verbose_name)

            setattr(self, name, enum)
            # reverse lookup
            self.cmd_ids[cmd] = name

    def __getitem__(self, value):
        return getattr(self, self.cmd_ids[value])

    def __call__(self, value):
        return getattr(self, self.cmd_ids[value])


CEnum = CEnum()


class Style(Enum, metaclass=EnumContainer):

    cmd = ("[", "]")
    dialog = ("", "")


VALIDATE = {
    "game": set(range(300, 1000)),
    "system": set(range(0, 300)),
}


def validate_cmd(num, target):
    return num in VALIDATE[target]


@logged
class Present:
    """
    Print stuff on the screen
    """

    WINDOW_SIZE = 150
    dchara = "#"
    style = Style

    def _print(self, string, style_start, style_end, align):
        charas = self.WINDOW_SIZE
        printed = 0
        cha = charas - 2
        index = len(string) - 1
        strlen = len(string)

        if align == "center":
            blanks = (cha - strlen) // 2
            print(" " * blanks)
            cha -= blanks

        if style_start:
            print(style_start, " ")
            cha -= bool(style_start) + 1

        # start: print content
        if strlen >= cha:
            # https://gitgud.io/moist/gensim/-/issues/9#note_273953
            index = 0
            while index < cha:
                c = string[index]
                print(c)
                index += 1

                if c == "\n":
                    # "reset"
                    return self._print(string[index:], style_start, style_end, align)

            printed = cha
        else:
            printed = strlen
            print(string)
        # end: print content

        cha -= printed
        print(" ", style_end)
        print((cha) * " ")
        # no, i don't care if default character is ""
        print("\n")

        if strlen - index > 1:
            # not completely printed (str[-1] was not printed)
            self._print(string[index:], style_start, style_end, align)

    def print(self, string, style=None, align="left"):
        if style in self.style:
            start, end = self.style[style]
        else:
            start, end = ("", "")
        self._print(string, start, end, align)

    def print_line(self):
        print(self.dchara * self.WINDOW_SIZE)
        print("\n")

    def print_blank(self, number=1):
        for _ in range(number):
            self.print("")

    def print_cmd(self, align, cmds: Command):
        if isinstance(cmds, dict):
            # for stuff like saves and anything that
            # is not a defined command
            for key, value in cmds.items():
                start, end = self.style.cmd.value
                self.print(f"{start}{key}{end} {value}", align=align)
        else:
            start, end = self.style.cmd.value
            for cmd in cmds:
                self.print(f"{start}{cmd.value}{end} {cmd.verbose_name}", align=align)

    def print_cmds(self, align, cmds: Command):
        """
        Squash all cmds together
        """
        start, end = self.style.cmd.value
        string = ""
        if isinstance(cmds, dict):
            for key, value in cmds.items():
                string += f" {start}{key}{end} {value}"
        else:
            for cmd in cmds:
                string += f" {start}{cmd.value}{end} {cmd.verbose_name}"
        self.print(string.strip(), align=align)


class BackMain(Exception):
    """
    Back to main menu
    """

    pass


@logged
class Game:
    """
    Singleton.
    Action commands are handled as internal.
    """

    _running = True
    client = GensimClient()
    pres = Present()

    # data
    #
    # present
    characters = []
    # selected to execute actions
    selected = 1

    # frequently used
    @property
    @lru_cache
    def player(self):
        return self.client.character.get("player")["name"]

    def execute_cmd(self, cmd: Command, type_, *args, **kwargs):
        self.logger_file.info(
            "Executing %s. Type: %s with (%s, %s)", cmd, type_, args, kwargs
        )
        if not validate_cmd(cmd.value, type_):
            self.logger_file.warning("Invalid cmd (%s) for type (%s)", cmd, type_)
            return False, False
        if type_ not in ("internal",):
            return cmd, getattr(self.client, cmd.name)(*args, **kwargs)

    def execute_internal(self, cmd: Command, type_, *args, **kwargs) -> Dict:
        """
        Here we handle the actions.
        Either raises an exception, returns kwargs for a command, moves on to
        another scene.
        Raises Back in case of failure.
        """
        self.logger_file.info(
            "Executing %s cmd '%s' with (%s, %s)", type_, cmd, args, kwargs
        )
        if not validate_cmd(cmd.value, type_):
            self.logger_file.warning("Invalid cmd (%s) for type (%s)", cmd, type_)
            return {}

        if hasattr(self, "_" + cmd.name):
            return getattr(self, "_" + cmd.name)(*args, **kwargs)
        self.logger.error("Invalid command %s", cmd)
        return {}

    def handle_subevents(self, children):
        """
        Handle child events
        """
        child_map = {}
        child_cmds = {}
        for index, child in enumerate(children):
            child_map[str(index)] = child["name"]
            child_cmds[str(index)] = child["verbose_name"]

        self.pres.print_cmd(align="left", cmds=child_cmds)

        indx = sinput()

        if indx in child_map:
            return self.client.trigger_event(child_map[indx])
        # retard
        self.handle_subevents(children)

    def handle_events(self, events):
        """
        Print several events on screen.
        """
        for event in events:
            self.handle_event(event)

    def handle_event(self, event):
        """
        Print event on screen. Can handle chained events.
        """
        for effect in event["effects"]:
            if effect["text"]:
                self.pres.print(
                    effect["text"].strip(), align="left", style=Style.dialog
                )
                sinput()  # little pause

        if event["children"]:
            choice = self.handle_subevents(event["children"])
            self.handle_events(choice)

    def _back(self):
        self.logger_file.info("Going back")
        raise BackMain

    def _action_walk(self):
        """
        The walk command requires further input
        """
        self.pres.print_line()
        self.pres.print("Move doko?")
        # immediate locations, list with filtering
        #
        # we get a raw input not a cmd so we use sindex and pass the
        # index as a string
        locations = {
            str(index): location["name"]
            for index, location in enumerate(self.client.area.close_locations.list())
        }
        self.pres.print_cmds(align="center", cmds=locations)

        location = sinput()
        if location in locations.keys():

            kwargs = {
                "character": self.player,
                "destination": locations[location],
            }
            _, events = self.execute_cmd(CEnum.action_walk, "game", **kwargs)

            self.handle_events(events["events"])
            return (_, events)
        # retard
        self.action_walk()

    # XXX refactor
    def _action_chat(self):
        try:
            _, events = self.execute_cmd(
                CEnum.action_chat, "game", character=self.characters[self.selected]
            )
        except IndexError:
            self.pres.print("You can't talk to yourself!")
            events = []
        self.handle_events(events)

    def _action_fish(self):
        _, events = self.execute_cmd(
            CEnum.action_fish,
            "game",
        )
        self.handle_events(events)

    def _action_cook(self):
        _, events = self.execute_cmd(
            CEnum.action_cook,
            "game",
        )
        self.handle_events(events)

    def _load_game(self):
        self.pres.print_line()
        self.pres.print_blank(number=2)

        saves = self.client.ls_saves()
        num = saves["num"]

        if num == 0:
            self.pres.print("No saves yet", align="center", style="title")
        else:
            # current
            self.pres.print_cmd(align="left", cmds={0: "(Auto) {Date} - {Player}"})

        for save in range(num - 1):
            self.pres.print_cmd(align="left", cmds={num - 1: "{Date} - {Player}"})
        self.pres.print_blank(number=2)
        self.pres.print_cmd(
            align="left",
            cmds=[
                CEnum.back,
            ],
        )

        gamenum = sinput()
        if gamenum.isnumeric():
            gamenum = int(gamenum)
            if gamenum not in range(num + 1):
                self.logger_file.warning("%s is not a valid savefile number", gamenum)
                return

        self.execute_cmd(CEnum.load_game, "system", num=gamenum)

        self.game()

    def _new_game(self):
        # configure game (name, stats, etc)
        self.pres.print_line()
        self.pres.print_blank(number=2)

        name = sinput("name: ")

        self.execute_cmd(CEnum.new_game, "system", name=name)

        self.game()

    def main_loop(self):
        while self._running:
            log.info("Main menu")
            try:
                self.main_menu()
            except BackMain:
                pass
            except Exception as exc:
                log.critical(exc)
                if settings.DEBUG:
                    raise exc
            log.info("Return to main menu")

    def main_menu(self):
        self.pres.print_line()
        self.pres.print_blank(number=10)
        self.pres.print("Gensim", align="center")
        self.pres.print_blank(1)

        self.pres.print_cmd(
            align="center",
            cmds=self.client.get_cmds("main_menu"),
        )

        cmd = input()
        self.execute_internal(cmd, "system")

    def game(self):
        while True:
            try:
                self.pres.print_line()
                data = self.client.event_loop()

                # present location
                self.pres.print(
                    f"[{data['time']}] You are at {data['location']}", align="left"
                )

                # present environment
                self.characters = data["characters"]  # cache
                self.pres.print(
                    "Characters present: " + str(self.characters), align="left"
                )
                self.handle_events(data["events"])

                # available cmds
                available_cmds = []
                # basic
                available_cmds.extend(self.client.get_cmds("game"))
                # location
                available_cmds.extend(self.client.get_cmds(data["location"]))
                # terrain
                terrain = self.client.get_location
                available_cmds.extend(self.client.get_cmds(data[""]))

                self.pres.print_cmds(
                    align="center",
                    cmds=self.client.get_cmds("game")
                    cmds=[
                        CEnum.action_walk,
                        CEnum.action_chat,
                        CEnum.action_fish,
                        CEnum.action_cook,
                    ],
                )

                # wait for input
                cmd = input()

                # execute cmd
                #
                # get any args the cmd needs, return or do nothing
                self.execute_internal(cmd, "game")
                # repeat
            except BackMain:
                self.logger.warning("going back")

    def exit_game(self):
        self.running = False


def play():
    log.info("Initializing gaem")
    game = Game()
    try:
        game.main_loop()
    except KeyboardInterrupt:
        print("bye bye\n")


if __name__ == "__main__":
    play()
