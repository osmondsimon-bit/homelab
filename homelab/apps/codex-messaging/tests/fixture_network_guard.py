"""Constrain the mock-model child to its fixture TCP port and deny internet UDP sockets."""

import ctypes
import errno
import os
import platform
import socket
import sys


def restrict_network(port):
    """Apply Linux Landlock TCP-port rules and a small UDP-denying seccomp filter."""
    if platform.machine() != "x86_64":
        raise RuntimeError("fixture guard requires the pinned x86_64 Linux runtime")
    libc = ctypes.CDLL(None, use_errno=True)

    def checked(result):
        if result < 0:
            raise OSError(ctypes.get_errno(), "fixture network confinement failed")
        return result

    if checked(libc.syscall(444, 0, 0, 1)) < 4:
        raise RuntimeError("Landlock network confinement unavailable")

    class Ruleset(ctypes.Structure):
        _fields_ = [("filesystem", ctypes.c_uint64), ("network", ctypes.c_uint64)]

    class PortRule(ctypes.Structure):
        _fields_ = [("access", ctypes.c_uint64), ("port", ctypes.c_uint64)]

    ruleset = Ruleset(0, 3)
    descriptor = checked(libc.syscall(444, ctypes.byref(ruleset), ctypes.sizeof(ruleset), 0))
    try:
        rule = PortRule(3, port)
        checked(libc.syscall(445, descriptor, 2, ctypes.byref(rule), 0))
        checked(libc.prctl(38, 1, 0, 0, 0))
        checked(libc.syscall(446, descriptor, 0))
    finally:
        os.close(descriptor)

    class Instruction(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("yes", ctypes.c_ubyte),
                    ("no", ctypes.c_ubyte), ("value", ctypes.c_uint32)]

    class Program(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ushort), ("instructions", ctypes.POINTER(Instruction))]

    instructions = (Instruction * 10)(
        Instruction(0x20, 0, 0, 0),
        Instruction(0x15, 0, 6, 41),
        Instruction(0x20, 0, 0, 16),
        Instruction(0x15, 1, 0, socket.AF_INET),
        Instruction(0x15, 0, 3, socket.AF_INET6),
        Instruction(0x20, 0, 0, 24),
        Instruction(0x54, 0, 0, 15),
        Instruction(0x15, 1, 0, socket.SOCK_DGRAM),
        Instruction(0x06, 0, 0, 0x7FFF0000),
        Instruction(0x06, 0, 0, 0x00050000 | errno.EPERM),
    )
    program = Program(len(instructions), instructions)
    checked(libc.prctl(22, 2, ctypes.byref(program), 0, 0))


if __name__ == "__main__":
    selected_port = int(sys.argv[1])
    restrict_network(selected_port)
    with socket.socket() as denied:
        if denied.connect_ex(("127.0.0.1", 443)) not in {errno.EACCES, errno.EPERM}:
            raise RuntimeError("fixture TCP confinement self-check failed")
    try:
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except PermissionError:
        pass
    else:
        raise RuntimeError("fixture UDP confinement self-check failed")
    os.execve(sys.argv[2], sys.argv[2:], dict(os.environ))
