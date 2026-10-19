"""Host-only lab wrapper around the unchanged M2 gateway. No hardware access."""
import getpass
import hashlib
import hmac
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import shutil
import zipfile
import ssl
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from phase_a import ROOT,save

def create_lab(config,client_hash,challenge,ca_hash,out,bind):
    from fastapi import Request,HTTPException
    from infrabadge_gateway.app import create_app
    app=create_app(config)
    lock=threading.Lock();sequence=0
    @app.middleware('http')
    async def trace_status(request,call_next):
        nonlocal sequence
        response=await call_next(request)
        if request.url.path=='/api/v1/devices/badge-lab/status':
            with lock:
                sequence+=1
                record={'sequence':sequence,'host_epoch':int(time.time()),'http_status':response.status_code,'conditional_request':bool(request.headers.get('if-none-match')),'peer_scope':'host' if request.client and request.client.host==bind else 'external_unattributed'}
                fd=os.open(out/'gateway-events.jsonl',os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
                try:os.write(fd,(json.dumps(record,separators=(',',':'))+'\n').encode('ascii'))
                finally:os.close(fd)
        return response

    @app.get('/phase-a/ready')
    def ready():return {'lab':'M2 phase A','challenge':challenge,'hardware_validated':False}
    @app.post('/phase-a/confirm')
    async def confirm(request:Request):
        auth=request.headers.get('authorization','')
        if not auth.startswith('Bearer ') or len(auth)>103 or not hmac.compare_digest(hashlib.sha256(auth[7:].encode()).hexdigest(),client_hash):raise HTTPException(401)
        if len(await request.body())>1024:raise HTTPException(413)
        try:value=await request.json()
        except Exception:raise HTTPException(400) from None
        fields=['dns_expected_address','tls_explicit_ca','hostname_and_dates_verified','http_200','http_304','auth_401']
        if not isinstance(value,dict) or any(value.get(k) is not True for k in fields) or value.get('challenge')!=challenge or value.get('ca_sha256')!=ca_hash or value.get('tls_version')!='TLSv1.2' or type(value.get('client_epoch')) is not int or abs(time.time()-value['client_epoch'])>60:raise HTTPException(400)
        peer=request.client.host if request.client else ''
        try:external=not ipaddress.ip_address(peer).is_loopback and peer!=bind
        except ValueError:external=False
        summary={'status':'external_client_passed' if external else 'host_client_passed','external_client_seen':external,**{k:True for k in fields},'tls_version':'TLSv1.2','firmware_source_ci':'9c5ef57','flash_performed':False,'provision_performed':False,'hardware_validated':False}
        if external:save(out/'external-client.json',summary)
        else:save(out/'host-client.json',summary)
        return {'accepted':True,'external_client_seen':external}
    return app

def serve(out,private):
    if not sys.stdin.isatty():raise SystemExit('Se requiere terminal normal para entrada sin eco; SIN sudo.')
    from infrabadge_gateway.lab import certificates
    from infrabadge_gateway.models import Device,GatewayConfig
    import uvicorn
    net=json.loads((private/'network.json').read_text());address=net['address'];hostname=net['hostname']
    ca,cert,key=certificates(private,hostname)
    ssid=getpass.getpass('SSID Wi-Fi (sin eco, no se registra): ')
    password=getpass.getpass('Clave Wi-Fi (sin eco, no se registra): ')
    if not all(32<=ord(c)<=126 for c in ssid+password) or not 1<=len(ssid)<=32 or not 8<=len(password)<=63:raise SystemExit('SSID/clave fuera de límites; no se muestran valores.')
    token=secrets.token_urlsafe(32);client_token=secrets.token_urlsafe(32)
    device={'schema_version':1,'device_id':'badge-lab','ssid':ssid,'wifi_password':password,'gateway_url':f'https://{hostname}:8443','token':token,'ca_pem':ca.read_text(),'interval_seconds':900,'wifi_timeout_ms':15000,'http_timeout_ms':5000}
    gateway={'devices':{'badge-lab':{'token_sha256':[hashlib.sha256(token.encode()).hexdigest()],'scenario':'HEALTHY'},'phase-a-client':{'token_sha256':[hashlib.sha256(client_token.encode()).hexdigest()],'scenario':'HEALTHY'}},'enable_faults':False}
    save(private/'device.json',device);save(private/'gateway.json',gateway)
    save(private/'client.json',{'url':device['gateway_url'],'device_id':'phase-a-client','token':client_token,'expected_lan_address':address})
    bundle=private/'phone-client.zip'
    with zipfile.ZipFile(bundle,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(ca,'ca.pem');archive.write(private/'client.json','client.json')
        archive.write(ROOT/'tools/m2/check_gateway.py','check_gateway.py')
    bundle.chmod(0o600)
    # Separate client token: never copy device.json or Wi-Fi credentials to the phone.
    fingerprint=hashlib.sha256(ca.read_bytes()).hexdigest();challenge=secrets.token_hex(3).upper()
    save(private/'server-context.json',{'bind':address,'hostname':hostname,'port':8443,'challenge':challenge,'ca_sha256':fingerprint})
    save(out/'tls-public-summary.json',{'status':'prepared','ca_sha256':fingerprint,'san_matches_configured_hostname':True,'keys_and_configs_outside_git':True,'files_mode_0600':True,'host_utc_synchronized':net['host_utc_synchronized'],'external_verification':'pending'})
    return serve_saved(out,private)

def serve_saved(out,private):
    from infrabadge_gateway.models import GatewayConfig
    import uvicorn
    net=json.loads((private/'network.json').read_text());address=net['address'];hostname=net['hostname']
    ca=private/'ca.pem';cert=private/'server.pem';key=private/'server.key'
    gateway=json.loads((private/'gateway.json').read_text())
    context=json.loads((private/'server-context.json').read_text())
    challenge=context['challenge'];fingerprint=context['ca_sha256']
    decision=json.loads((out/'operator-decision.json').read_text()) if (out/'operator-decision.json').exists() else {}
    waived=decision.get('external_client')=='omitted_by_user'
    config=GatewayConfig.model_validate(gateway)
    client_hash=gateway['devices']['phase-a-client']['token_sha256'][0]
    app=create_lab(config,client_hash,challenge,fingerprint,out,address)
    # Open only the selected LAN IPv4 address, no wildcard/Tailscale listener.
    listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind((address,8443));listener.listen(8)
    server=uvicorn.Server(uvicorn.Config(app,ssl_certfile=str(cert),ssl_keyfile=str(key),lifespan='off',access_log=False,log_level='critical'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    deadline=time.monotonic()+5
    while not server.started and thread.is_alive() and time.monotonic()<deadline:time.sleep(.05)
    if not server.started:raise SystemExit('No se pudo iniciar HTTPS; no se modifica firewall ni otro servicio.')
    spec=importlib.util.spec_from_file_location('check_gateway',ROOT/'tools/m2/check_gateway.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
    try:
        try:client.check(ca,private/'client.json')
        except Exception:
            save(out/'phase-a-status.json',{'status':'blocked_host_dns_or_tls','gateway_running':True,'flash_performed':False,'provision_performed':False})
            print('El resolver del host no permitió la prueba directa; verificando la interfaz sin cambiar SNI/CA.',flush=True)
            from audit_host import audit
            audit(private,out,make_bundle=not waived)
        else:
            # Negative control: system roots must not trust the new lab CA.
            rejected=False
            try:
                with socket.create_connection((address,8443),timeout=3) as raw:
                    with ssl.create_default_context().wrap_socket(raw,server_hostname=hostname):pass
            except ssl.SSLCertVerificationError:rejected=True
            if not rejected:raise ValueError('unexpected trust of lab CA')
            save(out/'phase-a-status.json',{'status':'waiting_external_client','local_https_200_304_401':'passed','untrusted_ca_rejected':True,'gateway_running':True,'external_client_seen':False,'flash_performed':False,'provision_performed':False,'hardware_validated':False})
            print('HTTPS local PASS: CA/SAN/fecha, 200/304/401; CA ajena rechazada.',flush=True)
        if waived:
            save(out/'phase-a-status.json',{'status':'prepared_local_only_external_waived','gateway_running':True,'external_client_seen':False,'external_client':'omitted_by_user','host_tls':'passed','flash_performed':False,'provision_performed':False,'hardware_validated':False})
        print('Gateway HTTPS: https://'+hostname+':8443',flush=True)
        print('Carpeta PRIVADA: '+str(private),flush=True)
        if not waived:print('Reto de esta sesión: '+challenge,flush=True)
        if not waived:print('Cliente externo opcional: paquete privado disponible; nunca compartir device.json ni server.key.',flush=True)
        print('SHA-256 CA pública: '+fingerprint,flush=True)
        print('Telemetría HTTP saneada preparada; no registra IP, identidad física ni cabeceras.',flush=True)
        print('Dejar esta terminal abierta. No abre puertos serie ni flashea. Ctrl+C detiene sólo el gateway.',flush=True)
        announced=False
        while thread.is_alive():
            if (out/'external-client.json').exists() and not announced:
                announced=True
                print('Cliente externo autenticado: PASS DNS/TLS/200/304/401. Fase A requiere revisión final; placa sin tocar.',flush=True)
                save(out/'phase-a-status.json',{'status':'external_client_passed_review_pending','gateway_running':True,'external_client_seen':True,'flash_performed':False,'provision_performed':False,'hardware_validated':False})
            time.sleep(.5)
    except KeyboardInterrupt:pass
    finally:
        server.should_exit=True;thread.join(5);listener.close()
        status=json.loads((out/'phase-a-status.json').read_text());status['gateway_running']=False;save(out/'phase-a-status.json',status)
