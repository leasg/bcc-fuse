#!/usr/bin/env python

import ctypes
from builtins import input
from bpf import BPF
import fcntl
import os
from subprocess import call
import sys
import time

bcc = ctypes.CDLL("libbccclient.so")
bcc.bcc_recv_fd.restype = int
bcc.bcc_recv_fd.argtypes = [ctypes.c_char_p]

call(["bcc-fuser", "-s", "/tmp/bcc"])

if not os.path.exists("/tmp/bcc/foo"):
    os.mkdir("/tmp/bcc/foo")

# First, create a valid C but invalid BPF program, check the error message
with open("/tmp/bcc/foo/source", "w") as f:
    f.write("""
int hello(void *ctx) {
    for (;;) bpf_trace_printk("Hello, World %d\\n");
    return 0;
}
""")
try:
    with open("/tmp/bcc/foo/functions/hello/type", "w") as f:
        f.write('kprobe')
except:
    with open("/tmp/bcc/foo/functions/hello/error") as f:
        print("Verifier error:")
        print(f.read())
        print("Retrying...")

# Correct the error
with open("/tmp/bcc/foo/source", "w") as f:
    f.write("""
int hello(void *ctx) {
    bpf_trace_printk("Hello, World %d\\n");
    return 0;
}
""")

with open("/tmp/bcc/foo/functions/hello/type", "w") as f:
    f.write('kprobe')

# Pause here due to fuse race condition, TBD soon
time.sleep(0.2)
fd = bcc.bcc_recv_fd(b"/tmp/bcc/foo/functions/hello/fd")

if fd < 0: raise Exception("invalid fd %d" % fd)

hello = BPF.Function(None, "hello", fd)
BPF.attach_kprobe(hello, "schedule")
for i in range(0, 10): time.sleep(0.01)
with open("/sys/kernel/debug/tracing/trace_pipe") as f:
    fl = fcntl.fcntl(f.fileno(), fcntl.F_GETFL)
    fcntl.fcntl(f.fileno(), fcntl.F_SETFL, fl | os.O_NONBLOCK)
    try:
        print(f.read())
    except BlockingIOError:
        pass

call(["killall", "bcc-fuser"])
