"""Bounded, straight RGBA16 PNG delivery with an actual embedded RGB profile."""
import os,struct,zlib
from pathlib import Path
import numpy as np
from . import icc_profiles as icc
from .icc_output import blocks

SIGNATURE=b'\x89PNG\r\n\x1a\n'

def inspect(path,profile,width,height,*,cancel=lambda:None):
    """Stream-verify this module's filter-0 RGBA16 transport and every CRC."""
    import hashlib
    if type(width) is not int or type(height) is not int or min(width,height)<1 or max(width,height)>16384 or width*height>16777216:
        raise icc.error('BUDGET','PNG核验尺寸超预算')
    row_size=width*8+1;expected=row_size*height;seen=0;pixels=hashlib.sha256();pending=b'';rows=0
    inflater=zlib.decompressobj();state='header';icc_seen=False
    with Path(path).open('rb') as f:
        if f.read(8)!=SIGNATURE:raise icc.error('PNG','PNG签名无效')
        while True:
            cancel();head=f.read(8)
            if len(head)!=8:raise icc.error('PNG','PNG分块截断')
            n,kind=struct.unpack('>I4s',head)
            limit=icc.MAX_PROFILE_BYTES+65536 if kind==b'iCCP' else 65536
            if n>limit:raise icc.error('BUDGET','PNG分块超过预算')
            data=f.read(n);crc=f.read(4)
            if len(data)!=n or len(crc)!=4 or struct.unpack('>I',crc)[0]!=(zlib.crc32(kind+data)&0xffffffff):raise icc.error('PNG','PNG分块CRC或长度错误')
            if kind==b'IHDR':
                if state!='header' or data!=struct.pack('>IIBBBBB',width,height,16,6,0,0,0):raise icc.error('PNG','PNG布局/尺寸错误')
                state='profile'
            elif kind==b'iCCP':
                prefix=b'AEK output RGB\0\0'
                if state!='profile' or icc_seen or not data.startswith(prefix):raise icc.error('PNG','ICC分块位置或格式错误')
                d=zlib.decompressobj();decoded=d.decompress(data[len(prefix):],len(profile)+1)
                if decoded!=profile or not d.eof or d.unused_data or d.unconsumed_tail:raise icc.error('PNG','嵌入ICC字节不一致')
                icc_seen=True;state='pixels'
            elif kind==b'IDAT':
                if state!='pixels' or not icc_seen:raise icc.error('PNG','PNG像素分块顺序错误')
                compressed=data
                while compressed:
                    cancel();block=inflater.decompress(compressed,min(row_size,expected-seen+1));compressed=inflater.unconsumed_tail
                    seen+=len(block)
                    if seen>expected or inflater.unused_data:raise icc.error('PNG','PNG像素解压超预算/存在尾数据')
                    pending+=block
                    if len(pending)>=row_size:
                        row,pending=pending[:row_size],pending[row_size:]
                        if row[0]!=0:raise icc.error('PNG','当前ICC交付核验只接受明确filter-0')
                        pixels.update(row[1:]);rows+=1
            elif kind==b'IEND':
                if n or state!='pixels' or not inflater.eof or pending or rows!=height or seen!=expected or f.read(1):raise icc.error('PNG','PNG终止/完整帧校验失败')
                break
            else:raise icc.error('PNG','ICC交付存在未知或冲突色彩分块')
    return {'status':'verified','width':width,'height':height,'pixel_bytes':width*height*8,
        'RGBA16BE_sha256':'sha256:'+pixels.hexdigest(),'embedded_profile_exact':True,'all_chunks_CRC_verified':True}

def estimate(width,height,profile_bytes):
    raw=height*(1+width*8)
    # Conservative zlib overhead and independently chunked IDAT overhead.
    return raw+raw//100+65536+profile_bytes+profile_bytes//100+4096

def write(path,surface,profile,*,max_bytes,cancel=lambda:None):
    """Create a new file only; remove our own partial file on any failure."""
    blocks(surface,65536,icc.MAX_WORKING_BYTES)
    icc.header(profile)
    if type(max_bytes) is not int or max_bytes<estimate(surface.shape[1],surface.shape[0],len(profile)):
        raise icc.error('BUDGET','PNG16输出预算不足')
    path=Path(path);created=False;written=0
    try:
        with path.open('xb') as stream:
            created=True
            def put(data):
                nonlocal written
                cancel();written+=len(data)
                if written>max_bytes:raise icc.error('BUDGET','PNG16输出超过预算')
                stream.write(data)
            def chunk(kind,data):
                put(struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff))
            put(SIGNATURE);h,w=surface.shape[:2]
            chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,16,6,0,0,0))
            chunk(b'iCCP',b'AEK output RGB\0\0'+zlib.compress(profile))
            compressor=zlib.compressobj(6)
            def emit(data):
                for start in range(0,len(data),65536):chunk(b'IDAT',data[start:start+65536])
            for row in surface:
                cancel()
                if not np.isfinite(row).all() or np.any(row<0) or np.any(row>1):
                    raise icc.error('OUTPUT_RANGE','PNG16必须接收明确域处理后的0..1 RGBA')
                emit(compressor.compress(b'\0'+np.rint(row.astype(np.float64)*65535).astype('>u2').tobytes()))
            emit(compressor.flush());chunk(b'IEND',b'');stream.flush();os.fsync(stream.fileno())
        return {'bytes':written,'pixel_format':'RGBA16BE','embedded_profile_bytes':len(profile),
                'quantization':'nearest-even Float64 scale to unsigned16; straight alpha',
                'conflicting_colour_chunks':False}
    except BaseException:
        if created:path.unlink(missing_ok=True)
        raise
