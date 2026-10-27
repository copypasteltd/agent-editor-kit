"""Exact native PTS subdivision, including VFR, without prefilter resampling."""
from fractions import Fraction
import hashlib,json
MAX_FRAMES=15000
MAX_OUTPUT_FRAMES=120000
MAX_DENOMINATOR=2**31-1

def clock_digest(clock):
    return 'sha256:'+hashlib.sha256(json.dumps(clock,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def validate_clock(clock):
    if not isinstance(clock,dict) or set(clock)!={'time_base','pts','durations'}:raise ValueError('native clock fields')
    value=clock['time_base']
    if not isinstance(value,str) or len(value)>64:raise ValueError('time base')
    base=Fraction(value)
    if base<=0 or max(base.numerator,base.denominator)>MAX_DENOMINATOR:raise ValueError('time base range')
    pts=clock['pts'];durations=clock['durations']
    if not isinstance(pts,list) or not isinstance(durations,list) or not 1<=len(pts)<=MAX_OUTPUT_FRAMES or len(pts)!=len(durations):raise ValueError('frame table size')
    if any(type(v)is not int or abs(v)>=2**62 for v in pts) or any(a>=b for a,b in zip(pts,pts[1:])):raise ValueError('strict native PTS')
    if any(type(v)is not int or not 0<=v<2**62 for v in durations) or durations[-1]<=0:raise ValueError('known final native duration')
    return base

def selected_clock(clock,start_frame,end_frame):
    validate_clock(clock);n=len(clock['pts'])
    end_frame=n if end_frame is None else end_frame
    if type(start_frame)is not int or type(end_frame)is not int or not 0<=start_frame<end_frame<=n:raise ValueError('half-open native frame selection')
    # A selected frame covers up to the next actual PTS. The final source
    # frame uses its separately probed native duration, never an average FPS.
    durations=[b-a for a,b in zip(clock['pts'],clock['pts'][1:])]+[clock['durations'][-1]]
    if end_frame-start_frame>MAX_FRAMES:raise ValueError('selected frame count budget')
    return dict(time_base=clock['time_base'],pts=clock['pts'][start_frame:end_frame],durations=durations[start_frame:end_frame])

def subdivision(clock,factor):
    base=validate_clock(clock)
    if type(factor)is not int or not 2<=factor<=8:raise ValueError('factor must be integer2..8')
    denominator=base.denominator*factor
    if denominator>MAX_DENOMINATOR or len(clock['pts'])*factor>MAX_OUTPUT_FRAMES:raise ValueError('output native clock budget')
    origin=clock['pts'][0];pts=[];durations=[]
    for index,point in enumerate(clock['pts']):
        duration=clock['pts'][index+1]-point if index+1<len(clock['pts']) else clock['durations'][-1]
        for k in range(factor):
            pts.append(((point-origin)*factor+k*duration)*base.numerator)
            durations.append(duration*base.numerator)
    if any(a>=b for a,b in zip(pts,pts[1:])) or pts[-1]+durations[-1]>=2**63:raise ValueError('output PTS overflow')
    return dict(time_base='1/'+str(denominator),pts=pts,durations=durations)

def duration_seconds(clock):
    base=validate_clock(clock)
    return (clock['pts'][-1]-clock['pts'][0]+clock['durations'][-1])*base

def lookup(values,first=0,end=None):
    end=len(values) if end is None else end
    if end-first==1:return str(values[first])
    if end<=first:raise ValueError('empty packet expression')
    middle=(first+end)//2
    return f'if(lt(N,{middle}),{lookup(values,first,middle)},{lookup(values,middle,end)})'

def packet_filter(clock):
    # Both packet clocks and every duration are explicit. An owned option file
    # avoids Windows command-line limits; qtrle emits exactly one packet/frame.
    value="setts=ts='"+lookup(clock['pts'])+"':duration='"+lookup(clock['durations'])+"':time_base="+clock['time_base']
    if len(value.encode('ascii'))>16*1024**2:raise ValueError('packet expression budget')
    return value
