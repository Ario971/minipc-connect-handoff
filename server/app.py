"""Central browser/device API. One worker; LiteLLM remains identity authority."""
import asyncio
from contextlib import asynccontextmanager
import time
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr
from .config import Config
from .gateway import Gateway
from .pairing import PairingError, PairingService
from .store import Store


class Login(BaseModel):
    email: str = Field(min_length=3,max_length=254)
    password: SecretStr = Field(min_length=1,max_length=1024)


class Start(BaseModel):
    device_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    label: str = Field(min_length=1,max_length=64)


class Approve(BaseModel):
    code: str = Field(pattern=r'^[A-Z2-9]{10}$')
    harnesses: list[str] = Field(min_length=1,max_length=2)


class Progress(BaseModel):
    phase: str = Field(max_length=64)
    harness: str = Field(default='',max_length=16)


class Complete(BaseModel):
    receipts: dict[str,float]


class Fail(BaseModel):
    reason: str = Field(max_length=64)


class Device(BaseModel):
    device_id: str = Field(pattern=r'^[a-f0-9]{32}$')


class Discovery(BaseModel):
    base_url: str = Field(min_length=1,max_length=1024)
    api_key: SecretStr = Field(default='',max_length=4096)


class Selection(Discovery):
    model_id: str = Field(min_length=1,max_length=200)


class Boundary:
    """Bound bodies before parsing; reject foreign browser origins."""
    def __init__(self, app, origin):
        self.app, self.origin = app, origin

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope,receive,send)
        headers = dict(scope.get('headers',[]))
        origin = headers.get(b'origin',b'').decode('latin-1')
        if origin and origin != self.origin:
            return await JSONResponse({'error':'Cross-origin request refused.'},403)(scope,receive,send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body',b''))
            if len(body)>16384:
                return await JSONResponse({'error':'Request too large.'},413)(scope,receive,send)
            if not message.get('more_body'):
                break
        async def replay():
            return {'type':'http.request','body':bytes(body),'more_body':False}
        async def safe_send(message):
            if message['type']=='http.response.start':
                message['headers'] += [(b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer')]
            await send(message)
        await self.app(scope,replay,safe_send)


def create_app(config=None,gateway=None,service=None):
    config = config or Config.from_environment()
    owned_gateway = gateway is None
    gateway = gateway or Gateway(config.gateway_url)
    service = service or PairingService(Store(config.state/'state.sqlite',config.key),gateway,config.site_id,config.model)
    rates = {}

    @asynccontextmanager
    async def lifespan(_):
        async def reap():
            while True:
                await asyncio.to_thread(service.cleanup)
                await asyncio.sleep(30)
        task = asyncio.create_task(reap())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            if owned_gateway:
                gateway.close()

    app = FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.add_middleware(Boundary,origin=config.origin)

    @app.exception_handler(PairingError)
    async def pairing_error(_,error):
        return JSONResponse({'error':str(error)},error.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_,error):
        # Validation details can contain a raw password or upstream key.
        return JSONResponse({'error':'Invalid or missing request fields.'},422)

    def token(request):
        value=request.headers.get('authorization','')
        if not value.startswith('Bearer ') or not 1 <= len(value[7:]) <= 4096 or any(ord(c)<33 for c in value[7:]):
            raise PairingError('Sign in first.',401)
        return value[7:]

    def administrator(request):
        value=token(request)
        if gateway.identity(value)['user_role'] != 'proxy_admin':
            raise PairingError('Administrator permission required.',403)
        return value

    def peer(request):
        # Caddy overwrites this header; this server listens only on loopback.
        return request.headers.get('x-minipc-client',request.client.host if request.client else 'unknown')[:80]

    def login_limit(request):
        now=time.monotonic()
        for key in list(rates):
            if now-rates[key][0]>=60:
                del rates[key]
        key=peer(request)
        if key not in rates and len(rates)>=1024:
            raise PairingError('Sign-in capacity reached; try later.',429)
        entry=rates.setdefault(key,[now,0])
        entry[1]+=1
        if entry[1]>8:
            raise PairingError('Too many sign-in attempts. Wait one minute.',429)

    prefix='/connect/api'

    @app.get(prefix+'/info')
    def info():
        return {**config.public,'ManagedModels':bool(config.managed_model_id)}

    @app.post(prefix+'/login')
    def login(body:Login,request:Request):
        login_limit(request)
        return gateway.login(body.email,body.password.get_secret_value())

    @app.get(prefix+'/me')
    def me(request:Request):
        return gateway.identity(token(request))

    @app.post(prefix+'/pair/start')
    def start(body:Start,request:Request):
        return service.start(body.device_id,body.label,peer(request))

    @app.get(prefix+'/pair/{code}')
    def view(code:str,request:Request):
        return service.view(code,token(request))

    @app.post(prefix+'/pair/approve')
    def approve(body:Approve,request:Request):
        return service.approve(body.code,token(request),body.harnesses)

    @app.get(prefix+'/poll')
    def poll(request:Request):
        return service.poll(token(request))

    @app.post(prefix+'/progress')
    def progress(body:Progress,request:Request):
        return service.progress(token(request),body.phase,body.harness or None)

    @app.post(prefix+'/complete')
    def complete(body:Complete,request:Request):
        return service.complete(token(request),body.receipts)

    @app.post(prefix+'/fail')
    def fail(body:Fail,request:Request):
        return service.fail(token(request),body.reason)

    @app.get(prefix+'/devices')
    def devices(request:Request):
        return {'devices':service.devices(token(request))}

    @app.post(prefix+'/device/revoke')
    def revoke(body:Device,request:Request):
        return service.revoke_device(body.device_id,token(request))

    @app.post(prefix+'/logout')
    def logout(request:Request):
        session=token(request)
        service.close_session(session)
        gateway.logout(session)
        return {'signed_out':True}

    @app.get(prefix+'/admin/models')
    def models(request:Request):
        session=administrator(request)
        return {'managed':bool(config.managed_model_id),'models':[
            {'alias':m.get('model_name'),'id':m.get('model_info',{}).get('id')}
            for m in gateway.models(session)]}

    @app.post(prefix+'/admin/discover')
    def discover(body:Discovery,request:Request):
        administrator(request)
        from company.discovery import discover
        try:
            return discover(body.base_url,body.api_key.get_secret_value())
        except ValueError as error:
            raise PairingError(str(error)) from None

    @app.post(prefix+'/admin/select')
    def select(body:Selection,request:Request):
        session=administrator(request)
        if not config.managed_model_id:
            raise PairingError('This pilot has a fixed model; changes are enabled only in the portable deployment.',409)
        from company.discovery import discover
        try:
            result=discover(body.base_url,body.api_key.get_secret_value())
        except ValueError as error:
            raise PairingError(str(error)) from None
        if body.model_id not in result['models']:
            raise PairingError('Select a model returned by this server.')
        return gateway.select_model(session,config.managed_model_id,result['api_base'],body.model_id,
            body.api_key.get_secret_value(),config.public['ContextTokens'],config.public['OutputTokens'])

    return app
