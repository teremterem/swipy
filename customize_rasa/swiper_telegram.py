from typing import Callable, Awaitable, Any

from rasa.core.channels import TelegramInput, UserMessage
from sanic import Blueprint

START_DEEPLINK_PREFIX = '/start '


class SwiperTelegramInput(TelegramInput):
    def blueprint(
            self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        async def handler(message: UserMessage) -> Any:
            if message.text and message.text.startswith(START_DEEPLINK_PREFIX):
                deeplink_data = message.text[len(START_DEEPLINK_PREFIX):]
                message.text = '/start'

                message.metadata = message.metadata or {}
                message.metadata['deeplink_data'] = deeplink_data
            res = await on_new_message(message)
            return res

        return super().blueprint(handler)
