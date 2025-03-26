from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda
import boto3
import json
import uuid
import os
import random
from decimal import Decimal

_LOG = get_logger('ApiHandler-handler')

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

class ApiHandler(AbstractLambda):

    def __init__(self):
        self.cognito = boto3.client('cognito-idp')
        self.dynamodb = boto3.resource('dynamodb')
        self.user_pool_id = os.getenv('cup_id')
        self.client_id = os.getenv('cup_client_id')
        self.tables_table = self.dynamodb.Table(os.environ.get('tables', "test1"))
        self.reservations_table = self.dynamodb.Table(os.environ.get('reservations', "test2"))

    def signup(self, event):
        body = json.loads(event['body'])
        try:
            response = self.cognito.sign_up(
                ClientId=self.client_id,
                Username=body['email'],
                Password=body['password'],
                UserAttributes=[
                    {'Name': 'email', 'Value': body['email']},
                    {'Name': 'given_name', 'Value': body['firstName']},
                    {'Name': 'family_name', 'Value': body['lastName']},
                ],
            )
            if not response['UserConfirmed']:
                self.cognito.admin_confirm_sign_up(
                    UserPoolId=self.user_pool_id,
                    Username=body['email']
                )
            return {'statusCode': 200, 'body': json.dumps({'message': 'Sign-up successful'})}
        except Exception as e:
            return {'statusCode': 400, 'body': json.dumps({'message': 'Bad request', 'error': str(e)})}

    def signin(self, event):
        body = json.loads(event['body'])
        try:
            response = self.cognito.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.client_id,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters={'USERNAME': body['email'], 'PASSWORD': body['password']}
            )
            if 'ChallengeName' in response and response['ChallengeName'] == 'NEW_PASSWORD_REQUIRED':
                new_password = body['password'] + str(random.randrange(1, 100))
                challenge_response = self.cognito.respond_to_auth_challenge(
                    ClientId=self.client_id,
                    ChallengeName='NEW_PASSWORD_REQUIRED',
                    Session=response['Session'],
                    ChallengeResponses={'USERNAME': body['email'], 'NEW_PASSWORD': new_password, 'USER_ID_FOR_SRP': body['email']}
                )
                return {'statusCode': 200, 'body': json.dumps({'accessToken': challenge_response['AuthenticationResult']['AccessToken']})}
            return {'statusCode': 200, 'body': json.dumps(response['AuthenticationResult'])}
        except Exception as e:
            return {'statusCode': 400, 'body': json.dumps({'message': 'Bad request', 'error': str(e)})}

    def get_tables(self, event):
        try:
            response = self.tables_table.scan()
            return {'statusCode': 200, 'body': json.dumps({'tables': response['Items']}, cls=DecimalEncoder)}
        except Exception as e:
            return {'statusCode': 400, 'body': json.dumps({'message': 'Bad request', 'error': str(e)})}

    def create_table(self, event):
        body = json.loads(event['body'])
        try:
            self.tables_table.put_item(
                Item={'id': body['id'], 'number': body['number'], 'places': body['places'], 'isVip': body['isVip'], 'minOrder': body['minOrder']}
            )
            return {'statusCode': 200, 'body': json.dumps({'id': body['id']})}
        except Exception as e:
            return {'statusCode': 400, 'body': json.dumps({'message': 'Bad request', 'error': str(e)})}

    def get_table_by_id(self, event):
        table_id = event['pathParameters']['tableId']
        try:
            response = self.tables_table.get_item(Key={'id': int(table_id)} if table_id.isdigit() else {'id': table_id})
            if 'Item' in response:
                return {'statusCode': 200, 'body': json.dumps(response['Item'], cls=DecimalEncoder)}
            return {'statusCode': 404, 'body': json.dumps({'message': 'Table not found'})}
        except Exception as e:
            return {'statusCode': 400, 'body': json.dumps({'message': 'Bad request', 'error': str(e)})}

    def create_reservation(self, event):
        body = json.loads(event['body'])
        reservation_id = str(uuid.uuid4())
        try:
            table_check_response = self.tables_table.scan(
                FilterExpression="#n = :table_number",
                ExpressionAttributeNames={"#n": "number"},
                ExpressionAttributeValues={":table_number": body['tableNumber']}
            )
            if not table_check_response['Items']:
                return {'statusCode': 400, 'body': json.dumps({'message': f'Table with number {body["tableNumber"]} does not exist.'})}

            existing_reservations = self.reservations_table.query(
                IndexName="tableNumber-date-index",
                KeyConditionExpression="tableNumber = :tn AND #d = :date",
                ExpressionAttributeNames={"#d": "date"},
                ExpressionAttributeValues={":tn": body['tableNumber'], ":date": body['date']}
            )
            for reservation in existing_reservations['Items']:
                if body['slotTimeStart'] < reservation['slotTimeEnd'] and body['slotTimeEnd'] > reservation['slotTimeStart']:
                    return {'statusCode': 400, 'body': json.dumps({'message': 'Time conflict: The table is already reserved for this time slot.'})}

            self.reservations_table.put_item(
                Item={'id': reservation_id, 'tableNumber': body['tableNumber'], 'clientName': body['clientName'],
                      'phoneNumber': body['phoneNumber'], 'date': body['date'], 'slotTimeStart': body['slotTimeStart'],
                      'slotTimeEnd': body['slotTimeEnd']}
            )
            return {'statusCode': 200, 'body': json.dumps({'reservationId': reservation_id})}
        except Exception as e:
            return {'statusCode': 400, 'body': json.dumps({'message': 'Bad request', 'error': str(e)})}

    def get_reservations(self, event):
        try:
            response = self.reservations_table.scan()
            return {'statusCode': 200, 'body': json.dumps({'reservations': response['Items']}, cls=DecimalEncoder)}
        except Exception as e:
            return {'statusCode': 400, 'body': json.dumps({'message': 'Bad request', 'error': str(e)})}

    def validate_request(self, event) -> dict:
        if 'body' not in event:
            return {'statusCode': 400, 'body': json.dumps({'message': 'Missing request body'})}
        try:
            json.loads(event['body'])
        except json.JSONDecodeError:
            return {'statusCode': 400, 'body': json.dumps({'message': 'Invalid JSON format'})}
        return {'statusCode': 200, 'body': json.dumps({'message': 'Valid request'})}

    def handle_request(self, event, context):
        route_key = f"{event['httpMethod']} {event['resource']}"
        if route_key == 'POST /signup':
            return self.signup(event)
        elif route_key == 'POST /signin':
            return self.signin(event)
        elif route_key == 'GET /tables':
            return self.get_tables(event)
        elif route_key == 'POST /tables':
            return self.create_table(event)
        elif route_key == 'GET /tables/{tableId}':
            return self.get_table_by_id(event)
        elif route_key == 'POST /reservations':
            return self.create_reservation(event)
        elif route_key == 'GET /reservations':
            return self.get_reservations(event)
        return {'statusCode': 400, 'body': json.dumps({'message': 'Invalid route'})}

HANDLER = ApiHandler()

def lambda_handler(event, context):
    return HANDLER.handle_request(event, context)
