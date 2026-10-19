"""Strict diagnostic report decoder; no hardware operations."""
import struct
import re
import zlib
from auto_lab import CASES
FIELDS=('index','reset','wake','error','http','clock','live','display','transfers','wifi_stopped','sleep_seconds','wifi_ms','https_ms','active_ms')


def validate(value,run):
    if not isinstance(value,dict) or set(value)!={'version','run','phase','fault','count','timer_returns','checksum','events'}:raise ValueError('report_schema')
    if type(value['version']) is not int or value['version']!=1 or value['run']!=run or not isinstance(run,str) or not re.fullmatch('[0-9a-f]{32}',run) or int(run,16)==0:raise ValueError('report_identity')
    for key in ('phase','fault','count','timer_returns','checksum'):
        if type(value[key]) is not int or not 0<=value[key]<=0xffffffff:raise ValueError('report_number')
    if value['phase'] not in (1,2,3,4) or value['fault']>7:raise ValueError('report_enum')
    count=value['count']
    if not 0<=count<=26 or value['timer_returns']>count or not isinstance(value['events'],list) or len(value['events'])!=count:raise ValueError('report_count')
    header=[0x49424d41,1]+[int(run[i:i+8],16) for i in range(0,32,8)]+[value[k] for k in ('phase','fault','count','timer_returns')]+[0]
    words=[]
    for index,e in enumerate(value['events']):
        if not isinstance(e,dict) or set(e)!=set(FIELDS) or e['index']!=index:raise ValueError('event_schema')
        if any(type(e[k]) is not int or not 0<=e[k]<=0xffffffff for k in FIELDS):raise ValueError('event_number')
        words.extend(e[k] for k in FIELDS)
    words.extend([0]*((26-count)*len(FIELDS)))
    crc=zlib.crc32(struct.pack('<'+'I'*(len(header)+len(words)),*(header+words)))
    if crc!=value['checksum']:raise ValueError('report_checksum')
    complete=value['phase']==3 and value['fault']==0 and count==26 and value['timer_returns']==25
    checks=[]
    for index,e in enumerate(value['events']):
        expected=CASES[index][2]
        good=e['error']==expected and e['clock']==1 and e['live']==int(expected==0) and e['wifi_stopped']==1 and e['display'] in (0,1) and e['transfers']<=1
        good=good and e['active_ms']<=3600000 and (index==0 or (e['reset']==8 and e['wake']==4))
        good=good and e['sleep_seconds']==(0 if index==25 else 120 if expected else 60)
        if expected==0:good=good and e['http'] in (200,304)
        if index==1:good=good and e['http']==304 and e['display']==0 and e['transfers']==0
        if index in (6,8):good=good and e['http']==(503 if index==6 else 401)
        checks.append(bool(good))
    return {'status':'diagnostic_cases_confirmed' if complete and all(checks) else 'incomplete_or_failed',
            'completed_cases':count,'case_checks':checks,'timer_reset_wake_confirmed':bool(complete and all(checks)),
            'identical_frame_driver_transfer_suppressed':bool(len(checks)>1 and checks[1]),
            'optical_display_validated':False,'current_measurements':'deferred_by_user','full_m2_validation':False}
