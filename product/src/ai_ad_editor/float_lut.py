"""Project-local CUBE grading on bounded straight Float32 RGBA tiles.

The five mathematical interpolators are independently expressed as weighted
vertex sums. Native filters are verification oracles, never runtime workers.
Tables keep red-fastest CUBE file order and immutable binary32 storage.
"""
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import struct

import numpy as np

from .animation import keyframe_value
from .errors import AppError
from .float_color_signal import ColorSignal, convert_rgba
from .lut_library import resolve_lut_path, lut_library_file

PROTOCOL = 'explicit-signal-float32-cube-lut-v2'
INTERPOLATIONS = ('nearest', 'trilinear', 'tetrahedral', 'pyramid', 'prism')
INTERPOLATIONS_1D = ('nearest', 'linear', 'cosine', 'cubic', 'spline')
MAX_1D_SIZE = 65536
MAX_WORKING_BYTES = 768*1024**2
MAX_FILE_BYTES = 512*1024**2
MAX_TILE_PIXELS = 262144
MAX_PIXELS = 16777216
MAX_LINE_BYTES = 4096
MAX_FLOAT32 = float(np.finfo(np.float32).max)


def error(code, message):
    return AppError('FLOAT_LUT_'+code, message, exit_code=2)


def number(value, low=None, high=None):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise error('ARGUMENT', 'LUT数值须为有限数字')
    try:
        value = float(value)
    except (ValueError, OverflowError) as caught:
        raise error('ARGUMENT', 'LUT数值超出有限范围') from caught
    if not math.isfinite(value) or low is not None and value < low or high is not None and value > high:
        raise error('ARGUMENT', 'LUT数值超出声明范围')
    return value


def _poll(cancel):
    if cancel is not None and not callable(cancel):
        raise error('ARGUMENT', '取消回调无效')
    return cancel if cancel is not None else lambda:None


def _budget(value):
    if type(value) is not int or not 1 <= value <= MAX_WORKING_BYTES:
        raise error('BUDGET', 'LUT工作区须为1字节到768MiB的整数')
    return value


@dataclass(frozen=True)
class Dependency:
    path: str
    root: str
    size: int
    sha256: str


def _local(root, raw):
    if not isinstance(raw, str) or not raw or raw.startswith(('\\\\', '//')) or '\x00' in raw:
        raise error('RESOURCE', 'LUT须为项目内本地文件')
    # Permit Windows drive names, reject URI protocols and UNC/network shares.
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', raw) and not re.match(r'^[A-Za-z]:[/\\]', raw):
        raise error('RESOURCE', 'LUT运行时不接受URL或网络协议')
    path = (root/Path(raw)).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise error('RESOURCE', 'LUT资源不存在或位于项目之外')
    return path


def _digest(path, root, poll):
    digest = hashlib.sha256()
    total = 0
    with path.open('rb') as handle:
        while True:
            poll()
            chunk = handle.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise error('BUDGET', 'LUT资源文件超过512MiB')
            digest.update(chunk)
    return Dependency(str(path), str(root), total, 'sha256:'+digest.hexdigest())


def verify_dependencies(dependencies, *, cancel=None):
    poll = _poll(cancel)
    for dependency in dependencies:
        poll()
        try:
            path = _local(Path(dependency.root), dependency.path)
            current = _digest(path, Path(dependency.root), poll)
        except (OSError, ValueError) as caught:
            raise error('RESOURCE_CHANGED', 'LUT依赖在执行期间不可读') from caught
        if current != dependency:
            raise error('RESOURCE_CHANGED', 'LUT文件或登记库在编译后已变化')
    poll()


