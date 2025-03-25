from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda
import requests
_LOG = get_logger(__name__)
import json

class ApiHandler(AbstractLambda):

    def validate_request(self, event) -> dict:
        pass
        
    def handle_request(self, event, context):
        """
        Explain incoming event here
        """
        method = event.get('requestContext', {}).get('http', {}).get('method')
        path = event.get('requestContext', {}).get('http', {}).get('path')

        if path == '/weather' and method == 'GET':
            weather = requests.get(
                "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m")

            return {
                        "headers": {
                            "Content-Type": "application/json"
                            },
                        "statusCode": 200,
                        "body": weather.json()
                        }
        else :
            return {
                "statusCode": 400,
                "body": {
                "statusCode": 400,
                "message": f"Bad request syntax or unsupported method. Request path: {path}. HTTP method: {method}"
                },
                "headers": {
                "content-type": "application/json"
                },
                "isBase64Encoded": False
            }
    

HANDLER = ApiHandler()


def lambda_handler(event, context):
    return HANDLER.lambda_handler(event=event, context=context)
