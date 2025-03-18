from commons.log_helper import get_logger
from commons.abstract_lambda import AbstractLambda
import json

_LOG = get_logger('LambdaHandler')

class HelloWorldHandler(AbstractLambda):

    def check_request_validity(self, event) -> dict:
        """
        Validate if the required fields are present in the event.
        """
        if not event.get('requestContext', {}).get('http'):
            return {"error": "Request context or HTTP method missing."}

        if not all(key in event['requestContext']['http'] for key in ['method', 'path']):
            return {"error": "Missing HTTP method or path in event."}

        return {}

    def process_request(self, event, context):
        """
        Process the incoming request and return appropriate response.
        """
        method = event.get('requestContext', {}).get('http', {}).get('method')
        path = event.get('requestContext', {}).get('http', {}).get('path')
        _LOG.info(f"Received request: {method} {path}")

        if path == '/hello' and method == 'GET':
            _LOG.info("Request matched the /hello endpoint")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Hello from Lambda"})
            }
        else:
            _LOG.error("Unrecognized endpoint or method")
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "message": f"Bad request: Method {method} and path {path} not supported."
                })
            }

HANDLER = HelloWorldHandler()

def lambda_handler(event, context):
    """
    The entry point of the Lambda function.

    Args:
        event: The input event from the trigger.
        context: The Lambda execution context.

    Returns:
        The response from the handler.
    """
    _LOG.debug(f"Received event: {event}")
    
    errors = HANDLER.check_request_validity(event)
    if errors:
        _LOG.error(f"Validation failed: {errors['error']}")
        return {
            "statusCode": 400,
            "body": errors.get("error", "Invalid request format.")
        }

    return HANDLER.process_request(event, context)
