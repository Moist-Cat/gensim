"""
Declarative class for the player goes here.
This template will be used when generating the player.

Defaults:
    energy = 2000
"""
from gensim.serializers import GenericCharacter, make_cls


class Player(GenericCharacter):
    is_player = True


def make_player(client, **kwargs):
    Player.energy = kwargs.pop("energy", 2000)
    Player.name = kwargs.pop("name")
    Player.home_name = kwargs.pop("home_name", "[some_area]")
    Player.location_name = kwargs.pop("location_name", "[some_location]")
    player = Player(client)
    for label, value in kwargs:
        stat = client.get_stat(chara_name=player.name, label=label)
        if len(stat) == 1:
            client.update(stat.one(), int(value))
