import datetime
import time
import traceback
from typing import Text


def current_timestamp_int() -> int:
    return int(time.time())  # TODO oleksandr: use int(time.time_ns()) instead ?


def datetime_now() -> datetime.datetime:
    return datetime.datetime.now()


def stack_trace_to_str(e: BaseException) -> Text:
    return ''.join(traceback.format_exception(type(e), e, e.__traceback__))


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
