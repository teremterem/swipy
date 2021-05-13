from sentry_sdk.integrations import boto3

# noinspection PyUnresolvedReferences
dynamodb = boto3.resource('dynamodb')

user_state_machine_table = dynamodb.Table('UserStateMachine')
