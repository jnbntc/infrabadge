"""Synthetic IPv4 and anonymous Unix sockets only; no LAN, USB or privilege."""
import json
from pathlib import Path
import socket
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/m2'))
from observe_network import FILTER,attach_filter,packet_event

HOST='private-synthetic.invalid';ADDRESS='192.0.2.1';PEER='192.0.2.9'


def ipv4(protocol,source,destination,body):
    return struct.pack('!BBHHHBBH4s4s',0x45,0,20+len(body),0,0,64,protocol,0,socket.inet_aton(source),socket.inet_aton(destination))+body


def question(host=HOST):
    return b''.join(bytes([len(label)])+label.encode() for label in host.split('.'))+b'\0'+struct.pack('!HH',1,1)


def udp(payload):return struct.pack('!HHHH',5353,5353,8+len(payload),0)+payload


def filter_result(packet):
    # Execute the exact limited cBPF instruction set used in the kernel filter.
    pc=acc=index=0
    for _ in range(32):
        code,yes,no,value=FILTER[pc];pc+=1
        if code==0x30:acc=packet[value]
        elif code==0x54:acc&=value
        elif code==0xb1:index=(packet[value]&15)*4
        elif code==0x48:acc=struct.unpack_from('!H',packet,index+value)[0]
        elif code==0x15:pc+=yes if acc==value else no
        elif code==0x06:return value
        else:raise AssertionError('Unexpected filter opcode')
    raise AssertionError('Unbounded filter')


def test_mdns_query_and_compressed_reply_are_sanitized():
    query=struct.pack('!6H',0,0,1,0,0,0)+question()
    frame=ipv4(17,PEER,'224.0.0.251',udp(query))
    event=packet_event(frame,HOST,ADDRESS)
    assert event=={'event':'mdns_query_external','asks_ipv4':True,'asks_ipv6':False}
    reply=struct.pack('!6H',0,0x8400,1,1,0,0)+question()+b'\xc0\x0c'+struct.pack('!HHIH',1,0x8001,120,4)+socket.inet_aton(ADDRESS)
    event=packet_event(ipv4(17,ADDRESS,'224.0.0.251',udp(reply)),HOST,ADDRESS)
    assert event=={'event':'mdns_reply','from_gateway_host':True,'contains_expected_ipv4':True,'contains_other_ipv4':False,'matching_ipv4_records':1}
    exported=json.dumps(event)
    assert HOST not in exported and ADDRESS not in exported and PEER not in exported


def test_other_dns_names_and_malformed_compression_are_dropped():
    query=struct.pack('!6H',0,0,1,0,0,0)+question('unrelated.invalid')
    assert packet_event(ipv4(17,PEER,'224.0.0.251',udp(query)),HOST,ADDRESS) is None
    loop=struct.pack('!6H',0,0,1,0,0,0)+b'\xc0\x0c'+struct.pack('!HH',1,1)
    assert packet_event(ipv4(17,PEER,'224.0.0.251',udp(loop)),HOST,ADDRESS) is None
    assert packet_event(b'',HOST,ADDRESS) is None


def test_tcp_metadata_never_exports_payload_or_addresses():
    secret=b'PRIVATE_PAYLOAD_CANARY'
    tcp=struct.pack('!HHIIBBHHH',43210,8443,0,0,0x50,0x18,1024,0,0)+secret
    full=ipv4(6,PEER,ADDRESS,tcp)
    event=packet_event(full[:40],HOST,ADDRESS)
    assert event=={'event':'tcp','direction':'to_gateway','syn':False,'ack':True,'fin':False,'rst':False,'payload_bytes':len(secret)}
    assert secret.decode() not in json.dumps(event) and PEER not in json.dumps(event)


def test_kernel_filter_rejects_unrelated_ports_and_limits_captured_bytes():
    for protocol,source,destination,expected in [(17,5353,5353,1500),(17,53,54321,0),(6,43210,8443,128),(6,8443,43210,128),(6,43210,443,0),(1,0,0,0)]:
        frame=ipv4(protocol,PEER,ADDRESS,struct.pack('!HH',source,destination)+bytes(20))
        assert filter_result(frame)==expected
    assert filter_result(bytes([0x60])+bytes(100))==0


def test_filter_is_accepted_and_enforced_by_real_kernel_without_network():
    import pytest
    sender,receiver=socket.socketpair(socket.AF_UNIX,socket.SOCK_DGRAM)
    try:
        attach_filter(receiver);receiver.settimeout(.05)
        allowed=ipv4(6,PEER,ADDRESS,struct.pack('!HH',43210,8443)+bytes(200))
        sender.send(allowed)
        assert receiver.recv(2048)==allowed[:128]
        rejected=ipv4(6,PEER,ADDRESS,struct.pack('!HH',43210,443)+bytes(200))
        sender.send(rejected)
        with pytest.raises(socket.timeout):receiver.recv(2048)
    finally:sender.close();receiver.close()
