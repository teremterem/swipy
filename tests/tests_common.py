all_expected_user_states = [
    'new',
    'wants_chitchat',
    'ok_to_chitchat',
    'waiting_partner_confirm',
    'asked_to_join',
    'asked_to_confirm',
    'roomed',
    'rejected_join',
    'rejected_confirm',
    'do_not_disturb',
    'bot_blocked',
    'user_banned',
]

all_expected_user_state_machine_triggers = [
    'request_chitchat',
    'become_ok_to_chitchat',
    'become_do_not_disturb',
    'wait_for_partner_to_confirm',
    'become_asked_to_join',
    'become_asked_to_confirm',
    'join_room',
    'reject',
]
