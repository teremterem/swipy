import html
import time
import traceback
from datetime import datetime
from typing import Text, Optional, Union, Any, List, Tuple

from rasa_sdk import Tracker


def present_partner_name(first_name: Text, placeholder: Text) -> Text:
    if first_name:
        return f"<b><i>{html.escape(first_name)}</i></b>"
    return placeholder


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


def roll_the_list(
        latest_list: Optional[Union[List[Any], Tuple[Any]]],
        new_item: Any,
        num_of_items_to_keep: int,
) -> List[Any]:
    latest_list = latest_list or []

    if num_of_items_to_keep > 1:
        new_list = latest_list[-num_of_items_to_keep + 1:]
        new_list.append(new_item)

    elif num_of_items_to_keep == 1:
        new_list = [new_item]
    else:
        new_list = []

    return new_list


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
