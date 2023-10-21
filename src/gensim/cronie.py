"""
Data structure for the simulation event set.
All the events of the day are set before.
"""
from datetime import datetime, timedelta
from logging import getLogger

logger = getLogger("user_info." + __name__)

START_DATE = datetime(2022, 1, 1).timestamp()


def parse_time(time: float) -> datetime:
    date = datetime.fromtimestamp(time)
    return date


def from_date(**kwargs):
    return int(timedelta(**kwargs).total_seconds())


class Notice:
    """
    Linked list. timestamp. recurrent events.
    """

    def __init__(
        self,
        event_id: int,
        date: datetime,
        previous: "Notice" = None,
        following: "Notice" = None,
    ):

        # NOTE id of the event for eaget loading
        # lazy loading is impossible because we save the
        # in-memory calendar to the database using pickle
        # so the Sqlalchemy objects stop being linked to a session
        self.event_id = event_id
        self.date = date
        self.previous = previous
        self.following = following

    def insert(self, notice: "Notice"):
        """
        Insert new event into the linked list.
        """
        if notice.date > self.date:
            if self.following is None:
                # case: last event
                #
                # [ self ] [ (None) ]
                self.following = notice
                notice.previous = self
                return
            # delegate
            #
            # [ self ] ... [ notice ]
            self.following.insert(notice)
            return
        # <
        # it's still before the previous
        if not self.previous:
            # case: firsto
            # [ (None) ] [ self ]
            self.previous = notice
            notice.following = self
            return
        # there is a previous fix it
        # fix previous
        #
        # [ prev ] > notice <  [ self ] [ following ]
        self.previous.following = notice
        notice.previous = self.previous

        # fix following
        self.previous = notice
        notice.following = self

    def next(self):
        """
        Return next event. A.K.A the head of the chain.
        """
        if self.previous is None:
            return self
        return self.previous.next()

    def all(self):
        notice = self

        while notice:
            yield notice.date
            notice = notice.following

    def event_ids(self, date_start, date_end):
        notice = self
        _old_notice = self
        event_ids = []

        while notice and notice.date <= date_end:
            if notice.date <= date_start:
                # not in range yet
                notice = notice.following
                _old_notice = notice
                continue
            event_ids.append(notice.event_id)
            _old_notice = notice
            notice = notice.following

        return {"event_ids": event_ids, "notice": _old_notice}

    def pop(self):
        self.following.previous = None
        return self.following

    def get(self, date):
        notice = self

        while notice and notice.date != date:
            notice = notice.following
        return notice

    def __str__(self):
        return (
            f"[ Notice ] (event_id={self.event_id}, date={self.date}, "
            f"following={self.following.date if self.following else None}"
            f", previous={self.previous.date if self.previous else None})"
        )

    def __repr__(self):
        return self.__str__()