@dataclass(frozen=True)
class Cube:
    size: int
    domain_min: tuple
    domain_max: tuple
    payload: bytes = field(repr=False)
    dependency: Dependency
    size_1d: int = 0
    domain_1d_min: tuple = (0., 0., 0.)
    domain_1d_max: tuple = (1., 1., 1.)
    dialect: str = 'iridas'

    @property
    def table(self):
        if not self.size:
            raise error('FORMAT', '独立1D LUT没有3D表')
        return np.frombuffer(self.payload, '<f4', offset=self.size_1d*12).reshape(self.size, self.size, self.size, 3)

    @property
    def table_1d(self):
        if not self.size_1d:
            raise error('FORMAT', '独立3D LUT没有1D表')
        return np.frombuffer(self.payload, '<f4', count=self.size_1d*3).reshape(self.size_1d, 3)


def _parse_cube(path, root, poll, max_working_bytes):
    if path.suffix.lower() != '.cube':
        raise error('FORMAT', '浮点LUT接受完整1D、3D或1D前置shaper的CUBE；其他格式须先显式转换')
    if not 0 < path.stat().st_size <= MAX_FILE_BYTES:
        raise error('BUDGET', 'CUBE文件为空或超过512MiB')
    digest, total, count = hashlib.sha256(), 0, 0
    size, size_1d, expected, storage = 0, 0, 0, None
    seen, minima, maxima, ranges = set(), (0., 0., 0.), (1., 1., 1.), {}
    headers = {'TITLE','LUT_3D_SIZE','LUT_1D_SIZE','DOMAIN_MIN','DOMAIN_MAX',
        'LUT_1D_INPUT_RANGE','LUT_3D_INPUT_RANGE'}
    try:
        with path.open('rb') as handle:
            line_index = 0
            while True:
                poll()
                raw = handle.readline(MAX_LINE_BYTES+1)
                if not raw:
                    break
                line_index += 1
                digest.update(raw); total += len(raw)
                if len(raw) > MAX_LINE_BYTES or total > MAX_FILE_BYTES:
                    raise error('BUDGET', 'CUBE单行或总文件长度超过预算')
                line = raw.decode('utf-8-sig' if line_index == 1 else 'utf-8').strip()
                if line.startswith('TITLE '):
                    title = re.fullmatch(r'(TITLE\s+"[^"\r\n]*")\s*(?:#.*)?',line)
                    if title is None: raise error('FORMAT', 'CUBE TITLE格式无效')
                    line = title[1]
                else:
                    line = line.split('#',1)[0].strip()
                if not line:
                    continue
                parts = line.split()
                header = parts[0]
                if header in headers:
                    if count or header in seen:
                        raise error('FORMAT', 'CUBE头重复或出现在数据之后')
                    seen.add(header)
                    if header == 'TITLE':
                        if not re.fullmatch(r'TITLE\s+"[^"\r\n]*"', line):
                            raise error('FORMAT', 'CUBE TITLE须为带引号的单行字符串')
                    elif header in ('LUT_3D_SIZE','LUT_1D_SIZE'):
                        if len(parts) != 2 or not re.fullmatch(r'[0-9]+', parts[1]):
                            raise error('FORMAT', 'CUBE尺寸须为范围内整数')
                        candidate = int(parts[1])
                        limit = MAX_1D_SIZE if header=='LUT_1D_SIZE' else 256
                        if not 2 <= candidate <= limit:
                            raise error('FORMAT', 'CUBE 1D须2到65536点；3D须每轴2到256点')
                        if header=='LUT_1D_SIZE': size_1d = candidate
                        else: size = candidate
                        expected = size_1d+size**3
                        if 2*expected*12+131072 > max_working_bytes:
                            raise error('BUDGET', 'CUBE表与冻结副本超过工作区估算')
                    elif header.endswith('_INPUT_RANGE'):
                        if len(parts)!=3:
                            raise error('FORMAT', 'CUBE INPUT_RANGE须为两个有限递增数')
                        values = tuple(float(v) for v in parts[1:])
                        if not all(math.isfinite(v) and abs(v)<=1e30 for v in values) or values[1]<=values[0]:
                            raise error('FORMAT', 'CUBE INPUT_RANGE须为两个有限递增数')
                        ranges[header] = values
                    else:
                        if len(parts) != 4:
                            raise error('FORMAT', 'CUBE DOMAIN须为三个有限数')
                        values = tuple(float(v) for v in parts[1:])
                        if not all(math.isfinite(v) and abs(v) <= 1e30 for v in values):
                            raise error('FORMAT', 'CUBE DOMAIN超出有限范围')
                        if header == 'DOMAIN_MIN': minima = values
                        else: maxima = values
                    continue
                if not expected or len(parts) != 3 or count >= expected:
                    raise error('FORMAT', 'CUBE须有完整且无额外扩展的1D/3D样本')
                if storage is None:
                    storage = bytearray(expected*12)
                values = tuple(float(v) for v in parts)
                if not all(math.isfinite(v) and abs(v) <= MAX_FLOAT32 for v in values):
                    raise error('FORMAT', 'CUBE样本须为有限Float32')
                struct.pack_into('<fff', storage, count*12, *values)
                count += 1
    except (ValueError, UnicodeError, OverflowError, struct.error) as caught:
        raise error('FORMAT', 'CUBE编码、数字或数据格式无效') from caught
    if not expected or count != expected or any(b <= a for a, b in zip(minima, maxima)):
        raise error('FORMAT', 'CUBE样本数或DOMAIN范围无效')
    domains_present = bool(seen & {'DOMAIN_MIN','DOMAIN_MAX'})
    if domains_present and (ranges or size and size_1d):
        raise error('FORMAT', 'DOMAIN不能与Resolve INPUT_RANGE或组合shaper混用')
    if 'LUT_1D_INPUT_RANGE' in ranges and not size_1d or 'LUT_3D_INPUT_RANGE' in ranges and not size:
        raise error('FORMAT', 'INPUT_RANGE没有对应维度的LUT')
    minima_1d, maxima_1d = (0.,0.,0.), (1.,1.,1.)
    if size_1d:
        if domains_present: minima_1d,maxima_1d = minima,maxima
        elif 'LUT_1D_INPUT_RANGE' in ranges:
            a,b = ranges['LUT_1D_INPUT_RANGE'];minima_1d,maxima_1d = (a,)*3,(b,)*3
    if 'LUT_3D_INPUT_RANGE' in ranges:
        a,b = ranges['LUT_3D_INPUT_RANGE'];minima,maxima = (a,)*3,(b,)*3
    dialect = 'resolve' if ranges or size and size_1d else 'iridas'
    dependency = Dependency(str(path), str(root), total, 'sha256:'+digest.hexdigest())
    verify_dependencies((dependency,), cancel=poll)
    poll()
    return Cube(size, minima, maxima, bytes(storage), dependency, size_1d, minima_1d, maxima_1d, dialect)


