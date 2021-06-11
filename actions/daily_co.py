import logging
import os
from pprint import pformat
from typing import Dict, Text, Any

import aiohttp

from actions.utils import SwiperDailyCoError

logger = logging.getLogger(__name__)

DAILY_CO_BASE_URL = os.getenv('DAILY_CO_BASE_URL', 'https://api.daily.co/v1')
DAILY_CO_API_TOKEN = os.environ['DAILY_CO_API_TOKEN']


async def create_room(sender_id: Text) -> Dict[Text, Any]:
    # TODO oleksandr: do I need to reuse ClientSession instance ? what should be its lifetime ?
    async with aiohttp.ClientSession() as session:
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
            resp_json = await resp.json()

    # TODO oleksandr: change log level back to DEBUG when you decide how to identify and react to failures
    if logger.isEnabledFor(logging.INFO):
        logger.info('NEW DAILY CO ROOM (sender_id=%r):\n%s', sender_id, pformat(resp_json))

    if not resp_json.get('url'):
        raise SwiperDailyCoError(repr(resp_json))

    return resp_json
