import logging
import os
from pprint import pformat
from typing import Any, Text, Dict, List

import aiohttp
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

logger = logging.getLogger(__name__)

DAILY_CO_BASE_URL = 'https://api.daily.co/v1'
DAILY_CO_API_TOKEN = os.environ['DAILY_CO_API_TOKEN']


class ActionCreateRoom(Action):

    def name(self) -> Text:
        return 'action_create_room'

    async def run(
            self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        async with aiohttp.ClientSession() as session:
            room_data = {
                'privacy': 'public',
                'properties': {
                    'enable_network_ui': False,
                    'enable_prejoin_ui': True,
                    'enable_new_call_ui': True,
                    'enable_screenshare': True,
                    'enable_chat': True,
                    'start_video_off': False,
                    'start_audio_off': False,
                    'owner_only_broadcast': False,
                    'lang': 'en',
                },
            }
            async with session.post(
                    f"{DAILY_CO_BASE_URL}/rooms",
                    headers={
                        'Authorization': f"Bearer {DAILY_CO_API_TOKEN}",
                    },
                    json=room_data,
            ) as resp:
                created_room = await resp.json()
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('NEW DAILY CO ROOM:\n%s', pformat(created_room))

        dispatcher.utter_template('utter_video_link', tracker, room_link=created_room['url'])

        return []