def _signal(value):
    from .float_hdr import parse_signal
    return parse_signal(value)


def _tracks(effect, parameters):
    if 'keyframes' in effect and 'keyframes' in parameters:
        raise error('ARGUMENT', 'LUT关键帧只能声明在一个层级')
    raw = effect.get('keyframes', parameters.get('keyframes', []))
    if not isinstance(raw, list) or len(raw) > 1:
        raise error('ARGUMENT', '浮点LUT只支持单条intensity轨道')
    tracks = []
    for track in raw:
        if not isinstance(track, dict) or set(track) != {'property', 'keyframes'} or not isinstance(track['property'], str):
            raise error('ARGUMENT', 'LUT强度轨道格式无效')
        name = track['property'].strip().lower().replace('-', '_')
        for prefix in ('effect.', 'parameters.', str(effect['type']).lower().replace('-', '_')+'.'):
            if name.startswith(prefix):
                name = name[len(prefix):]; break
        keys = track['keyframes']
        if name != 'intensity' or not isinstance(keys, list) or not 1 <= len(keys) <= 1024:
            raise error('ARGUMENT', 'LUT仅支持1到1024个intensity关键帧')
        previous = -1
        for key in keys:
            if not isinstance(key, dict) or set(key)-{'at_tick','value','interpolation','control_points'}:
                raise error('ARGUMENT', 'LUT关键帧包含未知字段')
            if type(key.get('at_tick')) is not int or key['at_tick'] <= previous:
                raise error('ARGUMENT', 'LUT关键帧须为递增非负整数时钟')
            previous = key['at_tick']; number(key.get('value'), 0, 1)
            mode = key.get('interpolation','linear')
            if mode not in ('linear','hold','ease_in','ease_out','ease_in_out','bezier'):
                raise error('ARGUMENT', 'LUT关键帧插值未知')
            if mode == 'bezier':
                cp = key.get('control_points')
                if not isinstance(cp,list) or len(cp) not in (2,4):
                    raise error('ARGUMENT', 'LUT Bezier须为2或4个有限控制值')
                cp = [number(v) for v in cp]
                if len(cp)==4 and (not 0<=cp[0]<=1 or not 0<=cp[2]<=1):
                    raise error('ARGUMENT', 'LUT Bezier横向控制值须在0到1')
        tracks.append({'property':'intensity','keyframes':keys})
    return json.dumps({'keyframes':tracks},sort_keys=True,allow_nan=False,separators=(',',':'))


