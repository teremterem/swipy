import traceback
from typing import Text


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
