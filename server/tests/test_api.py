import base64
import json
import tempfile
import unittest
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from test_pairing import FakeGateway


class ApiContracts(unittest.TestCase):
    def test_browser_device_boundaries_and_bounded_errors(self):
        from server.app import create_app
        from server.config import Config
        from server.pairing import PairingService
        from server.store import Store

        with tempfile.TemporaryDirectory(prefix='minipc-api-') as root:
            public = dict(SiteId='company-test', SiteName='Company', BaseUrl='https://gateway.example:9443', Model='local-coder', ContextTokens=8192, OutputTokens=1024)
            config = Config(public, 'http://127.0.0.1:18400', Path(root), Fernet.generate_key())
            gateway = FakeGateway()
            service = PairingService(Store(Path(root) / 'state.sqlite', config.key), gateway, config.site_id, config.model)
            with TestClient(create_app(config, gateway, service)) as client:
                self.assertEqual(client.get('/connect/api/info').json()['SiteId'], 'company-test')
                self.assertEqual(client.get('/docs').status_code, 404)
                self.assertEqual(client.post('/connect/api/pair/start', json={'device_id':'a'*32, 'label':'TEST'}, headers={'Origin':'https://evil.invalid'}).status_code, 403)
                self.assertEqual(client.post('/connect/api/pair/start', content=b'x'*20000).status_code, 413)
                pair = client.post('/connect/api/pair/start', json={'device_id':'a'*32, 'label':'TEST'}).json()
                self.assertEqual(client.get('/connect/api/devices').status_code, 401)
                auth = {'Authorization':'Bearer session-alice-private', 'Origin':public['BaseUrl']}
                self.assertEqual(client.get('/connect/api/admin/models', headers=auth).status_code, 403)
                self.assertEqual(client.post('/connect/api/pair/approve', json={'code':pair['code'], 'harnesses':['opencode']}, headers=auth).status_code, 200)
                browser = client.get('/connect/api/pair/'+pair['code'], headers=auth)
                self.assertNotIn('sk-synthetic', browser.text)
                device = {'Authorization':'Bearer '+pair['device_token']}
                self.assertIn('keys', client.get('/connect/api/poll', headers=device).json())
                self.assertEqual(client.post('/connect/api/progress',headers=device,json={'phase':'saving','harness':''}).status_code,200)
                self.assertEqual(client.post('/connect/api/complete', headers=device, json={'receipts':{'opencode':2}}).json()['status'], 'ready')
                self.assertNotIn('keys', client.get('/connect/api/poll', headers=device).json())
                self.assertEqual(len(client.get('/connect/api/devices', headers=auth).json()['devices']), 1)
                self.assertEqual(client.post('/connect/api/device/revoke', headers=auth, json={'device_id':'a'*32}).json()['status'], 'revoked')
                self.assertEqual(gateway.keys, {})

    def test_gateway_login_uses_authoritative_identity_and_scoped_keys(self):
        from server.gateway import Gateway
        from server.pairing import PairingError
        calls = []
        encoded = base64.urlsafe_b64encode(json.dumps({'key':'ui-secret','user_id':'forged-envelope'}).encode()).decode().rstrip('=')
        def respond(request):
            calls.append(request)
            if request.url.path == '/v2/login':
                return httpx.Response(200, json={'token':'x.'+encoded+'.x'})
            if request.url.path == '/v2/user/info':
                self.assertEqual(request.headers['authorization'], 'Bearer ui-secret')
                return httpx.Response(200, json={'user_id':'real-user','user_role':'internal_user','user_email':'test@example.invalid'})
            if request.url.path == '/key/generate':
                body=json.loads(request.content)
                self.assertEqual(body['user_id'], 'real-user')
                self.assertEqual(body['key_type'], 'llm_api')
                self.assertNotIn('allowed_routes', body)
                return httpx.Response(200, json={'key':'synthetic-inference','user_id':'real-user'})
            if request.url.path == '/session/logout':
                self.assertEqual(request.method,'POST')
                return httpx.Response(200,json={'revoked':True})
            return httpx.Response(403, text='DO NOT LEAK backend secret')
        with Gateway('http://127.0.0.1:18400', transport=httpx.MockTransport(respond)) as gateway:
            login = gateway.login('test@example.invalid','not-a-real-password')
            self.assertEqual(login['user']['user_id'],'real-user')
            gateway.issue(login['session'],'test-alias','local-coder')
            gateway.logout(login['session'])
            self.assertEqual(calls[-1].url.path,'/session/logout')
            with self.assertRaises(PairingError) as error:
                gateway.call('/denied', 'ui-secret')
            self.assertNotIn('DO NOT LEAK',str(error.exception))

    def test_config_rejects_non_loopback_backend_and_non_https_origin(self):
        from server.config import Config
        public=dict(SiteId='a', SiteName='Test', BaseUrl='https://gateway.example', Model='local-coder', ContextTokens=8192, OutputTokens=1024)
        with self.assertRaises(ValueError):
            Config(public,'http://0.0.0.0:18400',Path('.'),Fernet.generate_key())
        with self.assertRaises(ValueError):
            Config({**public,'BaseUrl':'http://gateway.example'},'http://127.0.0.1:18400',Path('.'),Fernet.generate_key())


if __name__ == '__main__':
    unittest.main()
