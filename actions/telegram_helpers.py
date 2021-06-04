import os
from typing import Text, Optional

from telebot import TeleBot

SWIPY_TELEGRAM_TOKEN = os.environ['SWIPY_TELEGRAM_TOKEN']


def get_user_profile_photo_file_id(user_id: Text) -> Optional[Text]:
    # TODO oleksandr: create TeleBot only once ?
    telebot = TeleBot(SWIPY_TELEGRAM_TOKEN, threaded=False)

    photos = telebot.get_user_profile_photos(user_id, limit=1)
    if not photos.photos:
        return None

    current_photo_biggest = max(photos.photos[0], key=lambda p: p.file_size, default=None)
    if not current_photo_biggest:
        return None

    # telebot.send_photo(
    #     user_id,
    #     current_photo_biggest.file_id,
    #     caption=f"{current_photo_biggest.file_size} ({current_photo_biggest.width}x{current_photo_biggest.height}) - "
    #             f"{current_photo_biggest.file_id}",
    # )
    return current_photo_biggest.file_id
