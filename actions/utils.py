import time
import traceback
from datetime import datetime
from typing import Text


def current_timestamp_int() -> int:
    return int(time.time())  # TODO oleksandr: use int(time.time_ns()) instead ?


def format_swipy_timestamp(timestamp: int) -> Text:
    return datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S Z')


def datetime_now() -> datetime:
    return datetime.now()


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
