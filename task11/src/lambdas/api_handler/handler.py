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
        email = body.get('email')
        password = body.get('password')
        _LOG.info("Preparing signup. Email: %s", email)

        if not email or not password:
            _LOG.error("Signup failed. Missing email or password.")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({'message': 'Missing email or password in signup.'})
            }

        try:
            _LOG.info("Attempting sign_up with Cognito. Email: %s", email)
            self.cognito.sign_up(
                ClientId=self.client_id,
                Username=email,
                Password=password,
                UserAttributes=[{'Name': 'email', 'Value': email}]
            )
            _LOG.info("Sign_up call succeeded. Now confirming sign_up in admin mode.")
            self.cognito.admin_confirm_sign_up(
                UserPoolId=self.user_pool_id,
                Username=email
            )
        except Exception as e:
            _LOG.error(f"Sign up error for email '{email}': {str(e)}")
            _LOG.exception(e)
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    'message': f'Cannot create user {email}. Error: {str(e)}'
                })
            }

        _LOG.info("User %s was created and confirmed successfully.", email)
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({'message': f'User {email} was created.'})
        }

    def signin(self, event):
        body = json.loads(event.get('body', '{}'))
        email = body.get('email')
        password = body.get('password')
        _LOG.info("Preparing signin. Email: %s", email)

        if not email or not password:
            _LOG.error("Signin failed. Missing email or password.")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({'message': 'Missing email or password in signin.'})
            }

        try:
            _LOG.info("Attempting admin_initiate_auth for email: %s", email)
            auth_result = self.cognito.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.client_id,
                AuthFlow='ADMIN_USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': email,
                    'PASSWORD': password
                }
            )

            _LOG.info("admin_initiate_auth response: %s", auth_result)

            if auth_result and 'AuthenticationResult' in auth_result:
                id_token = auth_result['AuthenticationResult'].get('IdToken')
                _LOG.info("Signin success for user: %s", email)
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"accessToken": id_token})
                }
            else:
                _LOG.error("Signin failed. AuthenticationResult missing or invalid.")
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({'message': 'Unable to authenticate user.'})
                }
        except self.cognito.exceptions.NotAuthorizedException:
            return {
                "statusCode": 401,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({'message': 'Incorrect email or password'})
            }
        except self.cognito.exceptions.UserNotFoundException:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({'message': 'User not found'})
            }
        except Exception as e:
            _LOG.error(f"Sign in error for email '{email}': {str(e)}")
            _LOG.exception(e)
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({'message': 'Invalid login.'})
            }

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
