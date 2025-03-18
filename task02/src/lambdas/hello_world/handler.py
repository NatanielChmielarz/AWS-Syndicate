from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda
import json


class HelloWorldHandler(AbstractLambda):

    def process_request(self, event, context):
        """
        Process the incoming request and return appropriate response.
        """
        method = event.get('requestContext', {}).get('http', {}).get('method')
        path = event.get('requestContext', {}).get('http', {}).get('path')

        if path == '/hello' and method == 'GET':
            return {
                "statusCode": 200,
                "body": json.dumps({"statusCode": 200,"message": "Hello from Lambda"})
            }
        else:
            return {
                "statusCode": 400,
                "body": json.dumps({"statusCode": 400,
                    "message": f"Bad request syntax or unsupported method. Request path: {path}. HTTP method: {method}"
                })
            }

HANDLER = HelloWorldHandler()

def lambda_handler(event, context):
    return HANDLER.process_request(event, context)
