import unittest
import importlib
from tests import ImportFromSourceContext

with ImportFromSourceContext():
    LAMBDA_HANDLER = importlib.import_module("lambdas.api_handler.handler")


class ApiHandlerLambdaTestCase(unittest.TestCase):
    """Common setups for this lambda"""

    def setUp(self) -> None:
        self.HANDLER = LAMBDA_HANDLER.ApiHandler()
