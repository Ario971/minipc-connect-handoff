"""Validated, non-secret site settings shared by setup and the portal."""
import ipaddress
import re
from urllib.parse import urlsplit


class Site:
    model_alias = 'local-coder'

    def __init__(self, site_id, name, origin, bind, networks, email, context=8192, output=1024):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,48}', site_id):
            raise ValueError('Site ID must contain lowercase letters, digits and hyphens')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(c) < 32 for c in name):
            raise ValueError('Invalid site display name')
        parsed = urlsplit(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.path not in ('', '/') or parsed.query or parsed.fragment
                or not re.fullmatch(r'[a-zA-Z0-9.-]+', parsed.hostname)):
            raise ValueError('Public origin must be an HTTPS host and port, without credentials or a path')
        port = parsed.port or 443
        if not 1 <= port <= 65535:
            raise ValueError('Invalid HTTPS port')
        address = ipaddress.ip_address(bind)
        if address.version != 4 or address.is_unspecified or address.is_multicast or address.is_link_local:
            raise ValueError('Bind to an explicit IPv4 address of this MiniPC')
        if not isinstance(networks, list) or not 1 <= len(networks) <= 8:
            raise ValueError('Provide one to eight explicitly approved LAN CIDRs')
        parsed_networks = [ipaddress.ip_network(value, strict=False) for value in networks]
        if any(n.version != 4 or n.prefixlen == 0 or n.is_multicast or not n.is_private for n in parsed_networks):
            raise ValueError('Only explicit private/loopback IPv4 network scopes are supported')
        if not any(address in network for network in parsed_networks):
            raise ValueError('The bind address must be in the approved network scope')
        if not isinstance(email, str) or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
            raise ValueError('Provide the administrator login email; this is not Google sign-in')
        if (type(context) is not int or type(output) is not int or not 4096 <= context <= 131072
                or not 128 <= output <= context // 4):
            raise ValueError('Invalid explicit model context/output limits')
        self.site_id, self.name = site_id, name.strip()
        self.origin, self.bind, self.port = origin.rstrip('/'), bind, port
        self.networks = [str(network) for network in parsed_networks]
        self.email, self.context, self.output = email, context, output

    def public_info(self):
        return {'SiteId': self.site_id, 'SiteName': self.name, 'BaseUrl': self.origin,
                'Model': self.model_alias, 'ContextTokens': self.context, 'OutputTokens': self.output}

    def as_dict(self):
        return {'site_id': self.site_id, 'name': self.name, 'origin': self.origin, 'bind': self.bind,
                'networks': self.networks, 'email': self.email, 'context': self.context, 'output': self.output}
