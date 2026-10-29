import os, tempfile, unittest
from concurrent.futures import ThreadPoolExecutor
from smartdialer.core import SmartDialer

class SmartDialerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = SmartDialer(os.path.join(self.tmp.name, 'test.db'), seed_demo=False)
        self.app.seed_demo(agents=2, borrowers=5)
    def tearDown(self): self.tmp.cleanup()

    def test_progressive_never_exceeds_available_agents(self):
        r = self.app.dial('progressive', requested=99)
        self.assertEqual(r['approved'], 2)
        s = self.app.state()
        self.assertEqual(sum(a['state'] != 'AVAILABLE' for a in s['agents']), 2)
    def test_second_dial_has_no_available_agents(self):
        self.app.dial('progressive', requested=2)
        r = self.app.dial('progressive', requested=2)
        self.assertEqual(r['approved'], 0)
    def test_duplicate_provider_event_is_idempotent(self):
        call = self.app.dial()['calls'][0]
        a = self.app.provider_event(call['call_id'], 'FAILED', 'same-event')
        b = self.app.provider_event(call['call_id'], 'FAILED', 'same-event')
        self.assertTrue(a['accepted']); self.assertTrue(b['duplicate'])
        self.assertEqual(self.app.state()['metrics']['failed_calls'], 1)
    def test_terminal_call_cannot_be_reopened_by_late_event(self):
        call = self.app.dial()['calls'][0]
        self.app.provider_event(call['call_id'], 'FAILED', 'failed-event')
        late = self.app.provider_event(call['call_id'], 'ANSWERED', 'late-answer')
        self.assertTrue(late['stale'])
        self.assertEqual(next(c for c in self.app.state()['calls'] if c['id']==call['call_id'])['state'], 'FAILED')
    def test_failed_call_releases_agent(self):
        call = self.app.dial()['calls'][0]
        self.app.provider_event(call['call_id'], 'FAILED', 'failed-event')
        self.assertEqual(self.app.state()['metrics']['available_agents'], 2)
    def test_predictive_request_is_safety_capped(self):
        r = self.app.dial('predictive', requested=50)
        self.assertLessEqual(r['approved'], 2)

    def test_out_of_order_events_do_not_reopen_terminal_call(self):
        call = self.app.dial()["calls"][0]
        first = self.app.provider_event(call["call_id"], "COMPLETED", "completed-first")
        late = self.app.provider_event(call["call_id"], "ANSWERED", "answered-late")
        self.assertTrue(first["accepted"])
        self.assertTrue(late["stale"])
        row = next(c for c in self.app.state()["calls"] if c["id"] == call["call_id"])
        self.assertEqual(row["state"], "COMPLETED")

    def test_provider_outage_releases_reserved_agents(self):
        result = self.app.simulate("outage", requested=2, provider="B")
        self.assertEqual(result["dial"]["approved"], 2)
        self.assertEqual(self.app.state()["metrics"]["available_agents"], 2)
        self.assertEqual(self.app.state()["metrics"]["failed_calls"], 2)

    def test_agent_drop_fails_setup_call_and_requeues_borrower(self):
        call = self.app.dial()['calls'][0]
        result = self.app.simulate_agent_drop(1)
        self.assertEqual(result['count'], 1)
        state = self.app.state()
        row = next(c for c in state['calls'] if c['id'] == call['call_id'])
        self.assertEqual(row['state'], 'FAILED')
        borrower = next(b for b in state['borrowers'] if b['id'] == call['borrower_id'])
        self.assertEqual(borrower['state'], 'QUEUED')

    def test_recovery_releases_stale_setup_call(self):
        call = self.app.dial()['calls'][0]
        with self.app._connect() as con:
            con.execute("UPDATE calls SET updated_at=0 WHERE id=?", (call['call_id'],))
        result = self.app.recover_stale_calls(stale_seconds=1)
        self.assertEqual(result['count'], 1)
        state = self.app.state()
        self.assertEqual(next(c for c in state['calls'] if c['id'] == call['call_id'])['state'], 'FAILED')
        self.assertEqual(state['metrics']['available_agents'], 2)

    def test_mock_providers_have_distinct_profiles(self):
        from smartdialer.providers import get_provider
        a = get_provider('A').describe()
        b = get_provider('B').describe()
        self.assertLess(a['simulated_latency_ms'], b['simulated_latency_ms'])
        self.assertLess(a['configured_failure_rate'], b['configured_failure_rate'])
        self.assertGreater(b['duplicate_event_rate'], a['duplicate_event_rate'])

    def test_concurrent_workers_do_not_double_reserve_agent(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.app.dial('progressive', requested=1), range(8)))
        created = [call for result in results for call in result['calls']]
        self.assertEqual(len(created), 2)
        self.assertEqual(len({call['agent_id'] for call in created}), len(created))

if __name__ == '__main__': unittest.main()
