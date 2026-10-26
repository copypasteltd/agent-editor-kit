"""Bounded render-owned control pipes; shared memory still carries all pixels.

Only a child process's inherited stdin/stdout are used. No listener, network,
temporary control files, pickle or global worker registry is involved.
"""
from __future__ import annotations

import json
import queue
import struct
import threading

from .float_gpu_native import error

PROTOCOL = 'owned-inherited-binary-pipes-v1'
MAX_CONTROL = 128*1024
_HEADER = struct.Struct('!I')


def encode_packet(value):
    if not isinstance(value, dict):
        raise error('PROTOCOL', 'GPU控制消息必须为对象')
    try:
        body = json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':')).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise error('PROTOCOL', 'GPU控制消息不是有限UTF-8 JSON对象') from exc
    if not 1 <= len(body) <= MAX_CONTROL:
        raise error('PROTOCOL', 'GPU控制消息超过128KiB', bytes=len(body))
    return _HEADER.pack(len(body))+body


def _exact(stream, length, *, initial=False):
    chunks = bytearray()
    while len(chunks) < length:
        value = stream.read(length-len(chunks))
        if not value:
            if initial and not chunks:
                return None
            raise error('PROTOCOL', 'GPU控制管道消息被截断')
        chunks.extend(value)
    return bytes(chunks)


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON member')
        value[key] = item
    return value


def read_packet(stream, *, with_size=False):
    header = _exact(stream, _HEADER.size, initial=True)
    if header is None:
        return None
    length = _HEADER.unpack(header)[0]
    if not 1 <= length <= MAX_CONTROL:
        raise error('PROTOCOL', 'GPU控制管道长度超出128KiB边界', bytes=length)
    body = _exact(stream, length)
    try:
        value = json.loads(body.decode('utf-8'), object_pairs_hook=_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise error('PROTOCOL', 'GPU控制管道不是完整有限UTF-8 JSON') from exc
    if not isinstance(value, dict):
        raise error('PROTOCOL', 'GPU控制消息必须为对象')
    return (value, length+_HEADER.size) if with_size else value


def write_packet(stream, packet):
    view = memoryview(packet)
    while view:
        count = stream.write(view)
        if not count or count > len(view):
            raise error('PROTOCOL', 'GPU控制管道写入未完成')
        view = view[count:]
    stream.flush()


class OwnedPipeControl:
    """Two bounded I/O queues keep OS pipe backpressure off the cancel thread.

    The owner must stop/wait for its child before close(), so a blocked native
    read or write is released by the child's handle closure. Both helper
    threads are joined and their actual state is recorded in the receipt.
    """
    def __init__(self, process):
        self.process = process
        self.input, self.output = process.stdin, process.stdout
        if self.input is None or self.output is None:
            raise error('PROTOCOL', 'GPU进程缺少任务自有管道')
        self.stop = threading.Event()
        self.outgoing, self.incoming = queue.Queue(1), queue.Queue(1)
        self.evidence = {'protocol': PROTOCOL, 'max_packet_bytes': MAX_CONTROL,
            'queue_capacity_each': 1, 'pixel_payload': False, 'network': False,
            'transient_control_persisted': False, 'sent_packets': 0,
            'received_packets': 0, 'sent_bytes': 0, 'received_bytes': 0,
            'threads_closed': False}
        self.threads = [threading.Thread(target=self._writer, name='aek-gpu-send', daemon=True),
                        threading.Thread(target=self._reader, name='aek-gpu-receive', daemon=True)]
        self.closed = False
        for thread in self.threads:
            thread.start()

    def _deliver(self, value):
        while not self.stop.is_set():
            try:
                self.incoming.put(value, timeout=.02)
                return
            except queue.Full:
                pass

    def _writer(self):
        try:
            while not self.stop.is_set():
                try: packet = self.outgoing.get(timeout=.02)
                except queue.Empty: continue
                if self.stop.is_set(): break
                write_packet(self.input, packet)
                self.evidence['sent_packets'] += 1
                self.evidence['sent_bytes'] += len(packet)
        except BaseException as exc:
            self._deliver(('error', exc))

    def _reader(self):
        try:
            while not self.stop.is_set():
                packet = read_packet(self.output, with_size=True)
                if packet is None:
                    self._deliver(('eof', None))
                    return
                value, length = packet
                self.evidence['received_packets'] += 1
                self.evidence['received_bytes'] += length
                self._deliver(('packet', value))
        except BaseException as exc:
            self._deliver(('error', exc))

    def send(self, value):
        if self.closed or self.stop.is_set():
            raise error('STATE', 'GPU控制管道已关闭')
        packet = encode_packet(value)
        try: self.outgoing.put_nowait(packet)
        except queue.Full as exc:
            raise error('PROTOCOL', 'GPU控制管道尚有未发送消息') from exc

    def receive(self, timeout):
        try: kind, value = self.incoming.get(timeout=max(0., timeout))
        except queue.Empty: return None
        if kind == 'packet': return value
        if kind == 'eof':
            raise error('WORKER_EXIT', '本任务GPU控制管道已关闭', returncode=self.process.poll())
        if getattr(value, 'code', None): raise value
        raise error('PROTOCOL', '本任务GPU控制管道读写失败', detail=str(value)[:1000]) from value

    def close(self):
        if self.closed: return
        self.stop.set()
        for thread in self.threads:
            thread.join(timeout=2)
        self.evidence['threads_closed'] = all(not thread.is_alive() for thread in self.threads)
        # Do not close a stream while a thread is still in its OS I/O call.
        if self.evidence['threads_closed']:
            self.input.close()
            self.output.close()
        self.evidence['streams_closed'] = self.input.closed and self.output.closed
        self.closed = True
