from typing import Callable, Awaitable, Any

from rasa.core.channels import TelegramInput, UserMessage
from sanic import Blueprint


class SwiperTelegramInput(TelegramInput):
    def blueprint(
            self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        async def handler(message: UserMessage) -> Any:
            print()
            print()
            print()
            print('SWIPERASA - BEFORE HANDLER')
            print()
            res = await on_new_message(message)
            print()
            print('SWIPERASA - AFTER HANDLER')
            print()
            print()
            print()
            return res

        return super().blueprint(handler)
