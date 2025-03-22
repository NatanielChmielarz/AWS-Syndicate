from tests.test_audit_producer import AuditProducerLambdaTestCase


class TestSuccess(AuditProducerLambdaTestCase):

    def test_success(self):
        self.assertEqual(True,True)

