#!/usr/bin/env python3
"""
Standalone test runner — no pytest dependency required.
Usage: python3 tests/run_tests.py
"""
import sys, os
from pathlib import Path
# Inject rich stub if rich is not installed (CI environments without pip access)
try:
    import rich
except ImportError:
    _stub = Path(__file__).resolve().parent.parent / "rich_stub"
    if _stub.exists():
        sys.path.insert(0, str(_stub))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import struct, tempfile
from pathlib import Path

passed = failed = 0

def ok(v, m=''):
    if not v: raise AssertionError(m or 'assertion failed')

def run(name, fn):
    global passed, failed
    try:
        fn()
        print(f'  PASS  {name}')
        passed += 1
    except Exception as e:
        print(f'  FAIL  {name}: {e}')
        failed += 1

print('\n=== LTE Bitmask ===')
from modules.qualcomm import build_lte_bitmask, parse_lte_bitmask
run('B66 in high word',   lambda: ok(build_lte_bitmask([66])[1] & (1<<1)))
run('B71 in high word',   lambda: ok(build_lte_bitmask([71])[1] & (1<<6)))
run('empty = (0,0)',      lambda: ok(build_lte_bitmask([]) == (0,0)))
run('round-trip B13/66/71', lambda: ok(sorted(parse_lte_bitmask(*build_lte_bitmask([2,4,13,66,71]))) == sorted([2,4,13,66,71])))
run('round-trip 1-128',   lambda: ok(sorted(parse_lte_bitmask(*build_lte_bitmask(list(range(1,129))))) == list(range(1,129))))

print('\n=== Carrier Profiles ===')
from modules.modem_bands import CARRIER_PROFILES
run('16+ carriers',       lambda: ok(len(CARRIER_PROFILES) >= 16))
run('verizon B13',        lambda: ok(13 in CARRIER_PROFILES['verizon']['lte_bands']))
run('verizon B13 primary',lambda: ok(CARRIER_PROFILES['verizon']['primary_lte'] == 13))
run('verizon n77 C-band', lambda: ok('n77' in CARRIER_PROFILES['verizon']['nr_sub6']))
run('verizon n260 mmWave',lambda: ok('n260' in CARRIER_PROFILES['verizon'].get('nr_mmwave',[])))
run('verizon n261 mmWave',lambda: ok('n261' in CARRIER_PROFILES['verizon'].get('nr_mmwave',[])))
run('verizon B48 CBRS',   lambda: ok(48 in CARRIER_PROFILES['verizon']['lte_bands']))
run('verizon B66 AWS-3',  lambda: ok(66 in CARRIER_PROFILES['verizon']['lte_bands']))
run('tmobile B71 600MHz', lambda: ok(71 in CARRIER_PROFILES['tmobile']['lte_bands']))
run('tmobile n41 mid',    lambda: ok('n41' in CARRIER_PROFILES['tmobile']['nr_sub6']))
run('att B14 FirstNet',   lambda: ok(14 in CARRIER_PROFILES['att']['lte_bands']))
run('firstnet B14 primary',lambda: ok(CARRIER_PROFILES['firstnet']['primary_lte'] == 14))
run('eu_generic B20',     lambda: ok(20 in CARRIER_PROFILES['eu_generic']['lte_bands']))
run('australia B28 APT',  lambda: ok(28 in CARRIER_PROFILES['australia_telstra']['lte_bands']))
run('japan B19 Docomo',   lambda: ok(19 in CARRIER_PROFILES['japan_docomo']['lte_bands']))
def check_hex():
    for n,p in CARRIER_PROFILES.items():
        int(p['lte_hex_low'],16); int(p['nr_hex'],16)
run('all hex masks parse', check_hex)
def check_fields():
    req = {'display','lte_bands','nr_sub6','primary_lte','primary_nr','lte_hex_low','nr_hex'}
    for n,p in CARRIER_PROFILES.items():
        m = req - set(p.keys())
        if m: raise AssertionError(f'{n} missing {m}')
run('all required fields', check_fields)

