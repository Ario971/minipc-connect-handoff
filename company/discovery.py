"""Query one administrator-supplied local OpenAI-compatible model service.

No port/LAN scanning, redirects, model download, model start or inference occurs.
"""
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit

MAX_RESPONSE = 1024 * 1024


def _local_address(value):
    address = ipaddress.ip_address(value)
    return (address.is_private or address.is_loopback) and not (
        address.is_link_local or address.is_multicast or address.is_unspecified or address.is_reserved)


def models_url(base_url):
    if not isinstance(base_url, str) or len(base_url) > 1024 or any(ord(c) < 33 for c in base_url):
        raise ValueError('Invalid model service URL')
    parsed = urlsplit(base_url)
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment):
        raise ValueError('Use a local HTTP(S) model URL without embedded credentials')
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('Invalid model service port')
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        if not re.fullmatch(r'[a-zA-Z0-9.-]+', parsed.hostname):
            raise ValueError('Invalid local hostname') from None
    else:
        if not _local_address(parsed.hostname):
            raise ValueError('Model discovery is restricted to the supplied private/loopback service')
    path = parsed.path.rstrip('/')
    if path.endswith('/models'):
        raise ValueError('Enter the API base URL, not its /models resource')
    if not path.endswith('/v1'):
        path += '/v1'
    return urlunsplit((parsed.scheme, parsed.netloc, path + '/models', '', ''))


def parse_models(body):
    data = body.get('data') if isinstance(body, dict) else None
    if not isinstance(data, list) or not 1 <= len(data) <= 256:
        raise ValueError('Model service did not return a bounded OpenAI-compatible model list')
    result = []
    for entry in data:
        model = entry.get('id') if isinstance(entry, dict) else None
        if not isinstance(model, str) or not 1 <= len(model) <= 200 or any(ord(c) < 32 for c in model):
            raise ValueError('Model service returned an invalid model identifier')
        if model not in result:
            result.append(model)
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def discover(base_url, api_key=''):
    url = models_url(base_url)
    parsed = urlsplit(url)
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not _local_address(info[4][0]) for info in addresses):
        raise ValueError('The supplied model hostname must resolve only to private/loopback addresses')
    if not isinstance(api_key, str) or len(api_key) > 4096 or '\r' in api_key or '\n' in api_key:
        raise ValueError('Invalid model API key')
    headers = {'Accept': 'application/json', 'Accept-Encoding': 'identity'}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=8) as response:
            raw = response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as error:
        raise ValueError('Model service returned HTTP ' + str(error.code) + '; check URL and its API credential') from None
    except (OSError, urllib.error.URLError):
        raise ValueError('Cannot reach or verify the supplied model service within 8 seconds') from None
    if len(raw) > MAX_RESPONSE:
        raise ValueError('Model response exceeds the 1 MiB limit')
    try:
        models = parse_models(json.loads(raw))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError('Model service did not return valid JSON') from None
    return {'api_base': url.removesuffix('/models'), 'models': models, 'tool_use_verified': False}
