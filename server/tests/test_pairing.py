import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.fernet import Fernet


class FakeGateway:
    def __init__(self):
        self.keys = {}
        self.generated = 0
        self.revoked = []

    def identity(self, session):
        if session not in ('session-alice-private', 'session-bob-private', 'session-alice-fresh'):
            raise ValueError('Invalid test session')
        return {'user_id': session.split('-')[1], 'user_role': 'internal_user', 'user_email': 'test@example.invalid'}

    def issue(self, session, alias, model):
        self.generated += 1
        key = 'sk-synthetic-private-' + str(self.generated)
        record = {'key': key, 'key_alias': alias, 'user_id': self.identity(session)['user_id'],
                  'expires': '2099-01-01T00:00:00Z', 'models': [model]}
        self.keys[key] = record
        return record

    def key_hash(self, key):
        import hashlib
        return hashlib.sha256(key.encode()).hexdigest()

    def owned_keys(self, session, user_id):
        assert self.identity(session)['user_id'] == user_id
        return [{**value, 'token': self.key_hash(key)} for key, value in self.keys.items() if value['user_id'] == user_id]

    def revoke(self, session, hashes):
        user = self.identity(session)['user_id']
        for key, value in list(self.keys.items()):
            if self.key_hash(key) in hashes:
                assert value['user_id'] == user
                self.revoked.append(key)
                del self.keys[key]


