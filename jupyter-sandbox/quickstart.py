# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START calendar_quickstart]
from __future__ import print_function

import datetime
import os.path
from pprint import pprint

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/gmail.send',
]


def main():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # raise ValueError('needs refresh')
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)

    # Refer to the Python quickstart on how to setup the environment:
    # https://developers.google.com/calendar/quickstart/python
    # Change the scope to 'https://www.googleapis.com/auth/calendar' and delete any
    # stored credentials.

    event = {
        'summary': 'Google I/O 2015',
        # 'location': '800 Howard St., San Francisco, CA 94103',
        'description': 'A chance to hear more about Google\'s developer products.',
        'start': {
            'dateTime': '2021-04-23T01:00:00-07:00',
            'timeZone': 'America/Los_Angeles',
        },
        'end': {
            'dateTime': '2021-04-23T07:00:00-07:00',
            'timeZone': 'America/Los_Angeles',
        },
        # 'recurrence': [
        #     'RRULE:FREQ=DAILY;COUNT=1'
        # ],
        'conferenceData': {
            # 'conferenceId': 'abbadwewf4',
            'createRequest': {
                'requestId': 'abbadwewf4',  # TODO oleksandr: generate new each time
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet',
                },
            },
        },
        'attendees': [
            {
                'email': 'teremswell@gmail.com',
                'responseStatus': 'accepted',
            },
            {
                'email': 'toporok@gmail.com',
                'responseStatus': 'accepted',
            },
        ],
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 10},
            ],
        },
    }

    event = service.events().insert(
        calendarId='primary',
        body=event,
        conferenceDataVersion=1,
        sendUpdates='all',
        sendNotifications=True,
    ).execute()
    pprint(event)
    print('Event created: %s' % (event.get('htmlLink')))

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    print('Getting the upcoming 10 events')
    events_result = service.events().list(calendarId='primary', timeMin=now,
                                          maxResults=10, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        print('No upcoming events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(start, event['summary'])
    print(len(events))


if __name__ == '__main__':
    main()
# [END calendar_quickstart]
