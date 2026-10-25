"""Public site metadata and local-only service configuration."""
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
from cryptography.fernet import Fernet


class Config:
    def __init__(self, public, gateway_url, state, key, managed_model_id=None):
        origin, backend = urlsplit(public['BaseUrl']), urlsplit(gateway_url)
        if (origin.scheme != 'https' or not origin.hostname or origin.username or origin.password
                or origin.path not in ('', '/') or origin.query or origin.fragment):
            raise ValueError('Portal origin must be HTTPS without credentials or path')
        if (backend.scheme != 'http' or backend.hostname != '127.0.0.1' or backend.username
                or backend.password or backend.path or backend.query or backend.fragment or not backend.port):
            raise ValueError('Gateway must be an explicit loopback HTTP port')
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,48}', public['SiteId']) or public['Model'] != 'local-coder':
            raise ValueError('Invalid site/model alias')
        if type(public['ContextTokens']) is not int or type(public['OutputTokens']) is not int:
            raise ValueError('Integer context/output limits required')
        if not 4096 <= public['ContextTokens'] <= 131072 or not 128 <= public['OutputTokens'] <= public['ContextTokens']//4:
            raise ValueError('Invalid context/output limits')
        self.public = {field:public[field] for field in ('SiteId','SiteName','BaseUrl','Model','ContextTokens','OutputTokens')}
        self.site_id, self.model, self.origin = public['SiteId'], public['Model'], public['BaseUrl'].rstrip('/')
        self.gateway_url, self.state, self.key = gateway_url, Path(state), key
        self.managed_model_id = managed_model_id
        Fernet(key)

    @classmethod
    def from_environment(cls):
        data = json.loads(Path(os.environ['MINIPC_PORTAL_CONFIG']).read_text(encoding='utf-8'))
        return cls(data['public'], data['gateway_url'], os.environ['MINIPC_PORTAL_STATE'],
                   os.environ['MINIPC_PORTAL_KEY'].encode(), data.get('managed_model_id'))