class PairingContracts(unittest.TestCase):
    def setUp(self):
        self.assertTrue(importlib.util.find_spec('server.pairing') is not None,
                        'Central pairing service has not been implemented')
        from server.pairing import PairingService, PairingError
        from server.store import Store
        self.PairingService, self.PairingError, self.Store = PairingService, PairingError, Store
        self.temporary = tempfile.TemporaryDirectory(prefix='minipc-pairing-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.encryption_key = Fernet.generate_key()
        self.store = Store(self.root / 'state.sqlite', self.encryption_key)
        self.gateway = FakeGateway()
        self.clock = [1000]
        self.service = PairingService(self.store, self.gateway, 'test-site', 'local-coder',
                                      clock=lambda: self.clock[0], capacity=4)

    def start(self, device='a' * 32):
        return self.service.start(device, 'TEST-LAPTOP', '127.0.0.1')

    def approve(self, pair, who='alice', harnesses=None):
        return self.service.approve(pair['code'], 'session-' + who + '-private', harnesses or ['opencode', 'claude'])

    def test_one_use_owner_bound_pair_and_secret_free_browser_status(self):
        pair = self.start()
        browser = self.approve(pair)
        self.assertNotIn('sk-synthetic', json.dumps(browser))
        self.assertNotIn('session-alice', json.dumps(browser))
        helper = self.service.poll(pair['device_token'])
        self.assertEqual(helper['user_id'], 'alice')
        self.assertEqual(len(helper['keys']), 2)
        self.assertNotIn('session-alice', json.dumps(helper))
        self.approve(pair)
        self.assertEqual(self.gateway.generated, 2, 'Approval retry must not issue duplicate keys')
        with self.assertRaises(self.PairingError):
            self.approve(pair, 'bob')
        with self.assertRaises(self.PairingError):
            self.service.poll('mpc-invalid-token')
        result = self.service.complete(pair['device_token'], {'opencode': 12.5, 'claude': 13.2})
        self.assertEqual(result['status'], 'ready')
        self.assertNotIn('keys', self.service.poll(pair['device_token']))

    def test_encrypted_restart_expiry_revokes_only_new_keys(self):
        unrelated = self.gateway.issue('session-alice-private', 'unrelated', 'local-coder')['key']
        pair = self.start()
        self.approve(pair)
        raw = (self.root / 'state.sqlite').read_bytes()
        self.assertNotIn(b'session-alice-private', raw)
        self.assertNotIn(b'sk-synthetic-private', raw)
        restarted = self.PairingService(self.Store(self.root / 'state.sqlite', self.encryption_key),
                                       self.gateway, 'test-site', 'local-coder', clock=lambda: self.clock[0])
        self.clock[0] += 2000
        restarted.cleanup()
        self.assertEqual(list(self.gateway.keys), [unrelated])
        with self.assertRaises(self.PairingError):
            restarted.poll(pair['device_token'])

    def test_failure_preserves_previous_device_until_verified_rotation(self):
        first = self.start()
        self.approve(first, harnesses=['opencode'])
        self.service.complete(first['device_token'], {'opencode': 1.0})
        previous = set(self.gateway.keys)
        replacement = self.start()
        self.approve(replacement, harnesses=['opencode'])
        self.service.fail(replacement['device_token'], 'client_test_failed')
        self.assertEqual(set(self.gateway.keys), previous)
        second = self.start()
        self.approve(second, harnesses=['opencode'])
        self.assertTrue(previous.issubset(self.gateway.keys))
        self.service.complete(second['device_token'], {'opencode': 2.0})
        self.assertTrue(previous.isdisjoint(self.gateway.keys))
        self.assertEqual(len(self.gateway.keys), 1)

    def test_only_owner_may_replace_or_revoke_device(self):
        pair = self.start()
        self.approve(pair)
        self.service.complete(pair['device_token'], {'opencode': 1.0, 'claude': 1.0})
        another = self.start()
        with self.assertRaises(self.PairingError):
            self.approve(another, 'bob')
        with self.assertRaises(self.PairingError):
            self.service.revoke_device('a' * 32, 'session-bob-private')
        self.service.revoke_device('a' * 32, 'session-alice-private')
        self.assertEqual(self.gateway.keys, {})

    def test_capacity_validation_and_required_real_receipts(self):
        for i in range(4):
            self.start(str(i) * 32)
        with self.assertRaises(self.PairingError):
            self.start('f' * 32)
        with self.assertRaises(self.PairingError):
            self.service.start('../escape', 'name', '127.0.0.1')
        self.clock[0] += 601
        self.service.cleanup()
        pair = self.start()
        with self.assertRaises(self.PairingError):
            self.approve(pair, harnesses=['unrecognized'])
        self.approve(pair)
        with self.assertRaises(self.PairingError):
            self.service.complete(pair['device_token'], {'opencode': 1.0})
        self.assertEqual(self.service.poll(pair['device_token'])['status'], 'approved')

    def test_deferred_rotation_cleanup_uses_fresh_owner_session(self):
        first=self.start();self.approve(first,harnesses=['opencode'])
        self.service.complete(first['device_token'],{'opencode':1})
        second=self.start();self.approve(second,harnesses=['opencode'])
        revoke=self.gateway.revoke
        def expired(session,hashes):
            if session=='session-alice-private':raise ValueError('Expired synthetic UI session')
            return revoke(session,hashes)
        self.gateway.revoke=expired
        self.service.complete(second['device_token'],{'opencode':1})
        self.assertEqual(len(self.gateway.keys),2)
        self.service.devices('session-alice-fresh')
        self.assertEqual(len(self.gateway.keys),1)
        self.assertIsNone(self.service.poll(second['device_token'])['warning'])

    def test_own_device_revocation_includes_deferred_previous_keys(self):
        first=self.start();self.approve(first,harnesses=['opencode'])
        self.service.complete(first['device_token'],{'opencode':1})
        second=self.start();self.approve(second,harnesses=['opencode'])
        revoke=self.gateway.revoke
        def expired(session,hashes):
            if session=='session-alice-private':raise ValueError('Expired synthetic UI session')
            return revoke(session,hashes)
        self.gateway.revoke=expired
        self.service.complete(second['device_token'],{'opencode':1})
        self.service.revoke_device('a'*32,'session-alice-fresh')
        self.assertEqual(self.gateway.keys,{})


if __name__ == '__main__':
    unittest.main()
