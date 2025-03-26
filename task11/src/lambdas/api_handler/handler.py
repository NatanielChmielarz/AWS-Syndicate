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
        return super().default(obj)


class ApiHandler(AbstractLambda):
    def __init__(self):
        self.cognito = boto3.client('cognito-idp')
        self.dynamodb = boto3.resource('dynamodb')
        self.user_pool_id = os.getenv('cup_id')
        self.client_id = os.getenv('cup_client_id')
        self.tables_table = self._get_table('tables', 'test1')
        self.reservations_table = self._get_table('reservations', 'test2')
    
    def _get_table(self, env_var, default):
        return self.dynamodb.Table(os.environ.get(env_var, default))
    
    def _json_response(self, status_code, body):
        return {
            'statusCode': status_code,
            'body': json.dumps(body, cls=DecimalEncoder),
            'isBase64Encoded': False
        }

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
            _LOG.info(f'Sign-up response: {response}')
            
            if not response.get('UserConfirmed'):
                confirm_resp = self.cognito.admin_confirm_sign_up(
                    UserPoolId=self.user_pool_id, Username=body['email']
                )
                _LOG.info(f'Confirm response: {confirm_resp}')
                response['UserConfirmed'] = True
            
            return self._json_response(200, {'message': 'Sign-up successful', 'body': response})
        except Exception as e:
            return self._json_response(400, {'message': 'Bad request', 'error': str(e)})

    def signin(self, event):
        body = json.loads(event['body'])
        auth_params = {'USERNAME': body['email'], 'PASSWORD': body['password']}
        
        try:
            response = self.cognito.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.client_id,
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters=auth_params
            )
            _LOG.info(f'Authentication response: {response}')
            
            if response:
                return self._json_response(200, {"idToken": response['AuthenticationResult']['IdToken']})
            else: 
                return self._json_response(200, {"idToken": None})
        except Exception as e:
            _LOG.error(f'Error in signin: {e}')
            return self._json_response(400, {'message': 'Bad request', 'error': str(e)})

    def get_tables(self, event):
        try:
            response = self.tables_table.scan()
            return self._json_response(200, {'tables': response['Items']})
        except Exception as e:
            return self._json_response(400, {'message': 'Bad request', 'error': str(e)})

    def create_table(self, event):
        body = json.loads(event['body'])
        try:
            self.tables_table.put_item(Item=body)
            return self._json_response(200, {'id': body['id']})
        except Exception as e:
            return self._json_response(400, {'message': 'Bad request', 'error': str(e)})

    def get_table_by_id(self, table_id):
        try:
            response = self.tables_table.get_item(Key={'id': int(table_id)})
            if 'Item' in response:
                return self._json_response(200, response['Item'])
            return self._json_response(404, {'message': 'Table not found'})
        except Exception as e:
            return self._json_response(400, {'message': 'Bad request', 'error': str(e)})

    def create_reservation(self, event):
        body = json.loads(event['body'])
        reservation_id = str(uuid.uuid4())

        try:
            existing_reservations = self.reservations_table.scan(
                FilterExpression='#tn = :table_number AND #d = :date',
                ExpressionAttributeNames={'#tn': 'tableNumber', '#d': 'date'},
                ExpressionAttributeValues={':table_number': body['tableNumber'], ':date': body['date']}
            )
            
            for res in existing_reservations['Items']:
                if body['slotTimeStart'] < res['slotTimeEnd'] and body['slotTimeEnd'] > res['slotTimeStart']:
                    return self._json_response(400, {'message': 'Time conflict: Table is already reserved.'})
            
            self.reservations_table.put_item(Item={**body, 'id': reservation_id})
            return self._json_response(200, {'reservationId': reservation_id})
        except Exception as e:
            return self._json_response(400, {'message': 'Bad request', 'error': str(e)})

    def get_reservations(self, event):
        try:
            response = self.reservations_table.scan()
            return self._json_response(200, {'reservations': response['Items']})
        except Exception as e:
            return self._json_response(400, {'message': 'Bad request', 'error': str(e)})

    def handle_request(self, event, context):
        routes = {
            ('POST', '/signup'): self.signup,
            ('POST', '/signin'): self.signin,
            ('GET', '/tables'): self.get_tables,
            ('POST', '/tables'): self.create_table,
            ('POST', '/reservations'): self.create_reservation,
            ('GET', '/reservations'): self.get_reservations
        }
        route_key = (event['httpMethod'], event.get('resource'))
        
        handler = routes.get(route_key, lambda _: self._json_response(400, {'message': 'Invalid route'}))
        return handler(event)


HANDLER = ApiHandler()

def lambda_handler(event, context):
    return HANDLER.handle_request(event, context)
