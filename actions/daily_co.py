import logging
import os
from pprint import pformat

import aiohttp

logger = logging.getLogger(__name__)

DAILY_CO_BASE_URL = 'https://api.daily.co/v1'
DAILY_CO_API_TOKEN = os.environ['DAILY_CO_API_TOKEN']


async def create_room() -> dict:
    async with aiohttp.ClientSession() as session:  # TODO oleksandr: do I need to cache/reuse these sessions ?
        room_data = {
            'privacy': 'public',
            'properties': {
                'enable_network_ui': False,
                'enable_prejoin_ui': False,
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

    return created_room