print('\n=== Verizon Reference ===')
from modules.qualcomm_chips import VERIZON_BANDS, BAND_PRESETS
run('B13 type=primary',     lambda: ok(VERIZON_BANDS['lte'][13]['type']=='primary'))
run('n77 type=primary5g',   lambda: ok(VERIZON_BANDS['nr_sub6']['n77']['type']=='primary5g'))
run('n260 mmWave',          lambda: ok('n260' in VERIZON_BANDS['nr_mmwave']))
run('n261 mmWave',          lambda: ok('n261' in VERIZON_BANDS['nr_mmwave']))
run('notes >= 3',           lambda: ok(len(VERIZON_BANDS['notes'])>=3))
run('27+ presets',          lambda: ok(len(BAND_PRESETS)>=27))
run('lte_only nr=0',        lambda: ok(int(BAND_PRESETS['lte_only']['nr'],16)==0))
run('all_bands lte nonzero',lambda: ok(int(BAND_PRESETS['all_bands']['lte'],16)>0))
def vz_preset_b13():
    low = int(BAND_PRESETS['us_verizon_full']['lte'],16) & 0xFFFFFFFFFFFFFFFF
    ok(13 in parse_lte_bitmask(low))
run('verizon preset encodes B13', vz_preset_b13)

print('\n=== Chip Database ===')
from modules.chipsets import (MTK_CHIPS, UNISOC_CHIPS, ROCKCHIP_CHIPS,
                               ALLWINNER_CHIPS, REALTEK_CHIPS)
from modules.qualcomm_chips import SNAPDRAGON_CHIPS
total = sum(len(d) for d in [MTK_CHIPS,UNISOC_CHIPS,ROCKCHIP_CHIPS,
                              ALLWINNER_CHIPS,REALTEK_CHIPS,SNAPDRAGON_CHIPS])
run(f'137+ chips ({total})',  lambda: ok(total>=137))
run('mtk watch chips',       lambda: ok(sum(1 for v in MTK_CHIPS.values() if v.get('watch'))>=3))
run('unisoc watch chips',    lambda: ok(sum(1 for v in UNISOC_CHIPS.values() if v.get('watch'))>=5))
def check_chip_db():
    dbs = [
        (MTK_CHIPS,       {'name','platform','arch','year','watch','brom'}),
        (UNISOC_CHIPS,    {'name','platform','arch','year','watch','fdl'}),
        (ROCKCHIP_CHIPS,  {'name','platform','arch','year','type','maskrom'}),
        (ALLWINNER_CHIPS, {'name','platform','arch','year','type','fel'}),
        (REALTEK_CHIPS,   {'name','platform','arch','year','type'}),
        (SNAPDRAGON_CHIPS,{'name','modem','year','tier','edl','bands_5g'}),
    ]
    for db, req in dbs:
        for cid, info in db.items():
            m = req - set(info.keys())
            if m: raise AssertionError(f'{cid} missing {m}')
run('all chip entries valid', check_chip_db)

print('\n=== Core Framework ===')
import core
from core.registry import all_vendors, all_bands
run('6 vendors registered',  lambda: ok(len(all_vendors())==6))
run('4+ band backends',      lambda: ok(len(all_bands())>=4))
for k in ['mtk','unisoc','rockchip','allwinner','realtek','qualcomm']:
    run(f'vendor {k}',       lambda x=k: ok(x in all_vendors()))
