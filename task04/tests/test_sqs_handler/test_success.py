from tests.test_sqs_handler import SqsHandlerLambdaTestCase


class TestSuccess(SqsHandlerLambdaTestCase):

    def test_success(self):
        self.assertEqual(self.HANDLER.handle_request(dict(), dict()), 200)

