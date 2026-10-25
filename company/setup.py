"""Linux administrator entry point. Never installs or starts a model runtime."""
import argparse
import base64
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile

# Avoid importing the standard-library site module with the same filename.
import importlib.util
spec=importlib.util.spec_from_file_location('minipc_site',Path(__file__).with_name('site.py'))
site_module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(site_module)
Site=site_module.Site
from render import render

BUNDLE=Path(__file__).resolve().parent.parent
MARKER='minipc-connect-linux-v2'


def run(args, cwd=None, timeout=120):
    result=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        # Docker errors can interpolate environment credentials. Keep the command result private.
        raise RuntimeError('Command failed: '+args[0]+' (exit '+str(result.returncode)+'). Check service status locally; credentials were not printed.')
    return result.stdout


def write(path, value, mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as handle:
        handle.write(value)
    path.chmod(mode)


def read_settings(path):
    value=json.loads(path.read_text())
    site=Site(**value['site'])
    return value,site,render(site,value['ports'],value['tls'])


def root_for(value, new=False):
    root=Path(value)
    if not root.is_absolute() or root.is_symlink() or root.resolve()!=root or len(root.parts)<3:
        raise ValueError('Use an explicit non-symlink installation directory, e.g. /srv/minipc-connect')
    if new and root.exists():
        raise ValueError('Installation directory already exists; nothing was overwritten')
    if not new and (not (root/'installation.json').is_file() or json.loads((root/'installation.json').read_text()).get('format')!=MARKER):
        raise ValueError('Not a MiniPC Connect installation')
    return root


def prerequisite():
    if sys.platform!='linux' or os.geteuid()!=0:
        raise RuntimeError('Run this administrator setup on Linux with sudo; it does not request remote administrator access')
    if os.uname().machine!='x86_64':
        raise RuntimeError('This tested package targets Linux x86_64 and Windows x64')
    run(['docker','compose','version'],timeout=10)
    run(['docker','info','--format','{{.ServerVersion}}'],timeout=10)


def wizard(path):
    if path.exists():
        raise ValueError('Settings file exists; it was not overwritten')
    site_id=input('Site ID (lowercase letters/digits/hyphens): ').strip()
    name=input('Site display name: ').strip()
    bind=input('MiniPC LAN IPv4 address: ').strip()
    origin=input('HTTPS origin, including port (e.g. https://minipc.company:9443): ').strip()
    networks=input('Explicit approved client IPv4 CIDRs, comma-separated: ').strip().split(',')
    email=input('Your gateway administrator email (not a cloud password): ').strip()
    context=int(input('Per-request context tokens supported by the local server [8192]: ').strip() or '8192')
    output=int(input('Maximum output tokens [1024]: ').strip() or '1024')
    site=Site(site_id,name,origin,bind,[n.strip() for n in networks],email,context,output)
    tls=input('TLS mode: company certificate or internal test CA [company/internal]: ').strip()
    value={'site':site.as_dict(),'ports':{'database':15432,'gateway':18400,'portal':18401},'tls':tls}
    if tls=='company':
        value['tls_files']={name:input('Absolute path to '+name+': ').strip() for name in ('server.crt','server.key','root.crt')}
    render(site,value['ports'],tls)
    write(path,json.dumps(value,indent=2)+'\n')
    print('Settings saved. No services or model runtime were changed.')


def initialize(settings_path,destination):
    prerequisite()
    settings,site,rendered=read_settings(settings_path)
    root=root_for(destination,new=True)
    # Preflight ports before writing anything; never kill another service.
    for host,port in [(site.bind,site.port)]+[('127.0.0.1',p) for p in settings['ports'].values()]:
        with socket.socket() as sock:
            try:sock.bind((host,port))
            except OSError:raise ValueError('Address/port unavailable: '+host+':'+str(port)) from None
    binary=BUNDLE/'windows/MiniPCConnect.exe'
    if not binary.is_file():
        raise ValueError('Use the built portable release ZIP, including windows/MiniPCConnect.exe')
    tls_files={}
    if settings['tls']=='company':
        for name in ('server.crt','server.key','root.crt'):
            source=Path(settings['tls_files'][name])
            if not source.is_file() or source.stat().st_size>128*1024:
                raise ValueError('Missing or oversized TLS file: '+name)
            tls_files[name]=source.read_bytes()
        if tls_files['root.crt'].count(b'-----BEGIN CERTIFICATE-----')!=1 or b'PRIVATE KEY' in tls_files['root.crt']:
            raise ValueError('root.crt must contain exactly one public root certificate')
    root.mkdir(mode=0o755)
    for folder,uid,mode in [('secrets',0,0o700),('data',0,0o755),('data/postgres',70,0o700),('data/portal',1000,0o700),('data/caddy',1000,0o700),('data/caddy-config',1000,0o700),('connect-public',1000,0o755),('portal-service',0,0o755)]:
        path=root/folder;path.mkdir(mode=mode,parents=True,exist_ok=True);os.chown(path,uid,uid)
    # No home IP, home root CA, owner password or previous client keys are copied.
    for name in ('server','company'):
        shutil.copytree(BUNDLE/name,root/'portal-service'/name,ignore=shutil.ignore_patterns('__pycache__','test_*','setup.py','README*','*.zip'))
    shutil.copytree(BUNDLE/'portal',root/'connect-public',dirs_exist_ok=True)
    for tree in (root/'portal-service',root/'connect-public'):
        for path in [tree,*tree.rglob('*')]:
            if path.is_symlink():raise ValueError('Release sources must not contain symbolic links')
            path.chmod(0o755 if path.is_dir() else 0o644)
    write(root/'compose.json',json.dumps(rendered['compose'],indent=2)+'\n',0o644)
    write(root/'litellm.config.json',json.dumps(rendered['config'],indent=2)+'\n',0o644)
    write(root/'portal-service/config.json',json.dumps(rendered['portal'],indent=2)+'\n',0o644)
    write(root/'Caddyfile',rendered['caddy'],0o644)
    password=secrets.token_urlsafe(32)
    write(root/'secrets/database.env','POSTGRES_USER=litellm\nPOSTGRES_DB=litellm\nPOSTGRES_PASSWORD='+password+'\n')
    write(root/'secrets/proxy.env','LITELLM_MASTER_KEY=sk-'+secrets.token_urlsafe(40)+'\nLITELLM_SALT_KEY='+secrets.token_hex(32)+'\nDATABASE_URL=postgresql://litellm:'+password+'@127.0.0.1:'+str(settings['ports']['database'])+'/litellm\n')
    write(root/'secrets/portal.env','MINIPC_PORTAL_KEY='+base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()+'\n')
    if tls_files:
        folder=root/'secrets/tls';folder.mkdir(mode=0o700);os.chown(folder,1000,1000)
        for name,data in tls_files.items():
            path=folder/name;path.write_bytes(data);path.chmod(0o600);os.chown(path,1000,1000)
    write(root/'installation.json',json.dumps({'format':MARKER,**settings},indent=2)+'\n')
    run(['docker','compose','-f','compose.json','config','--quiet'],root)
    print('Created a separate installation at '+str(root)+'. Nothing has been started.')


def api(root,path,body=None,token=None):
    settings=json.loads((root/'installation.json').read_text())
    if not token:
        env=dict(line.split('=',1) for line in (root/'secrets/proxy.env').read_text().splitlines())
        token=env['LITELLM_MASTER_KEY']
    req=urllib.request.Request('http://127.0.0.1:'+str(settings['ports']['gateway'])+path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req,timeout=25) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError('Gateway setup request failed: HTTP '+str(error.code)) from None


def prepare_owner(root):
    state=root/'secrets/owner-invitation.json'
    if state.exists() or (root/'secrets/owner-activated').exists():return
    settings=json.loads((root/'installation.json').read_text())
    user='minipc-'+settings['site']['site_id']+'-owner'
    api(root,'/user/new',{'user_id':user,'user_email':settings['site']['email'],'user_role':'proxy_admin','auto_create_key':False})
    temporary=api(root,'/key/generate',{'user_id':user,'models':[],'duration':'5m','allowed_routes':['/invitation/new'],'key_alias':'temporary-owner-invitation'})['key']
    try:invitation=api(root,'/invitation/new',{'user_id':user},temporary)
    finally:api(root,'/key/delete',{'keys':[temporary]})
    write(state,json.dumps({'user_id':user,'id':invitation['id']})+'\n')


def publish(root):
    settings=json.loads((root/'installation.json').read_text())
    site=Site(**settings['site'])
    rendered=render(site,settings['ports'],settings['tls'])
    ca=root/('data/caddy/caddy/pki/authorities/local/root.crt' if settings['tls']=='internal' else 'secrets/tls/root.crt')
    raw=ca.read_bytes();der=ssl.PEM_cert_to_DER_cert(raw.decode())
    public={**site.public_info(),**rendered['artifacts'],'CAFile':'site-root.crt','CAHash':hashlib.sha256(der).hexdigest()}
    target=root/'connect-public/MiniPCConnect-Windows-x64.zip'
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(BUNDLE/'windows/MiniPCConnect.exe','MiniPCConnect.exe')
        archive.writestr('pilot.json',json.dumps(public))
        archive.writestr('site-root.crt',raw)
        archive.writestr('START-HERE.txt','Extract all files. Ask your administrator to verify/trust the site CA first. Run MiniPCConnect.exe. Sign into the browser portal with your own gateway account and approve this device. Start your harness from the Windows Start menu. No API keys are included in this download.\n')
    target.chmod(0o644)
    (root/'connect-public/SHA256SUMS.txt').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n')
    (root/'connect-public/SHA256SUMS.txt').chmod(0o644)
    print('Portal: '+site.origin+'/connect/')
    print('Public CA SHA-256: '+public['CAHash'])


def start(root):
    run(['docker','compose','-f','compose.json','up','-d'],root,timeout=600)
    for attempt in range(90):
        try:api(root,'/health/readiness');break
        except (RuntimeError,OSError):
            if attempt==89:raise RuntimeError('Gateway did not become ready; no model service was modified') from None
            time.sleep(2)
    prepare_owner(root)
    for attempt in range(20):
        try:publish(root);break
        except FileNotFoundError:
            if attempt==19:raise
            time.sleep(1)
    print('Next: activate-owner to set your private gateway password, then sign into the portal and select the existing local model.')


def activate_owner(root):
    state=json.loads((root/'secrets/owner-invitation.json').read_text())
    password=getpass.getpass('Choose a PRIVATE gateway password (not your email password): ')
    if len(password)<12 or password!=getpass.getpass('Repeat password: '):
        raise ValueError('Passwords must match and contain at least 12 characters')
    onboarding=api(root,'/onboarding/get_token?invite_link='+state['id'])
    encoded=onboarding['token'].split('.')[1]
    key=json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))['key']
    api(root,'/onboarding/claim_token',{'invitation_link':state['id'],'user_id':state['user_id'],'password':password},key)
    (root/'secrets/owner-invitation.json').unlink()
    write(root/'secrets/owner-activated','Owner activated; no password is stored here.\n')
    print('Account activated. Sign in with the administrator email from settings.json and the password you just chose.')


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['wizard','init','start','activate-owner','status','publish'])
    parser.add_argument('--settings',type=Path,default=Path('settings.json'))
    parser.add_argument('--dest',default='/srv/minipc-connect')
    args=parser.parse_args()
    if args.command=='wizard':wizard(args.settings);return
    prerequisite()
    if args.command=='init':initialize(args.settings,args.dest);return
    root=root_for(args.dest)
    if args.command=='start':start(root)
    elif args.command=='activate-owner':activate_owner(root)
    elif args.command=='publish':publish(root)
    else:print(run(['docker','compose','-f','compose.json','ps'],root))


if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError,subprocess.TimeoutExpired) as error:
        print('Setup stopped: '+str(error),file=sys.stderr);sys.exit(1)
