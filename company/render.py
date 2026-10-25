"""Pure, secret-free Linux deployment templates."""
import copy
import json
from pathlib import Path

IMAGES = {
    'proxy':'ghcr.io/berriai/litellm-database@sha256:87a881738240d0458a47588dd45cd819b00966ae3565786a7818e6d17d837921',
    'database':'postgres@sha256:f4610795587492cd4fb887c2dc3de301b813278bb6f616992061141b5f15ac36',
    'https':'caddy@sha256:eb4d35b7452d1ab6171fbdbe8d9275b2301dad6dad92115d91e19fb9b24d510f',
}


def render(site, ports, tls):
    if set(ports)!= {'database','gateway','portal'} or any(type(p) is not int or not 1024<=p<=65535 for p in ports.values()) or len(set([*ports.values(),site.port]))!=4:
        raise ValueError('Choose distinct unprivileged internal and HTTPS ports')
    if tls not in ('internal','company'):
        raise ValueError('TLS must be internal or company; plaintext is not supported')
    components=json.loads(Path(__file__).with_name('components.json').read_text())
    config=copy.deepcopy(components['settings'])
    config['general_settings']['store_model_in_db']=True
    config['general_settings']['global_max_parallel_requests']=5
    common={'network_mode':'host','read_only':True,'cap_drop':['ALL'],'security_opt':['no-new-privileges:true'],
            'restart':'unless-stopped','logging':{'driver':'local','options':{'max-size':'10m','max-file':'2'}}}
    db,proxy,portal=ports['database'],ports['gateway'],ports['portal']
    services={
        'database':{**common,'image':IMAGES['database'],'user':'70:70','command':['postgres','-p',str(db),'-c','listen_addresses=127.0.0.1','-c','shared_buffers=128MB','-c','max_connections=30'],
            'env_file':['./secrets/database.env'],'volumes':['./data/postgres:/var/lib/postgresql/data'],
            'tmpfs':['/tmp:size=64m,mode=1777','/var/run/postgresql:size=16m,uid=70,gid=70,mode=0700'],
            'mem_limit':'512m','cpus':'1.0','pids_limit':100,
            'healthcheck':{'test':['CMD','pg_isready','-h','127.0.0.1','-p',str(db),'-U','litellm','-d','litellm'],'interval':'5s','timeout':'3s','retries':12}},
        'proxy':{**common,'image':IMAGES['proxy'],'user':'1000:1000','command':['--config','/app/site-config.json','--host','127.0.0.1','--port',str(proxy),'--num_workers','1'],
            'env_file':['./secrets/proxy.env'],'environment':{'HOME':'/tmp','XDG_CACHE_HOME':'/tmp/cache','LITELLM_LOG':'WARNING','LITELLM_LOCAL_MODEL_COST_MAP':'True','LITELLM_TELEMETRY':'False','DO_NOT_TRACK':'1','STORE_MODEL_IN_DB':'True','PROXY_BASE_URL':site.origin,'ROOT_REDIRECT_URL':'/connect/'},
            'volumes':['./litellm.config.json:/app/site-config.json:ro'],'tmpfs':['/tmp:size=256m,mode=1777,uid=1000,gid=1000'],
            'mem_limit':'2g','cpus':'2.0','pids_limit':160,'depends_on':{'database':{'condition':'service_healthy'}},
            'healthcheck':{'test':['CMD','python','-c',f"import urllib.request; urllib.request.urlopen('http://127.0.0.1:{proxy}/health/readiness',timeout=3)"],'interval':'10s','timeout':'5s','retries':18,'start_period':'30s'}},
        'portal':{**common,'image':IMAGES['proxy'],'entrypoint':['python','-m','uvicorn'],
            'command':['server.app:create_app','--factory','--host','127.0.0.1','--port',str(portal),'--workers','1','--no-access-log','--no-proxy-headers'],
            'user':'1000:1000','working_dir':'/portal','env_file':['./secrets/portal.env'],
            'environment':{'PYTHONDONTWRITEBYTECODE':'1','MINIPC_PORTAL_CONFIG':'/portal/config.json','MINIPC_PORTAL_STATE':'/state'},
            'volumes':['./portal-service:/portal:ro','./data/portal:/state'],'tmpfs':['/tmp:size=16m,mode=1777'],
            'mem_limit':'384m','cpus':'0.5','pids_limit':64,'depends_on':{'proxy':{'condition':'service_healthy'}}},
        'https':{**common,'image':IMAGES['https'],'user':'1000:1000',
            'volumes':['./Caddyfile:/etc/caddy/Caddyfile:ro','./data/caddy:/data','./data/caddy-config:/config','./connect-public:/srv/connect:ro']+(['./secrets/tls:/tls:ro'] if tls=='company' else []),
            'tmpfs':['/tmp:size=16m,mode=1777'],'mem_limit':'128m','cpus':'0.5','pids_limit':50,'depends_on':{'proxy':{'condition':'service_healthy'}}},
    }
    caddy='''{
    admin off
    auto_https disable_redirects
    skip_install_trust
    servers {
        protocols h1 h2
    }
}
'''+site.origin+''' {
    bind '''+site.bind+'''
    tls '''+('internal' if tls=='internal' else '/tls/server.crt /tls/server.key')+'''
    @outside not remote_ip '''+' '.join(site.networks)+''' 127.0.0.1/32
    respond @outside "Approved LAN only" 403
    request_body {
        max_size 2MB
    }
    header {
        -Server
        X-Content-Type-Options nosniff
        Referrer-Policy no-referrer
    }
    handle /connect {
        redir /connect/ 308
    }
    handle /connect/api/* {
        reverse_proxy 127.0.0.1:'''+str(portal)+''' {
            header_up X-MiniPC-Client {remote_host}
        }
    }
    handle_path /connect/* {
        root * /srv/connect
        header {
            Content-Security-Policy "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
            X-Frame-Options DENY
            Cache-Control no-cache
        }
        file_server
    }
    handle {
        reverse_proxy 127.0.0.1:'''+str(proxy)+''' {
            flush_interval -1
        }
    }
}
'''
    return {'compose':{'name':'minipc-'+site.site_id,'services':services},'config':config,'caddy':caddy,
            'portal':{'public':site.public_info(),'gateway_url':f'http://127.0.0.1:{proxy}','managed_model_id':'minipc-'+site.site_id+'-model'},
            'artifacts':components['artifacts']}
