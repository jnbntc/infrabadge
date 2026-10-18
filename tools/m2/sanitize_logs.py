#!/usr/bin/env python3
"""Export numeric/enum M2 events only. Never emits original log text."""
import argparse
import json
from pathlib import Path
import re
ANSI=re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
PREFIX=re.compile(r'^[IWE] \(\d+\) (?:infrabadge-m2|power): ')
BOOT=re.compile(r'M2_BOOT: reset=(\d{1,2}) wake=(\d{1,2}); mock gateway only')
DISPLAY=re.compile(r'M2_DISPLAY: (drawn|unchanged|error); live=([01]) clock=([01])')
CYCLE=re.compile(r'M2_CYCLE: result=(OK|CONFIG|CLOCK|WIFI|DNS|TLS|HTTP|AUTH|JSON|OVERSIZE|EXPIRED|STORE) wifi_us=(\d{1,12}) https_us=(\d{1,12}) active_us=(\d{1,12}) sleep_s=(\d{1,4})')
SLEEP=re.compile(r'M1_SLEEP_ENTER: timer=(\d{1,4}) s; BOOT/PWR wake; USB may disconnect')
HTTP=re.compile(r'M2_HTTP: stage=(INIT|ALLOC|HEADERS|TRANSFER) esp=(-?\d{1,10}) tls=(-?\d{1,10}) detail=(-?\d{1,10}) flags=(-?\d{1,10}) http=(-?\d{1,3}) timeout=([01])')

def sanitize(text):
    events=[];dropped=0
    for line in text.splitlines():
        message=PREFIX.sub('',ANSI.sub('',line).strip())
        if m:=BOOT.fullmatch(message):events.append({'event':'boot','reset':int(m[1]),'wake':int(m[2])})
        elif m:=DISPLAY.fullmatch(message):events.append({'event':'display','result':m[1],'live':bool(int(m[2])),'clock':bool(int(m[3]))})
        elif m:=CYCLE.fullmatch(message):events.append({'event':'cycle','result':m[1],**dict(zip(['wifi_us','https_us','active_us','sleep_s'],map(int,m.groups()[1:])))})
        elif m:=SLEEP.fullmatch(message):events.append({'event':'sleep_requested','seconds':int(m[1])})
        elif m:=HTTP.fullmatch(message):
            values=list(map(int,m.groups()[1:6]))
            if all(-2147483648<=v<=2147483647 for v in values[:4]) and -1<=values[4]<=599:
                events.append({'event':'http','stage':m[1],**dict(zip(['esp','tls','detail','flags','http'],values)),'timeout':bool(int(m[7]))})
            else:dropped+=1
        else:dropped+=1
    return {'events':events,'discarded_lines':dropped,'source_text_exported':False,'hardware_pass_inferred':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.input.resolve()==a.output.resolve():p.error('Conservar el original')
    value=sanitize(a.input.read_text(errors='replace'))
    with a.output.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
    print('Eventos M2 exportados sin texto original; revisar antes de publicar.')
if __name__=='__main__':main()