@dataclass(frozen=True)
class LUTPlan:
    cube: Cube
    input_signal: ColorSignal
    output_signal: ColorSignal
    intensity: float
    interpolation: str
    tracks_json: str
    dependencies: tuple
    interpolation_1d: str = 'linear'


def compile_lut(effect, *, resource_root, cache=None, max_working_bytes=MAX_WORKING_BYTES, cancel=None):
    """Bind a complete local table, explicit signals and immutable author tracks."""
    poll = _poll(cancel); poll(); _budget(max_working_bytes)
    if resource_root is None:
        raise error('RESOURCE', '浮点LUT需要明确项目resource_root')
    root = Path(resource_root).resolve()
    if not root.is_dir() or str(root).startswith(('\\\\','//')):
        raise error('RESOURCE', '浮点LUT项目根目录须为现有本地目录')
    if not isinstance(effect,dict) or set(effect)-{'type','id','enabled','parameters','keyframes'}:
        raise error('ARGUMENT', '浮点LUT包含未知字段；参数须置于parameters')
    parameters = effect.get('parameters',{})
    allowed = {'path','file','lut','lut_id','interpolation','interpolation_1d','intensity','input_signal','output_signal','keyframes'}
    if not isinstance(parameters,dict) or set(parameters)-allowed:
        raise error('ARGUMENT', '浮点LUT参数包含未知字段')
    interpolation = parameters.get('interpolation','tetrahedral')
    if interpolation not in INTERPOLATIONS:
        raise error('ARGUMENT', 'LUT插值须为已声明的五种之一')
    interpolation_1d = parameters.get('interpolation_1d','linear')
    if interpolation_1d not in INTERPOLATIONS_1D:
        raise error('ARGUMENT', '1D LUT插值须为nearest、linear、cosine、cubic或spline')
    intensity = number(parameters.get('intensity',1),0,1)
    input_signal, output_signal = _signal(parameters.get('input_signal')), _signal(parameters.get('output_signal'))
    tracks_json = _tracks(effect,parameters)
    aliases = [parameters[k] for k in ('path','file','lut') if k in parameters]
    if aliases and any(v != aliases[0] for v in aliases):
        raise error('RESOURCE', 'LUT路径别名冲突')
    dependencies, expected = [], None
    if 'lut_id' in parameters:
        if aliases or not isinstance(parameters['lut_id'],str) or not parameters['lut_id']:
            raise error('RESOURCE', 'LUT登记ID与路径不能混用')
        registry = _local(root,str(lut_library_file(root)))
        before = _digest(registry,root,poll)
        resolved = resolve_lut_path(root,parameters['lut_id'])
        if resolved is None:
            raise error('RESOURCE', 'LUT登记ID不存在')
        path, record = resolved
        path = _local(root,str(path))
        expected = record.get('sha256')
        if not isinstance(expected,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',expected):
            raise error('RESOURCE', '登记LUT缺少有效SHA-256')
        verify_dependencies((before,),cancel=poll); dependencies.append(before)
    else:
        if not aliases:
            raise error('RESOURCE', 'LUT须提供项目内路径或登记ID')
        path = _local(root,aliases[0])
    cache = {} if cache is None else cache
    key = str(path)
    if key in cache:
        cube = cache[key]; verify_dependencies((cube.dependency,),cancel=poll)
    else:
        retained = sum(len(v.payload) for v in cache.values())
        cube = _parse_cube(path,root,poll,max_working_bytes-retained)
        cache[key] = cube
    if expected is not None and cube.dependency.sha256 != expected:
        raise error('RESOURCE_CHANGED', '登记LUT的SHA-256与实际文件不符')
    if 'interpolation_1d' in parameters and not cube.size_1d:
        raise error('ARGUMENT', 'interpolation_1d要求文件含1D LUT或shaper')
    dependencies.append(cube.dependency)
    return LUTPlan(cube,input_signal,output_signal,intensity,interpolation,tracks_json,tuple(dependencies),interpolation_1d)


def _lookup_1d(cube, rgb, method):
    """Independent channel weights; replicated endpoints, unclipped outputs.

    Cubic uses unit finite-difference tangents, spline uses half tangents.
    Domain normalization is explicit even when minima are nonzero, unlike
    legacy filters that scale values without subtracting the domain origin.
    """
    n = cube.size_1d
    q = (np.clip((rgb-np.asarray(cube.domain_1d_min))/
        (np.asarray(cube.domain_1d_max)-cube.domain_1d_min),0,1).astype(np.float32)*np.float32(n-1)).astype(np.float64)
    channels = np.arange(3)[None,:]
    if method=='nearest':
        return cube.table_1d[np.floor(q+.5).astype(np.int64),channels].astype(np.float64)
    low = np.floor(q).astype(np.int64);high = np.minimum(low+1,n-1);t = q-low
    def sample(index): return cube.table_1d[index,channels].astype(np.float64)
    if method in ('linear','cosine'):
        u = t if method=='linear' else (1-np.cos(np.pi*t))*.5
        return sample(low)*(1-u)+sample(high)*u
    t2,t3 = t*t,t*t*t
    if method=='cubic':
        weights = (-t3+2*t2-t, t3-2*t2+1, -t3+t2+t, t3-t2)
    else:
        weights = (-.5*t3+t2-.5*t, 1.5*t3-2.5*t2+1, -1.5*t3+2*t2+.5*t, .5*t3-.5*t2)
    indexes = (np.maximum(low-1,0),low,high,np.minimum(high+1,n-1))
    return sum(sample(index)*weight for index,weight in zip(indexes,weights))


def _lookup(cube, rgb, method):
    n = cube.size
    # Native binary32 grid coordinates are part of the convention. In
    # particular, exact grid planes/ties must not select a different pyramid
    # face merely because a wider temporary retains a sub-ulp fraction.
    coordinates = (np.clip((rgb-np.asarray(cube.domain_min))/(np.asarray(cube.domain_max)-cube.domain_min),0,1)
        .astype(np.float32)*np.float32(n-1)).astype(np.float64)
    table = cube.table
    if method == 'nearest':
        indices = np.floor(coordinates+.5).astype(np.int64)
        return table[indices[:,2],indices[:,1],indices[:,0]].astype(np.float64)
    low = np.floor(coordinates).astype(np.int64)
    high = np.minimum(low+1,n-1)
    fraction = coordinates-low
    result = np.zeros((len(rgb),3),np.float64)
    def vertex(bits):
        index = np.where(bits,high,low)
        return table[index[:,2],index[:,1],index[:,0]].astype(np.float64)
    if method == 'trilinear':
        for code in range(8):
            bits = np.array([(code>>axis)&1 for axis in range(3)],dtype=bool)
            weights = np.prod(np.where(bits,fraction,1-fraction),axis=1)
            result += vertex(bits)*weights[:,None]
    elif method == 'tetrahedral':
        order = np.argsort(-fraction,axis=1,kind='stable')
        sorted_f = np.take_along_axis(fraction,order,axis=1)
        weights = np.column_stack((1-sorted_f[:,0],sorted_f[:,0]-sorted_f[:,1],sorted_f[:,1]-sorted_f[:,2],sorted_f[:,2]))
        bits = np.zeros_like(low,dtype=bool)
        for level in range(4):
            result += vertex(bits)*weights[:,level,None]
            if level < 3: bits[np.arange(len(rgb)),order[:,level]] = True
    elif method == 'prism':
        # Two triangles in the R/B square, each linearly extruded along G.
        blue_first = fraction[:,2] > fraction[:,0]
        major = np.where(blue_first,2,0); minor = 2-major
        larger = np.take_along_axis(fraction,major[:,None],axis=1)[:,0]
        smaller = np.take_along_axis(fraction,minor[:,None],axis=1)[:,0]
        triangle_weights = (1-larger,larger-smaller,smaller)
        for green in (False,True):
            bits = np.zeros_like(low,dtype=bool); bits[:,1] = green
            vertical = fraction[:,1] if green else 1-fraction[:,1]
            for level in range(3):
                result += vertex(bits)*(triangle_weights[level]*vertical)[:,None]
                if level==0: bits[np.arange(len(rgb)),major] = True
                elif level==1: bits[:,[0,2]] = True
    else:
        # Native pyramid convention: bilinear on a selected zero-axis face,
        # then a correction toward the opposite diagonal. Strict comparisons
        # intentionally retain the native third-axis tie convention.
        r,g,b = fraction.T
        selected = np.where((g>r)&(b>r),0,np.where((r>g)&(b>g),1,2))
        for axis in range(3):
            chosen = selected==axis
            if not np.any(chosen): continue
            other = [a for a in range(3) if a!=axis]
            subtotal = np.zeros_like(result)
            for code in range(4):
                bits = np.zeros(3,dtype=bool)
                bits[other] = [bool(code&1),bool(code&2)]
                weight = np.prod(np.where(bits[other],fraction[:,other],1-fraction[:,other]),axis=1)
                subtotal += vertex(bits)*weight[:,None]
            far = np.ones(3,dtype=bool); far[axis] = False
            subtotal += (vertex(np.ones(3,dtype=bool))-vertex(far))*fraction[:,axis,None]
            result[chosen] = subtotal[chosen]
    return result


def apply_lut(surface, plan, author_tick, *, working_signal, tile_pixels=65536,
              retained_table_bytes=None, max_working_bytes=MAX_WORKING_BYTES, cancel=None):
    """Grade in declared LUT signals; mix in the common linear working signal.

    Domain coordinates clamp to the CUBE boundary; table outputs never clip.
    Bezier overshoot clamps intensity to [0,1]. Alpha bits always pass through.
    Source and table are immutable inputs; file identities are checked by the
    enclosing render transaction before publication, not re-read per pixel.
    """
    poll = _poll(cancel); poll(); _budget(max_working_bytes)
    if not isinstance(plan,LUTPlan) or not isinstance(working_signal,ColorSignal) or working_signal.transfer!='linear':
        raise error('SIGNAL', 'LUT须使用编译计划和明确线性光工作信号')
    tick = number(float(author_tick)) if isinstance(author_tick,Fraction) else number(author_tick)
    if not isinstance(surface,np.ndarray) or surface.dtype!=np.float32 or surface.ndim!=3 or surface.shape[-1]!=4 or not surface.flags.c_contiguous:
        raise error('SURFACE', 'LUT输入须为连续H×W×4 Float32')
    height,width = surface.shape[:2]; pixels = height*width
    if min(height,width)<1 or max(height,width)>16384 or pixels>MAX_PIXELS:
        raise error('BUDGET', 'LUT表面超过尺寸预算')
    if type(tile_pixels) is not int or not 1<=tile_pixels<=MAX_TILE_PIXELS:
        raise error('BUDGET', 'LUT分块大小无效')
    retained = len(plan.cube.payload) if retained_table_bytes is None else retained_table_bytes
    if type(retained) is not int or retained<len(plan.cube.payload):
        raise error('BUDGET', 'LUT保留表大小无效')
    actual_tile = min(tile_pixels,16384)
    estimated = 3*surface.nbytes+retained+min(pixels,actual_tile)*1536+131072
    if estimated>max_working_bytes:
        raise error('BUDGET', 'LUT输入/输出、保留表与分块工作区估算超限')
    intensity = min(1.,max(0.,keyframe_value(json.loads(plan.tracks_json),('intensity',),plan.intensity,tick)))
    source = surface.reshape(-1,4); output = np.empty_like(source)
    for start in range(0,pixels,actual_tile):
        poll(); value = source[start:start+actual_tile]; target = output[start:start+len(value)]
        if not np.isfinite(value).all() or np.any(value[:,3]<0) or np.any(value[:,3]>1):
            raise error('VALUES', 'LUT RGB须有限且alpha须在0到1')
        target[:] = value
        if intensity==0: continue
        # Conversion is shared with the explicit signal contract and runs on
        # tiles, so neither intermediate scales with the full-frame count.
        transformed,_ = convert_rgba(value.reshape(1,len(value),4),working_signal,plan.input_signal,
            tile_pixels=tile_pixels,max_working_bytes=max_working_bytes,cancel=poll)
        with np.errstate(over='ignore',invalid='ignore'):
            if plan.cube.size_1d:
                transformed.reshape(-1,4)[:,:3] = _lookup_1d(plan.cube,transformed.reshape(-1,4)[:,:3].astype(np.float64),plan.interpolation_1d)
                if not np.isfinite(transformed).all():
                    raise error('VALUES', '1D LUT插值输出超出Float32有限范围')
            if plan.cube.size:
                poll()
                transformed.reshape(-1,4)[:,:3] = _lookup(plan.cube,transformed.reshape(-1,4)[:,:3].astype(np.float64),plan.interpolation)
        if not np.isfinite(transformed).all():
            raise error('VALUES', 'LUT插值输出超出Float32有限范围')
        graded,_ = convert_rgba(transformed,plan.output_signal,working_signal,
            tile_pixels=tile_pixels,max_working_bytes=max_working_bytes,cancel=poll)
        if intensity==1: target[:,:3] = graded.reshape(-1,4)[:,:3]
        else:
            with np.errstate(over='ignore',invalid='ignore'):
                target[:,:3] = value[:,:3].astype(np.float64)*(1-intensity)+graded.reshape(-1,4)[:,:3].astype(np.float64)*intensity
        if not np.isfinite(target).all():
            raise error('VALUES', 'LUT混合超出Float32有限范围')
    poll()
    return output.reshape(surface.shape),{'protocol':PROTOCOL,'interpolation':plan.interpolation,'intensity':intensity,
        'interpolation_1d':plan.interpolation_1d if plan.cube.size_1d else None,
        'table_1d_size':plan.cube.size_1d,'table_dialect':plan.cube.dialect,
        'stages':(['1D'] if plan.cube.size_1d else [])+(['3D'] if plan.cube.size else []),
        'domain_1d_min':list(plan.cube.domain_1d_min),'domain_1d_max':list(plan.cube.domain_1d_max),
        'author_tick':str(author_tick),'table_sha256':plan.cube.dependency.sha256,'table_size':plan.cube.size,
        'domain_min':list(plan.cube.domain_min),'domain_max':list(plan.cube.domain_max),
        'input_signal':vars(plan.input_signal),'output_signal':vars(plan.output_signal),'working_signal':vars(working_signal),
        'mix_domain':'linear-working-straight-RGB','coordinate_boundary':'clamp-after-domain-normalization',
        'coordinate_precision':'binary32-normalized-grid;Float64-vertex-weights',
        'alpha':'input-bits-preserved','integer_intermediate':False,'table_outputs_clipped':False,
        'intensity_zero_bit_exact':intensity==0,'estimated_working_bytes':estimated,'estimated_bytes_are_peak_RSS':False,
        'requested_tile_pixels':tile_pixels,'actual_tile_pixels_limit':actual_tile,
        'natural_quality_accepted':False,'HDR_accepted':False}
