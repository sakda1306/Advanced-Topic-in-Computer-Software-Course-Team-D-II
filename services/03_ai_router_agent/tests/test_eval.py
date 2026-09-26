import unittest

from eval_routes import evaluate


class EvalTests(unittest.IsolatedAsyncioTestCase):
    async def test_forty_cases_through_router(self):
        report = await evaluate()
        self.assertEqual(report["total"], 40)
        self.assertEqual(report["correct"], 40, report["failures"])
