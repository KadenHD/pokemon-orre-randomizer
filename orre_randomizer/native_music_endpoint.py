"""Read-only routing of WaveOut to Cubeb's Windows default eConsole endpoint."""
from __future__ import annotations

import ctypes as C
import uuid


class _Guid(C.Structure):
    _fields_ = [('data1', C.c_uint32), ('data2', C.c_uint16), ('data3', C.c_uint16), ('data4', C.c_ubyte * 8)]


def _guid(value):
    return _Guid.from_buffer_copy(uuid.UUID(value).bytes_le)


def _method(pointer, index, result, *arguments):
    table = C.cast(pointer, C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(result, C.c_void_p, *arguments)(table[index])


def default_console_endpoint():
    """Return IMMDevice's ID without opening a stream or changing any settings."""
    ole = C.WinDLL('ole32')
    ole.CoInitializeEx.argtypes = [C.c_void_p, C.c_uint32]
    ole.CoInitializeEx.restype = C.c_long
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None
    ole.CoCreateInstance.argtypes = [C.POINTER(_Guid), C.c_void_p, C.c_uint32, C.POINTER(_Guid), C.POINTER(C.c_void_p)]
    ole.CoCreateInstance.restype = C.c_long
    ole.CoTaskMemFree.argtypes = [C.c_void_p]
    ole.CoTaskMemFree.restype = None
    initialized = False
    # Separate pointer objects are necessary; each COM out parameter is mutable.
    enumerator, device, identifier = C.c_void_p(), C.c_void_p(), C.c_void_p()
    try:
        result = ole.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED
        initialized = result in (0, 1)
        # An existing STA is usable for these synchronous read-only calls.
        if result < 0 and result != -2147417850:  # RPC_E_CHANGED_MODE
            raise OSError('Cannot initialize the read-only audio endpoint query')
        clsid = _guid('BCDE0395-E52F-467C-8E3D-C4579291692E')
        iid = _guid('A95664D2-9614-4F35-A746-DE8DB63617E6')
        if ole.CoCreateInstance(C.byref(clsid), None, 1, C.byref(iid), C.byref(enumerator)) < 0 or not enumerator.value:
            raise OSError('Cannot enumerate the Dolphin audio endpoint')
        get_default = _method(enumerator, 4, C.c_long, C.c_int, C.c_int, C.POINTER(C.c_void_p))
        if get_default(enumerator, 0, 0, C.byref(device)) < 0:  # eRender, eConsole
            raise OSError('The default Dolphin audio endpoint is unavailable')
        get_id = _method(device, 5, C.c_long, C.POINTER(C.c_void_p))
        if get_id(device, C.byref(identifier)) < 0 or not identifier.value:
            raise OSError('Cannot identify the default Dolphin audio endpoint')
        result = C.wstring_at(identifier)
        if not result or len(result) > 32768:
            raise OSError('Invalid default Dolphin audio endpoint ID')
        return result
    finally:
        if identifier.value:
            ole.CoTaskMemFree(identifier)
        for pointer in (device, enumerator):
            if pointer.value:
                _method(pointer, 2, C.c_uint32)(pointer)  # IUnknown::Release
        if initialized:
            ole.CoUninitialize()


def waveout_endpoint(library, device_id):
    """Resolve a WinMM device/mapper ID to the corresponding IMMDevice ID."""
    size = C.c_uint32()
    # mmddk.h: DRV_QUERYFUNCTIONINSTANCEIDSIZE=DRV_RESERVED+18,
    # DRV_QUERYFUNCTIONINSTANCEID=DRV_RESERVED+17. Size is in bytes.
    if library.waveOutMessage(C.c_void_p(device_id), 0x0812, C.addressof(size), 0):
        return None
    if not 2 <= size.value <= 65536 or size.value % 2:
        return None
    buffer = C.create_unicode_buffer(size.value // 2)
    if library.waveOutMessage(C.c_void_p(device_id), 0x0811, C.addressof(buffer), size.value):
        return None
    return buffer.value


def matching_waveout_device(library, *, endpoint=None):
    """Prefer the mapper when matched, otherwise select a matching WinMM ID.

    An unidentified/different endpoint refuses companion playback. Native
    Dolphin audio remains available through its expired/disabled gain lease.
    """
    library.waveOutMessage.argtypes = [C.c_void_p, C.c_uint32, C.c_size_t, C.c_size_t]
    library.waveOutMessage.restype = C.c_uint32
    library.waveOutGetNumDevs.argtypes = []
    library.waveOutGetNumDevs.restype = C.c_uint32
    endpoint = endpoint or default_console_endpoint()
    mapper = waveout_endpoint(library, 0xffffffff)
    if mapper and mapper.casefold() == endpoint.casefold():
        return 0xffffffff, endpoint
    count = library.waveOutGetNumDevs()
    if not 0 <= count <= 256:
        raise OSError('WinMM audio endpoint count exceeds bounds')
    for device in range(count):
        candidate = waveout_endpoint(library, device)
        if candidate and candidate.casefold() == endpoint.casefold():
            return device, endpoint
    raise OSError('Gameplay music and Dolphin have no matching audio output; native audio restored')
