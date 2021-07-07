from typing import Callable, Awaitable, Any, Optional, Dict, Text

import ujson
from rasa.core.channels import TelegramInput, UserMessage
from sanic import Blueprint
from sanic.request import Request

START_DEEPLINK_PREFIX = '/start '


class SwiperTelegramInput(TelegramInput):
    def blueprint(
            self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        async def handler(message: UserMessage) -> Any:
            if message.text and message.text.startswith(START_DEEPLINK_PREFIX):
                deeplink_data = message.text[len(START_DEEPLINK_PREFIX):]
                message.text = '/start'

                if deeplink_data:
                    message.metadata = message.metadata or {}
                    message.metadata['deeplink_data'] = deeplink_data

            res = await on_new_message(message)
            return res

        return super().blueprint(handler)

    def get_metadata(self, request: Request) -> Optional[Dict[Text, Any]]:
        if request.method == "POST":
            # TODO oleksandr: go back to request.json when telebot fixes the problem they created
            # request_dict = request.json  # new version of telebot ruins this dict by injecting its objects into it
            request_dict = ujson.loads(request.body)

            # TODO oleksandr: account for other types of updates too (not all of them have 'message') ?
            telegram_message = request_dict.get('message') or {}
            telegram_from = telegram_message.get('from')
            if telegram_from:
                return {'telegram_from': telegram_from}

        return None