from core.pipeline import list_pipelines
pipes = list_pipelines()
run('6+ pipelines',           lambda: ok(len(pipes)>=6))
run('root-device 7 steps',    lambda: ok(len(pipes['root-device'].dry_run({}))==7))
run('full-backup 4 steps',    lambda: ok(len(pipes['full-backup'].dry_run({}))==4))
run('avb-disable 4 steps',    lambda: ok(len(pipes['avb-disable'].dry_run({}))==4))
run('flash-rom 4 steps',      lambda: ok(len(pipes['flash-rom'].dry_run({}))==4))
run('wearos-setup 6 steps',   lambda: ok(len(pipes['wearos-setup'].dry_run({}))==6))
run('configure-bands 4 steps',lambda: ok(len(pipes['configure-bands'].dry_run({}))==4))
from core.pipeline import Pipeline, Task
from core.interfaces import Result, Status
def w(ctx): ctx['x']=99; return Result.ok('w')
def r(ctx): ok(ctx.get('x')==99); return Result.ok('r')
p=Pipeline('ctx','t'); p.add(Task('w',w,'W',True)); p.add(Task('r',r,'R',True))
run('pipeline context sharing',  lambda: ok(p.run({}).success))
_ran=[]
def side(ctx): _ran.append(1); return Result.ok('r')
p2=Pipeline('d','t'); p2.add(Task('s',side,'s',True))
p2.dry_run({})
run('dry-run no execution',      lambda: ok(len(_ran)==0))
def opt_f(ctx): return Result.fail('opt')
_aft={}
def aft(ctx): _aft['ran']=True; return Result.ok('ok')
p3=Pipeline('o','t'); p3.add(Task('f',opt_f,'f',False)); p3.add(Task('a',aft,'a',True))
p3.run({})
run('optional failure continues',lambda: ok(_aft.get('ran')))
run('ok() truthy',    lambda: ok(bool(Result.ok('t'))))
run('fail() falsy',   lambda: ok(not bool(Result.fail('e'))))
run('ok data',        lambda: ok(Result.ok('t',foo=42).data.get('foo')==42))
run('skip status',    lambda: ok(Result.skip().status==Status.SKIPPED))

print('\n=== Vendor Detection ===')
from core.vendors import MTKVendor, RockchipVendor, UnisocVendor, AllwinnerVendor
mv=MTKVendor(); rv=RockchipVendor(); uv=UnisocVendor(); av=AllwinnerVendor()
run('mtk detects mt6761',     lambda: ok(mv.detect({'ro.board.platform':'mt6761'}) is not None))
run('rk detects rk3588',      lambda: ok(rv.detect({'ro.board.platform':'rk3588'}) is not None))
run('unisoc detects sc9863a', lambda: ok(uv.detect({'ro.board.platform':'sc9863a'}) is not None))
run('aw detects sun50i',      lambda: ok(av.detect({'ro.board.platform':'sun50i'}) is not None))
run('mtk rejects rk3588',     lambda: ok(mv.detect({'ro.board.platform':'rk3588'}) is None))
run('rk rejects mt6761',      lambda: ok(rv.detect({'ro.board.platform':'mt6761'}) is None))

print('\n=== AVB / ROM / Analysis ===')
from modules.avb import create_blank_vbmeta
with tempfile.TemporaryDirectory() as td:
    out=Path(td)/'v.img'; create_blank_vbmeta(out)
    data=out.read_bytes()
    fo=struct.calcsize('>4sI I I I I I I I I I I I I 64s 32s')
    flags=struct.unpack_from('>I',data,fo)[0]
    run('avb magic=AVB0', lambda: ok(data[:4]==b'AVB0'))
    run('avb flags=3',    lambda: ok(flags==3))
    run('avb size=4096',  lambda: ok(out.stat().st_size==4096))
from modules.rom import generate_mtk_scatter, generate_unisoc_xml
with tempfile.TemporaryDirectory() as td:
    p=Path(td)
    for n in ['boot','system','vendor']:
        (p/f'{n}.img').write_bytes(b'ANDROID!'+b'\x00'*100)
    sc=generate_mtk_scatter(p,'MT6761','test'); xml=generate_unisoc_xml(p,'SC9863A')
    run('scatter MT6761',   lambda: ok('MT6761' in sc.read_text()))
    run('scatter has boot', lambda: ok('boot' in sc.read_text()))
    run('unisoc xml ok',    lambda: ok('SC9863A' in xml.read_text()))
from modules.analyze import block_entropy
run('entropy zeros=0',      lambda: ok(abs(block_entropy(b'\x00'*4096))<0.001))
run('entropy random>7.9',   lambda: ok(block_entropy(bytes(range(256))*16)>7.9))
run('entropy empty=0',      lambda: ok(block_entropy(b'')==0.0))

print(f'\n{"="*52}')
print(f'  {passed} passed  |  {failed} failed  |  {passed+failed} total')
if not failed:
    print('  ALL TESTS PASSED')
else:
    sys.exit(1)
