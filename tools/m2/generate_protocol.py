#!/usr/bin/env python3
"""Generate public schema and synthetic C/Python fixtures; never credentials."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'gateway'))
from infrabadge_gateway.models import Snapshot
from infrabadge_gateway.app import fixture

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    outputs={'protocol/status-v1.schema.json':json.dumps(Snapshot.model_json_schema(),indent=2)+'\n'}
    for state in ('HEALTHY','WARNING','CRITICAL','UNKNOWN'):
        outputs[f'protocol/fixtures/{state.lower()}.json']=fixture('badge-lab',state,1800000000,1).model_dump_json()+'\n'
    for name,expected in outputs.items():
        path=ROOT/name
        if args.check:
            if not path.exists() or path.read_text()!=expected:raise SystemExit('Stale protocol asset: '+name)
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(expected)
    print('Protocol schema and four SYNTHETIC snapshots '+('verified' if args.check else 'generated'))
if __name__=='__main__':main()
