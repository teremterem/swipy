import time
import traceback
from datetime import datetime
from typing import Text, Optional

from rasa_sdk import Tracker


def current_timestamp_int() -> int:
    return int(time.time())  # TODO oleksandr: use int(time.time_ns()) instead ?


def format_swipy_timestamp(timestamp: int) -> Text:
    return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S Z')


def datetime_now() -> datetime:
    return datetime.now()


def stack_trace_to_str(e: BaseException) -> Text:
    return ''.join(traceback.format_exception(type(e), e, e.__traceback__))


def get_intent_of_latest_message_reliably(tracker: Tracker) -> Optional[Text]:
    """
    tracker.get_intent_of_latest_message() doesn't work for artificial messages because intent_ranking is absent,
    hence the existence of this utility function...
    """
    if not tracker.latest_message:
        return None
    return (tracker.latest_message.get('intent') or {}).get('name')


class SwiperError(Exception):
    ...


class InvalidSwiperStateError(SwiperError):
    ...


class SwiperStateMachineError(SwiperError):
    ...


class SwiperExternalCallError(SwiperError):
    ...


class SwiperRasaCallbackError(SwiperExternalCallError):
    ...


class SwiperDailyCoError(SwiperExternalCallError):
    ...
