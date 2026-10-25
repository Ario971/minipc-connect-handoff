"""Single-worker, durable device pairing with explicit owner approval."""
import hashlib
import math
import re
import secrets
import threading
import time

HARNESS = frozenset(('opencode', 'claude'))


class PairingError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class PairingService:
    def __init__(self, store, gateway, site_id, model, clock=time.time, capacity=64):
        self.store, self.gateway, self.site_id, self.model = store, gateway, site_id, model
        self.clock, self.capacity = clock, capacity
        self.lock = threading.RLock()
        self.rates = {}
        # An interrupted issuance is not retried: reconcile/revoke its unique aliases.
        for pair in self.store.pairs():
            if pair['status'] == 'issuing':
                pair['expires'] = 0
                self.store.put(pair)

    @staticmethod
    def digest(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def _identity(self, session):
        identity = self.gateway.identity(session)
        if identity.get('user_role') not in ('internal_user', 'proxy_admin'):
            raise PairingError('This account cannot create a device connection.', 403)
        return identity

    def _token(self, token):
        if not isinstance(token, str) or not re.fullmatch(r'mpc_[A-Za-z0-9_-]{43}', token):
            raise PairingError('Invalid device pairing token.', 401)
        pair = self.store.pair(token_hash=self.digest(token))
        if not pair or pair['expires'] <= self.clock():
            raise PairingError('This pairing expired. Start the helper again.', 410)
        return pair

    def _code(self, code):
        if not isinstance(code, str) or not re.fullmatch(r'[A-Z2-9]{10}', code):
            raise PairingError('Invalid pairing code.', 404)
        pair = self.store.pair(code=code)
        if not pair or pair['expires'] <= self.clock():
            raise PairingError('This pairing expired. Start the helper again.', 410)
        return pair

    @staticmethod
    def public(pair):
        return {field: pair.get(field) for field in
                ('code', 'device_id', 'label', 'status', 'expires', 'harnesses', 'phase', 'warning')}

    def start(self, device_id, label, peer):
        if (not isinstance(device_id, str) or not re.fullmatch(r'[a-f0-9]{32}', device_id)
                or not isinstance(label, str) or not 1 <= len(label) <= 64 or any(ord(c) < 32 for c in label)):
            raise PairingError('Invalid device name or identifier.')
        with self.lock:
            now = self.clock()
            self.rates = {key: value for key, value in self.rates.items() if value[0] > now - 60}
            bucket = self.rates.get(peer, [now, 0])
            if bucket[1] >= 8 or (peer not in self.rates and len(self.rates) >= 1024):
                raise PairingError('Too many setup attempts. Wait one minute.', 429)
            bucket[1] += 1
            self.rates[peer] = bucket
            self.cleanup()
            if sum(pair['status'] != 'ready' for pair in self.store.pairs()) >= self.capacity:
                raise PairingError('Setup capacity reached; finish or cancel existing pairings.', 429)
            code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(10))
            token = 'mpc_' + secrets.token_urlsafe(32)
            pair = {'code': code, 'token_hash': self.digest(token), 'device_id': device_id,
                    'label': label, 'status': 'pending', 'expires': now + 600, 'harnesses': [],
                    'keys': [], 'aliases': [], 'phase': 'waiting_for_browser_approval'}
            self.store.put(pair)
            return {**self.public(pair), 'device_token': token}

    def view(self, code, session):
        identity = self._identity(session)
        with self.lock:
            pair = self._code(code)
            device = self.store.device(pair['device_id'])
            if ((pair.get('user_id') and pair['user_id'] != identity['user_id'])
                    or (device and device['user_id'] != identity['user_id'])):
                raise PairingError('This device belongs to a different account.', 403)
            return {**self.public(pair), 'renewal': bool(device and device.get('keys'))}

    def approve(self, code, session, harnesses):
        if (not isinstance(harnesses, list) or not 1 <= len(harnesses) <= 2
                or len(set(harnesses)) != len(harnesses) or not set(harnesses).issubset(HARNESS)):
            raise PairingError('Choose OpenCode, Claude Code or both.')
        identity = self._identity(session)
        with self.lock:
            self.view(code, session)
            pair = self._code(code)
            if pair['status'] in ('approved', 'ready'):
                return self.public(pair)
            if pair['status'] != 'pending':
                raise PairingError('This setup cannot be approved again.', 409)
            if len(self.store.devices(identity['user_id'])) >= 40 and not self.store.device(pair['device_id']):
                raise PairingError('The account has reached the 40-device limit.', 409)
            pair.update(user_id=identity['user_id'], session=session, harnesses=harnesses,
                        aliases=[self.site_id + '-' + code.lower() + '-' + name for name in harnesses],
                        expires=self.clock() + 1800, status='issuing', phase='creating_limited_keys')
            self.store.put(pair)
            try:
                for name, alias in zip(harnesses, pair['aliases']):
                    issued = self.gateway.issue(session, alias, self.model)
                    if not isinstance(issued.get('key'), str) or issued.get('user_id') != identity['user_id']:
                        raise PairingError('Gateway returned an unexpected key identity.', 502)
                    pair['keys'].append({'harness': name, 'key': issued['key'], 'key_alias': alias,
                                         'expires': issued.get('expires')})
                    self.store.put(pair)
                pair.update(status='approved', phase='waiting_for_helper')
                self.store.put(pair)
                return self.public(pair)
            except Exception:
                pair.update(status='failed', phase='key_issuance_failed', expires=self.clock())
                self.store.put(pair)
                self.cleanup()
                raise PairingError('Key creation failed. Only this setup is being cleaned up.', 502) from None

    def poll(self, token):
        with self.lock:
            pair = self._token(token)
            result = self.public(pair)
            if pair['status'] == 'approved':
                result.update(user_id=pair['user_id'], keys=pair['keys'])
            return result

    def progress(self, token, phase, harness=None):
        if phase not in ('downloading', 'verifying', 'testing', 'saving', 'waiting_for_approval') or harness not in (*HARNESS, None):
            raise PairingError('Unknown setup progress.')
        with self.lock:
            pair = self._token(token)
            if pair['status'] not in ('pending', 'approved'):
                raise PairingError('This setup is not running.', 409)
            pair['phase'] = phase + (':' + harness if harness else '')
            self.store.put(pair)

    def complete(self, token, receipts):
        with self.lock:
            pair = self._token(token)
            if pair['status'] == 'ready':
                return self.public(pair)
            if (pair['status'] != 'approved' or not isinstance(receipts, dict)
                    or set(receipts) != set(pair['harnesses'])
                    or any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 160 for value in receipts.values())):
                raise PairingError('Every selected harness needs a completed bounded read-test receipt.')
            previous = self.store.device(pair['device_id']) or {'keys': []}
            old = [item for item in previous['keys'] if item['harness'] in pair['harnesses']]
            keep = [item for item in previous['keys'] if item['harness'] not in pair['harnesses']]
            keys = [{'harness': item['harness'], 'hash': self.digest(item['key']),
                     'alias': item['key_alias'], 'expires': item['expires']} for item in pair['keys']]
            device = {'device_id': pair['device_id'], 'user_id': pair['user_id'], 'label': pair['label'],
                      'keys': keep + keys, 'status': 'ready', 'updated': self.clock(), 'receipts': receipts}
            pair.update(status='ready', phase='ready', keys=[], expires=self.clock()+7*86400, cleanup_keys=[item['hash'] for item in old])
            if not old:
                pair.pop('session', None)
            self.store.commit_device(pair, device)
            self._cleanup_old(pair)
            return self.public(pair)

    def _cleanup_old(self, pair):
        if not pair.get('cleanup_keys'):
            return
        try:
            self.gateway.revoke(pair['session'], pair['cleanup_keys'])
            pair.update(cleanup_keys=[], warning=None)
            pair.pop('session', None)
        except Exception:
            pair['warning'] = 'previous_key_cleanup_pending'
        self.store.put(pair)

    def _revoke_pair(self, pair, session=None):
        credential = session or pair.get('session')
        if not credential or not pair.get('aliases'):
            return
        owned = self.gateway.owned_keys(credential, pair['user_id'])
        targets = [item['token'] for item in owned if item.get('key_alias') in pair['aliases']
                   and item.get('user_id') == pair['user_id']]
        if targets:
            self.gateway.revoke(credential, targets)

    def fail(self, token, reason):
        if reason not in ('client_test_failed', 'cancelled', 'installation_failed'):
            raise PairingError('Unknown setup failure.')
        with self.lock:
            pair = self._token(token)
            if pair['status'] == 'ready':
                return self.public(pair)
            pair.update(status='failed', phase=reason, expires=self.clock())
            self.store.put(pair)
            self.cleanup()
            return {'status': 'failed', 'phase': reason}

    def cleanup(self):
        with self.lock:
            for pair in self.store.pairs():
                if pair['status'] == 'ready':
                    self._cleanup_old(pair)
                    if pair['expires'] <= self.clock() and not pair.get('cleanup_keys'):
                        self.store.delete(pair['code'])
                elif pair['expires'] <= self.clock():
                    try:
                        self._revoke_pair(pair)
                        self.store.delete(pair['code'])
                    except Exception:
                        pair['warning'] = 'cleanup_needs_account_sign_in'
                        self.store.put(pair)

    def devices(self, session):
        owner = self._identity(session)['user_id']
        with self.lock:
            for pair in self.store.pairs():
                if pair.get('user_id') == owner and pair['status'] == 'ready' and pair.get('cleanup_keys'):
                    pair['session'] = session
                    self._cleanup_old(pair)
                if pair.get('user_id') == owner and pair['expires'] <= self.clock() and pair['status'] != 'ready':
                    self._revoke_pair(pair, session)
                    self.store.delete(pair['code'])
            return [{**{k: v for k, v in device.items() if k not in ('keys', 'user_id')},
                     'harnesses': [{'name': item['harness'], 'expires': item['expires']} for item in device['keys']]}
                    for device in self.store.devices(owner)]

    def close_session(self, session):
        self._identity(session)
        with self.lock:
            for pair in self.store.pairs():
                if pair.get('session') != session:
                    continue
                if pair['status'] == 'ready':
                    self._cleanup_old(pair)
                    if pair.get('cleanup_keys'):
                        raise PairingError('Previous-key cleanup is pending; retry sign-out.', 409)
                else:
                    self._revoke_pair(pair, session)
                    self.store.delete(pair['code'])

    def revoke_device(self, device_id, session):
        owner = self._identity(session)['user_id']
        with self.lock:
            device = self.store.device(device_id)
            if not device or device['user_id'] != owner:
                raise PairingError('Device not found for this account.', 404)
            for pair in self.store.pairs():
                if pair['device_id'] == device_id and pair.get('user_id') == owner and pair.get('cleanup_keys'):
                    self.gateway.revoke(session, pair['cleanup_keys'])
                    pair.update(cleanup_keys=[], warning=None)
                    pair.pop('session', None)
                    self.store.put(pair)
                if pair['device_id'] == device_id and pair.get('user_id') == owner and pair['status'] != 'ready':
                    self._revoke_pair(pair, session)
                    self.store.delete(pair['code'])
            self.gateway.revoke(session, [item['hash'] for item in device['keys']])
            device.update(keys=[], status='revoked', updated=self.clock())
            self.store.put_device(device)
            return {'status': 'revoked'}
