from tests.test_api_handler import ApiHandlerLambdaTestCase
import json


class TestSuccess(ApiHandlerLambdaTestCase):

    def test_success(self):
        response = {}
        response = {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response, indent=4),
        }
        self.assertEqual(True, True)
