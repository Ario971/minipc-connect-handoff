"""User-authorized LiteLLM calls. No master key, cloud fallback or secret logging."""
import base64
import json
from urllib.parse import urlencode
import httpx
from .pairing import PairingError


class Gateway:
    def __init__(self, base_url, transport=None):
        self.http = httpx.Client(base_url=base_url, timeout=25, follow_redirects=False,
                                 trust_env=False, transport=transport)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self.http.close()

    def call(self, path, session=None, body=None, method=None):
        headers = {'Authorization':'Bearer '+session} if session else {}
        try:
            with self.http.stream(method or ('POST' if body is not None else 'GET'), path, headers=headers, json=body) as response:
                if not response.is_success:
                    status = response.status_code if response.status_code in (401,403,409,429) else 502
                    raise PairingError('Gateway request rejected (HTTP '+str(response.status_code)+'). Check account or service status.',status)
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 2*1024*1024:
                        raise PairingError('Gateway response exceeds the safety limit.',502)
                    chunks.append(chunk)
                result = json.loads(b''.join(chunks))
                if not isinstance(result, dict):
                    raise ValueError('Not an object')
                return result
        except (httpx.HTTPError, ValueError):
            raise PairingError('Gateway unavailable or returned an invalid response; no cloud fallback was used.',502) from None

    def identity(self, session):
        result = self.call('/v2/user/info', session)
        if not result.get('user_id') or result.get('user_role') not in ('internal_user','proxy_admin'):
            raise PairingError('This account cannot enroll devices.',403)
        return {field:result.get(field) for field in ('user_id','user_email','user_role')}

    def login(self, email, password):
        result = self.call('/v2/login', body={'username':email,'password':password})
        try:
            encoded = result['token'].split('.')[1]
            claims = json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))
            if claims.get('password_reset_required'):
                raise PairingError('Complete the required password change in the LiteLLM panel first.',403)
            session = claims['key']
            if not isinstance(session,str) or not 1 <= len(session) <= 4096:
                raise ValueError('Invalid session')
        except (ValueError,KeyError,IndexError,TypeError):
            raise PairingError('Unexpected gateway login response.',502) from None
        return {'session':session, 'user':self.identity(session)}

    def issue(self, session, alias, model):
        owner = self.identity(session)['user_id']
        return self.call('/key/generate',session,{'user_id':owner,'key_alias':alias,'models':[model],
            'key_type':'llm_api','duration':'30d','max_parallel_requests':1,'rpm_limit':30,'tpm_limit':60000})

    def owned_keys(self, session, user_id):
        if self.identity(session)['user_id'] != user_id:
            raise PairingError('Wrong account.',403)
        result = []
        for page in range(1,21):
            data = self.call('/key/list?'+urlencode({'user_id':user_id,'return_full_object':'true','page':page,'size':100}),session)
            entries = data.get('keys',[])
            if not isinstance(entries,list) or any(not isinstance(entry,dict) for entry in entries):
                raise PairingError('Unexpected key-list response.',502)
            result.extend(entries)
            if page >= data.get('total_pages',1):
                return result
        raise PairingError('Account key list exceeds the cleanup safety limit.',409)

    def revoke(self, session, hashes):
        if hashes:
            self.call('/key/delete',session,{'keys':hashes})

    def logout(self, session):
        self.call('/session/logout',session,method='POST')

    def models(self, session):
        return self.call('/model/info',session).get('data',[])

    def select_model(self, session, model_id, api_base, upstream_id, api_key, context, output):
        existing = [item for item in self.models(session) if item.get('model_info',{}).get('id') == model_id]
        payload = {'model_name':'local-coder', 'litellm_params':{'model':'openai/'+upstream_id,
            'api_base':api_base,'api_key':api_key or 'unused-local-key','timeout':180,
            'stream_timeout':180,'max_retries':0,'max_tokens':output,'max_parallel_requests':5},
            'model_info':{'id':model_id,'mode':'chat','max_tokens':context,
                'max_input_tokens':context-output,'max_output_tokens':output,
                'input_cost_per_token':0,'output_cost_per_token':0,'supports_function_calling':True}}
        self.call('/model/update' if existing else '/model/new',session,payload)
        return {'saved':True,'model':'local-coder','tool_use_verified':False}
