"""
Here you can create the necessary data for events declaratively.
"""
from gensim.serializers import (
    GenericEvent,
    Chat,
    Meet,
    Encounter,
    Flavor,
    Fish,
    Cook,
    FriendBuff,
    ScheduleWork,
    ScheduleDaily,
    DialogWPlayer,
    no_effect,
    prel_req,
    prel_eff,
    time_req,
    time_eff,
    move_eff,
    pstat_eff,
)

class LiddellMixin:
    character_name = "Alice Liddell"


class Welcome(LiddellMixin, Meet):
    """
    Welcome the player to the wonderland.
    """

    # override type_ to make it trigger whenever the player spawns
    type_ = "GLOBAL"
    name = "welcome"
    _is_data = True
