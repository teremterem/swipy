import time
import traceback
from typing import Text


def current_timestamp_int() -> int:
    timestamp = int(time.time())  # TODO oleksandr: use int(time.time_ns()) instead ?
    return timestamp


def stack_trace_to_str(e: BaseException) -> Text:
    return ''.join(traceback.format_exception(type(e), e, e.__traceback__))


class SwiperError(Exception):
    ...


class InvalidSwiperStateError(SwiperError):
    ...


class SwiperExternalCallError(SwiperError):
    ...


class SwiperRasaCallbackError(SwiperExternalCallError):
    ...


class SwiperDailyCoError(SwiperExternalCallError):
    ...
