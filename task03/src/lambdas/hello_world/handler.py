from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda
import json
_LOG = get_logger(__name__)


class HelloWorld(AbstractLambda):

    def validate_request(self, event) -> dict:
        if event.get('path') == '/hello':
            return {
                "statusCode": 200,
                "body": json.dumps({"statusCode": 200, "message": "Hello from Lambda"})
            }
        else:
            return None
        
    def handle_request(self, event, context):
        """
        Explain incoming event here
        """
        # todo implement business logic
        result =  {
         "statusCode": 200,
         "message": "Hello from Lambda"
        }
        return result
    

HANDLER = HelloWorld()


def lambda_handler(event, context):
    response = HANDLER.validate_request(event)
    if response:
        return response
    return HANDLER.lambda_handler(event=event, context=context)
