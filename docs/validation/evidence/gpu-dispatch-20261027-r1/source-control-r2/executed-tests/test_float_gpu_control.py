"""Control framing and real native-child backpressure/lifetime regressions."""
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import unittest

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_gpu_control import (
    MAX_CONTROL, OwnedPipeControl, encode_packet, read_packet, write_packet,
)


class FragmentedBytes(io.BytesIO):
    def read(self, length=-1): return super().read(min(3, length))
    def write(self, value): return super().write(value[:3])


class PacketTests(unittest.TestCase):
    def test_fragmented_unicode_and_multiple_packets(self):
        values = [{'sequence': 1, 'label': '中文訊息'}, {'sequence': 2, 'ok': True}]
        stream = FragmentedBytes()
        for value in values: write_packet(stream, encode_packet(value))
        stream.seek(0)
        self.assertEqual([read_packet(stream) for _ in values], values)
        self.assertIsNone(read_packet(stream))

    def test_truncated_header_and_body(self):
        packet = encode_packet({'x': 'value'})
        for length in (1, 3, 4, len(packet)-1):
            with self.subTest(length=length), self.assertRaises(AppError):
                read_packet(FragmentedBytes(packet[:length]))

    def test_oversize_header_rejected_before_reading_body(self):
        class HeaderOnly:
            def __init__(self): self.calls = 0
            def read(self, n):
                self.calls += 1
                if self.calls > 1: raise AssertionError('must reject before allocation/read')
                return struct.pack('!I', MAX_CONTROL+1)
        value = HeaderOnly()
        with self.assertRaises(AppError): read_packet(value)
        self.assertEqual(value.calls, 1)

    def test_zero_length_and_invalid_json_objects(self):
        bodies = [b'[]', b'null', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1,"x":2}',
                  b'\xff', b'{', b'['*1500+b'0'+b']'*1500]
        for body in bodies:
            with self.subTest(body=body[:40]), self.assertRaises(AppError):
                read_packet(io.BytesIO(struct.pack('!I', len(body))+body))
        with self.assertRaises(AppError): read_packet(io.BytesIO(b'\0\0\0\0'))

    def test_nonfinite_nonobject_and_oversize_send_rejected(self):
        for value in ([], None, {'x': float('nan')}, {'x': float('inf')},
                      {'x': 'a'*MAX_CONTROL}, {'x': '\ud800'}):
            with self.subTest(value=str(value)[:80]), self.assertRaises(AppError): encode_packet(value)

    def test_exact_payload_limit_is_accepted(self):
        value = {'x': 'a'*(MAX_CONTROL-8)}
        packet = encode_packet(value)
        self.assertEqual(len(packet), MAX_CONTROL+4)
        self.assertEqual(read_packet(io.BytesIO(packet)), value)

    def test_incomplete_native_write_is_error(self):
        class FailedWrite:
            def write(self, _): return 0
        with self.assertRaises(AppError): write_packet(FailedWrite(), encode_packet({'x': 1}))


class OwnedPipeTests(unittest.TestCase):
    def launch(self, body):
        package = str(Path(sys.modules['ai_ad_editor'].__file__).resolve().parent.parent)
        paths = [package, str(Path(np.__file__).resolve().parent.parent)]
        bootstrap = 'import sys;sys.path[:0]='+repr(paths)+';'+body
        process = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', '-c', bootstrap],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        control = OwnedPipeControl(process)
        def cleanup():
            if process.poll() is None: process.terminate()
            process.wait(timeout=5)
            control.close()
            self.assertTrue(control.evidence['threads_closed'])
            self.assertTrue(control.evidence['streams_closed'])
        self.addCleanup(cleanup)
        return process, control

    def receive(self, control, timeout=5):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            value = control.receive(.02)
            if value is not None: return value
        self.fail('child response timed out')

    def test_real_child_roundtrip_120_packets_and_eof(self):
        loop = ('while True:\n v=read_packet(sys.stdin.buffer)\n if v is None: break\n '
                'write_packet(sys.stdout.buffer,encode_packet(v))')
        body = ('from ai_ad_editor.float_gpu_control import read_packet,write_packet,encode_packet;'
                'exec('+repr(loop)+')')
        process, control = self.launch(body)
        for i in range(120):
            value = {'sequence': i, 'label': 'native pipe'}
            control.send(value)
            self.assertEqual(self.receive(control), value)
        process.terminate(); process.wait(timeout=5)
        with self.assertRaises(AppError): self.receive(control)
        self.assertEqual(control.evidence['received_packets'], 120)
        self.assertEqual(control.evidence['sent_packets'], 120)

    def test_read_timeout_is_nonblocking_for_cancel_loop(self):
        process, control = self.launch('import time;time.sleep(30)')
        started = time.monotonic()
        for _ in range(3): self.assertIsNone(control.receive(.01))
        self.assertLess(time.monotonic()-started, 1)
        self.assertIsNone(process.poll())

    def test_full_native_pipe_keeps_main_cancellable_and_cleanup_joins(self):
        process, control = self.launch('import time;time.sleep(30)')
        packet = {'x': 'a'*(MAX_CONTROL-8)}
        started = time.monotonic(); control.send(packet)
        # Let the writer take the first packet and block in a real full OS pipe.
        deadline = time.monotonic()+2
        while not control.outgoing.empty() and time.monotonic() < deadline: time.sleep(.005)
        self.assertTrue(control.outgoing.empty())
        control.send(packet)
        with self.assertRaises(AppError): control.send(packet)
        self.assertLess(time.monotonic()-started, 3)
        process.terminate(); process.wait(timeout=5); control.close()
        self.assertTrue(control.evidence['threads_closed'])
        self.assertTrue(control.evidence['streams_closed'])
        with self.assertRaises(AppError): control.send({'sequence': 3})

    def test_malformed_child_packet_propagates_structured_error(self):
        _, control = self.launch('sys.stdout.buffer.write(b"\\x00\\x02\\x00\\x01");sys.stdout.buffer.flush()')
        with self.assertRaises(AppError) as exc: self.receive(control)
        self.assertEqual(exc.exception.code, 'FLOAT_GPU_PROTOCOL')

    def test_closed_child_stdin_does_not_block_host(self):
        process, control = self.launch('import os;os.close(0);from ai_ad_editor.float_gpu_control import '
            'write_packet,encode_packet;write_packet(sys.stdout.buffer,encode_packet({"closed":True}));'
            'import time;time.sleep(30)')
        self.assertEqual(self.receive(control), {'closed': True})
        self.assertIsNone(process.poll())
        control.send({'sequence': 1})
        with self.assertRaises(AppError): self.receive(control)


if __name__ == '__main__': unittest.main(verbosity=2)
