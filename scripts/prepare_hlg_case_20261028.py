"""Derive original C57 HLG black diagnostic from the original C55 harness."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'scripts/run_chromatic_case_20261028.py').read_text('utf8')
for a,b in [('C55','C57'),('native-chromatic','native-hlg-black'),('0.1.45','0.1.47'),('len(caps)==84','len(caps)==86'),
            ("caps['native_chromatic_adaptation']","caps['native_hlg_black_level']"),('editable-chromatic','editable-hlg-black'),
            ('source-prophoto-d50','source-hlg-black'),('ap1-surface','linear-surface'),('Bradford white adaptation','HLG display black')]:s=s.replace(a,b)
start=s.index("SOURCE=dict(");stop=s.index('\ndef sha(',start)
s=s[:start]+'''SOURCE=dict(primaries='bt2020',transfer='hlg-bt2100',reference_white_nits=203,display_peak_nits=1000,system_gamma=1.2,display_black_nits=.5)
WORK=dict(primaries='bt2020',transfer='linear',reference_white_nits=203)
OUTPUT=dict(primaries='bt2020',transfer='pq-st2084',reference_white_nits=203)
MAPPING=dict(operator='reinhard-luminance',source_peak_nits=1000,target_peak_nits=100,exposure_stops=0,gamut_policy='clip')
PATCHES=np.repeat(np.array([0,.002,.01,.03,.07,.2,.5,.9])[:,None],3,axis=1)
BT2020=np.array([[.6369580483012914,.14461690358620832,.1688809751641721],
    [.2627002120112671,.6779980715188708,.05930171646986196],[0,.028072693049087428,1.060985057710791]])
BT709=np.array([[506752/1228815,87881/245763,12673/70218],
    [87098/409605,175762/245763,12673/175545],[7918/409605,87881/737289,1001167/1053270]])

def hlg_nits(v,black=.5):
    # Independent Table5 scalar constants/vector math, no product imports.
    import math
    lift=math.sqrt(3)*math.exp(math.log(black/1000)/2.4) if black else 0
    x=lift+(1-lift)*v;aa=.17883277;bb=1-4*aa;cc=.5-aa*math.log(4*aa)
    scene=np.where(x<=.5,x*x/3,(np.exp((x-cc)/aa)+bb)/12)
    lum=scene@np.array([.2627,.678,.0593])
    return 1000*scene*lum[...,None]**.2

def pq(v):
    p=(np.maximum(v,0)/10000)**(2610/16384)
    return ((3424/4096+2413/128*p)/(1+2392/128*p))**(2523/32)

def display(v):
    x=np.einsum('ij,...j->...i',np.linalg.inv(BT709)@BT2020,v)/100
    lum=np.maximum(x@np.array([.2126,.7152,.0722]),0)
    mapped=lum*(1+lum/100)/(1+lum)
    return srgb(np.clip(x*np.divide(mapped,lum,out=np.zeros_like(lum),where=lum!=0)[...,None],0,1))
''' +s[stop:]
s=s.replace("'AGENT EDITOR KIT / EXPLICIT REFERENCE WHITES'","'AGENT EDITOR KIT / EXPLICIT HLG DISPLAY BLACK'")
s=s.replace("'ProPhoto D50 > linear AP1 D60 > BT.709 D65'","'HLG / 0.5 nit black / 1000 nit peak > linear > PQ'")
s=s.replace("'Neutral / colour patches | moving highlight + editable GPU Bloom'","'Neutral shadow patches | moving highlight + editable GPU Bloom'")
s=s.replace("s['color']=dict(primaries='bt709',transfer='iec61966-2-1',matrix='bt709',range='limited')","s['color']=dict(primaries='bt2020',transfer='smpte2084',matrix='bt2020nc',range='limited')")
s=s.replace("output_signal=OUTPUT,range_policy='clip',","output_signal=OUTPUT,range_policy='clip',preview_mapping=MAPPING,")
s=s.replace('threshold=.75','threshold=3')
start=s.index("        surface=invoke('surface'");stop=s.index("        actual=np.fromfile(",start)
s=s[:start]+'''        source_json=work/'source-signal.json';working_json=work/'working-signal.json'
        save(source_json,SOURCE);save(working_json,WORK)
        surface=invoke('surface','surface','export','--project',project,'--asset-id','chart','--output',project/'renders/linear-surface',
            '--source-signal-json',source_json,'--working-signal-json',working_json,'--stop-frame','1')
        source32=frames[0].astype(np.float32)/65535
        expected=hlg_nits(source32.astype(float))/203
''' +s[stop:]
s=s.replace('error<1.3e-7','error<1e-6')
start=s.index('            mapped=np.linalg.inv(BT709)');stop=s.index('            seen=float(',start)
s=s[:start]+'''            expected_y=64+876*(pq(hlg_nits(rgb.astype(float)))@np.array([.2627,.678,.0593]))
''' +s[stop:]
start=s.index("        control=np.einsum(");stop=s.index("        sheet=Image.new(",start)
s=s[:start]+'''        control=Image.fromarray(np.rint(np.clip(display(hlg_nits(control32.astype(float),black=0)),0,1)*255).astype(np.uint8))
        control.save(public/'independent-zero-black-control.png')
''' +s[stop:]
s=s.replace('INDEPENDENT NO-ADAPTATION CONTROL / no glow','INDEPENDENT ZERO-BLACK CONTROL / no glow').replace('D50 XYZ interpreted without white matching','Same HLG codes; ideal zero-nit display black')
s=s.replace('ACTUAL ENGINE / D50 > D60 > D65 + GPU Bloom','ACTUAL ENGINE / 0.5-nit HLG black + GPU Bloom').replace('Explicit reference whites; not full ACES or ICC','Explicit display declaration; SDR review only')
start=s.index("        (public/'SOURCE.txt').write_text(");stop=s.index('        files=[',start)
s=s[:start]+'''        (public/'SOURCE.txt').write_text('C57 / agent editor kit CLI0.1.47\\nOriginal generated RGB16 chart, lettering and stereo tones: CC0-1.0.\\n'
            'Declared BT.2020 HLG: reference203, peak1000, black0.5 nits, gamma1.2. Black0.5 is an intentional diagnostic declaration, not measured monitor calibration.\\n'
            'Actual native Windows/OpenCL Bloom, CPU x264 ten-bit PQ master; separate explicit modified-Reinhard SDR previews.\\n'
            'Independent zero-black/no-glow mathematical control; published ITU-R BT.2100-3 Table5 facts, original implementation, no copied standard pages.\\n'
            'No human continuous playback/listening, natural-image aesthetic or HDR monitor acceptance claimed.\\n',encoding='utf8')
''' +s[stop:]
s=s.replace("mathematical_control_is_engine_render=False","mathematical_control_is_engine_render=False,declared_black_nits=.5")
s=s.replace("planes=np.frombuffer(video,'<u2').reshape(N,3,H,W);patch_errors=[]\n        for j in range(8):\n            rgb=frames[0][120,50+75*j].astype(np.float32)/65535",
    "planes=np.frombuffer(video,'<u2').reshape(N,3,H,W);patch_errors=[];patch_records=[]\n        for index in range(N):\n          for j in range(8):\n            rgb=frames[index][120,50+75*j].astype(np.float32)/65535")
s=s.replace("seen=float(planes[:,0,110:138,35+75*j:70+75*j].mean());patch_errors.append(abs(seen-expected_y))",
    "seen=float(planes[index,0,110:138,35+75*j:70+75*j].mean());patch_errors.append(abs(seen-expected_y))\n"
    "            patch_records.append(dict(frame=index,patch=j,expected=float(expected_y),actual=seen,error=abs(seen-expected_y)))\n"
    "        save(out/'independent-every-frame-patches.json',dict(status='passed' if max(patch_errors)<1.6 else 'failed',comparisons=len(patch_records),maximum_luma_code_error=max(patch_errors),product_code_imported=False,records=patch_records))")
p=ROOT/'scripts/run_hlg_case_20261028.py';assert not p.exists();p.write_text(s,encoding='utf8',newline='\n');print(p)
