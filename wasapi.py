"""Windows audio capture through WASAPI, with nothing but ctypes.

DirectShow has no way to record what the speakers are playing: it needs a
loopback device the driver happens to expose ("Stereo Mix", VB-CABLE), which
most machines don't have enabled. WASAPI captures the render endpoint itself,
so the other side of a meeting arrives whatever the driver offers. The
microphone comes from the same API while we are at it, and the shared-mode
engine converts both to 16 kHz mono s16, which is what the recorder wants.

Importing this module is safe on every platform; every call is a no-op or a
WasapiError away from Windows.
"""

import ctypes
import sys
import threading

RATE = 16000


class WasapiError(Exception):
    """A WASAPI call failed; the message names it."""


_WIN = sys.platform == "win32"

if _WIN:
    _ole32 = ctypes.WinDLL("ole32", use_last_error=True)

    class _GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    class _PropertyKey(ctypes.Structure):
        _fields_ = [("fmtid", _GUID), ("pid", ctypes.c_ulong)]

    class _PropVariant(ctypes.Structure):
        # Only VT_LPWSTR (31) is ever read: vt plus one pointer.
        _fields_ = [("vt", ctypes.c_ushort), ("wReserved1", ctypes.c_ushort),
                    ("wReserved2", ctypes.c_ushort), ("wReserved3", ctypes.c_ushort),
                    ("value", ctypes.c_void_p)]

    class _WaveFormatEx(ctypes.Structure):
        _fields_ = [("wFormatTag", ctypes.c_ushort), ("nChannels", ctypes.c_ushort),
                    ("nSamplesPerSec", ctypes.c_uint), ("nAvgBytesPerSec", ctypes.c_uint),
                    ("nBlockAlign", ctypes.c_ushort), ("wBitsPerSample", ctypes.c_ushort),
                    ("cbSize", ctypes.c_ushort)]

    _ULONG = ctypes.c_ulong
    _P = ctypes.c_void_p

    _F = ctypes.WINFUNCTYPE
    _HR = _F(_ULONG, _P)
    _ENUM_ENDPOINTS = _F(_ULONG, _P, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(_P))
    _GET_DEFAULT = _F(_ULONG, _P, ctypes.c_int, ctypes.c_int, ctypes.POINTER(_P))
    _GET_DEVICE = _F(_ULONG, _P, ctypes.c_wchar_p, ctypes.POINTER(_P))
    _ACTIVATE = _F(_ULONG, _P, _P, ctypes.c_uint, _P, ctypes.POINTER(_P))
    _OPEN_STORE = _F(_ULONG, _P, ctypes.c_uint, ctypes.POINTER(_P))
    _GET_ID = _F(_ULONG, _P, ctypes.POINTER(_P))
    _GET_COUNT = _F(_ULONG, _P, ctypes.POINTER(ctypes.c_uint))
    _COLLECTION_ITEM = _F(_ULONG, _P, ctypes.c_uint, ctypes.POINTER(_P))
    _GET_VALUE = _F(_ULONG, _P, _P, _P)
    _INITIALIZE = _F(_ULONG, _P, ctypes.c_int, ctypes.c_uint, ctypes.c_uint64,
                     _P, _P, _P)
    _CLIENT_START = _F(_ULONG, _P)
    _CLIENT_STOP = _F(_ULONG, _P)
    _GET_SERVICE = _F(_ULONG, _P, _P, ctypes.POINTER(_P))
    _GET_BUFFER = _F(_ULONG, _P, ctypes.POINTER(_P), ctypes.POINTER(ctypes.c_uint),
                     ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint64),
                     ctypes.POINTER(ctypes.c_uint64))
    _GETMIX = _F(_ULONG, _P, ctypes.POINTER(_P))
    _RELEASE_BUFFER = _F(_ULONG, _P, ctypes.c_uint)
    _NEXT_PACKET = _F(_ULONG, _P, ctypes.POINTER(ctypes.c_uint))

    # ole32 calls go through argtypes-bound DLL functions; the prototypes
    # above are only for vtable calls through _call().
    _ole32.CoCreateInstance.argtypes = (
        ctypes.POINTER(_GUID), _P, ctypes.c_uint,
        ctypes.POINTER(_GUID), ctypes.POINTER(_P))
    _ole32.CoCreateInstance.restype = _ULONG
    _ole32.CLSIDFromString.argtypes = (
        ctypes.c_wchar_p, ctypes.POINTER(_GUID))
    _ole32.CLSIDFromString.restype = _ULONG
    _ole32.CoInitializeEx.argtypes = (_P, ctypes.c_uint)
    _ole32.CoInitializeEx.restype = _ULONG
    _ole32.CoTaskMemFree.argtypes = (_P,)
    _ole32.PropVariantClear.argtypes = (ctypes.POINTER(_PropVariant),)
    _ole32.PropVariantClear.restype = _ULONG

    _CLSCTX_ALL = 0x17
    _COINIT_MULTITHREADED = 0x0
    _RPC_E_CHANGED_MODE = 0x80010106
    _DEVICE_STATE_ACTIVE = 0x1
    _VT_LPWSTR = 31
    _SHARE_SHARED = 0
    _LOOPBACK = 0x00020000
    _AUTOCONVERT = 0x80000000 | 0x08000000  # AUTOCONVERTPCM | SRC_DEFAULT_QUALITY
    _SILENT = 0x2
    _BUFFER_HNS = 2_000_000  # 200 ms
    _CAPTURE, _RENDER = 1, 0

    def _guid(text):
        guid = _GUID()
        hr = _ole32.CLSIDFromString(text, ctypes.byref(guid))
        if hr:
            raise WasapiError(f"CLSIDFromString({text}) failed")
        return guid

    _KEY_FRIENDLY = _PropertyKey(
        _guid("{A45C254E-DF1C-4EFD-8020-67D146A850E0}"), 14)
    _IID_ENUM = _guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
    _IID_CLIENT = _guid("{1CB9AD4C-DBFA-4C32-B178-C2F568A703B2}")
    _IID_CAPCLIENT = _guid("{C8ADBD64-E71E-48A0-A4DE-185C395CD317}")
    _CLSID_ENUM = _guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")

    def _check(hr, what):
        if hr:
            raise WasapiError(f"{what} failed (0x{hr & 0xFFFFFFFF:08X})")

    def _com_on_thread():
        """Join the process's multithreaded apartment; one call per thread.

        The apartment is never left (no CoUninitialize): the process lives
        for the session and everything audio-related shares it, so balancing
        the call would only tear the MTA down under whoever joined first.
        Endpoints opened from an MTA thread are callable from any other MTA
        thread, which is what lets a reader thread poll what another opened.
        """
        hr = _ole32.CoInitializeEx(None, _COINIT_MULTITHREADED)
        # S_FALSE (1) means already a member; RPC_E_CHANGED_MODE means the
        # thread hosts an STA, whose pointers we would only reach through
        # marshalling — but the worker below is always fresh, so it never
        # carries one in.
        if hr not in (0, 1) and (hr & 0xFFFFFFFF) != _RPC_E_CHANGED_MODE:
            raise WasapiError(f"CoInitializeEx failed (0x{hr & 0xFFFFFFFF:08X})")

    def _call(obj, index, proto, *args):
        vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(_P))).contents
        return proto(vtbl[index])(obj, *args)

    def _release(obj):
        if obj:
            _call(obj, 2, _HR)

    def _enumerator():
        ptr = _P()
        _check(_ole32.CoCreateInstance(ctypes.byref(_CLSID_ENUM), None,
                                       _CLSCTX_ALL, ctypes.byref(_IID_ENUM),
                                       ctypes.byref(ptr)),
               "CoCreateInstance(MMDeviceEnumerator)")
        return ptr

    def _endpoint_info(dev):
        """(friendly name, id) of one IMMDevice."""
        # c_void_p, not c_wchar_p: .value must stay the raw CoTaskMemAlloc'd
        # pointer, because CoTaskMemFree has to free exactly that block — a
        # decoded Python string would have its own buffer, and freeing that
        # one corrupts the heap.
        wid = _P()
        _check(_call(dev, 5, _GET_ID, ctypes.byref(wid)), "IMMDevice::GetId")
        dev_id = ctypes.wstring_at(wid.value) if wid.value else ""
        _ole32.CoTaskMemFree(wid.value)
        name = ""
        store = _P()
        _check(_call(dev, 4, _OPEN_STORE, 0, ctypes.byref(store)),
               "IMMDevice::OpenPropertyStore")
        value = _PropVariant()
        try:
            _check(_call(store, 5, _GET_VALUE, ctypes.byref(_KEY_FRIENDLY),
                         ctypes.byref(value)),
                   "IPropertyStore::GetValue")
            if value.vt == _VT_LPWSTR and value.value:
                name = ctypes.wstring_at(value.value)
        finally:
            _ole32.PropVariantClear(ctypes.byref(value))
            _release(store)
        return name, dev_id

    def _endpoints(dataflow):
        _com_on_thread()
        enum = _enumerator()
        try:
            collection = _P()
            _check(_call(enum, 3, _ENUM_ENDPOINTS, dataflow,
                         _DEVICE_STATE_ACTIVE, ctypes.byref(collection)),
                   "EnumAudioEndpoints")
            try:
                count = ctypes.c_uint()
                _check(_call(collection, 3, _GET_COUNT, ctypes.byref(count)),
                       "IMMDeviceCollection::GetCount")
                out = []
                for index in range(count.value):
                    dev = _P()
                    _check(_call(collection, 4, _COLLECTION_ITEM, index,
                                 ctypes.byref(dev)),
                           "IMMDeviceCollection::Item")
                    try:
                        out.append(_endpoint_info(dev))
                    finally:
                        _release(dev)
                return out
            finally:
                _release(collection)
        finally:
            _release(enum)

    def _default_endpoint(dataflow):
        _com_on_thread()
        enum = _enumerator()
        try:
            dev = _P()
            _check(_call(enum, 4, _GET_DEFAULT, dataflow, 0, ctypes.byref(dev)),
                   "GetDefaultAudioEndpoint")
            try:
                return _endpoint_info(dev)
            finally:
                _release(dev)
        finally:
            _release(enum)

    def _resolve(dataflow, name):
        """IMMDevice for `name` (empty = the default endpoint of that flow)."""
        enum = _enumerator()
        try:
            dev = _P()
            if not name:
                _check(_call(enum, 4, _GET_DEFAULT, dataflow, 0,
                             ctypes.byref(dev)),
                       "GetDefaultAudioEndpoint")
                return dev
            dev_id = _pick(name, _endpoints(dataflow), "")
            # GetDevice takes the same string GetId hands out; try it braced
            # as well in case the stored spelling lost them.
            hr = 0
            for candidate in (dev_id, "{" + dev_id.strip("{}") + "}"):
                dev = _P()
                hr = _call(enum, 5, _GET_DEVICE, candidate, ctypes.byref(dev))
                if not hr:
                    return dev
            _check(hr, "IMMDeviceEnumerator::GetDevice")
        finally:
            _release(enum)

    class _Source:
        """One open endpoint, polled for packets of mono s16 at 16 kHz.

        read() never blocks: it drains whatever packets are waiting and
        returns b"" when the device is quiet — a loopback endpoint delivers
        nothing at all while no app plays sound. The lock lets the owner
        close the source from another thread without a use-after-release.
        """

        def __init__(self, client, capture, dev, friendly):
            self._client = client
            self._capture = capture
            self._dev = dev
            self.friendly_name = friendly
            self._closed = False
            self._com = False
            self._lock = threading.Lock()

        def _join_mta(self):
            if not self._com:
                _com_on_thread()
                self._com = True

        def read(self):
            with self._lock:
                if self._closed:
                    return b""
                self._join_mta()
                out = bytearray()
                while True:
                    packets = ctypes.c_uint()
                    _check(_call(self._capture, 5, _NEXT_PACKET,
                                 ctypes.byref(packets)),
                           "GetNextPacketSize")
                    if not packets.value:
                        break
                    data = _P()
                    frames = ctypes.c_uint()
                    flags = ctypes.c_uint()
                    pos = ctypes.c_uint64()
                    qpc = ctypes.c_uint64()
                    _check(_call(self._capture, 3, _GET_BUFFER,
                                 ctypes.byref(data), ctypes.byref(frames),
                                 ctypes.byref(flags), ctypes.byref(pos),
                                 ctypes.byref(qpc)),
                           "GetBuffer")
                    size = frames.value * 2
                    if flags.value & _SILENT or not data.value:
                        out += b"\x00" * size
                    else:
                        out += ctypes.string_at(data.value, size)
                    _check(_call(self._capture, 4, _RELEASE_BUFFER,
                                 frames.value),
                           "ReleaseBuffer")
                return bytes(out)

        def close(self):
            with self._lock:
                if self._closed:
                    return
                self._closed = True
                self._join_mta()
                try:
                    _call(self._client, 11, _CLIENT_STOP)
                except WasapiError:
                    pass  # the device is gone; the releases below still apply
                _release(self._capture)
                _release(self._client)
                _release(self._dev)

    def _open(dataflow, extra_flags, name):
        if not available():
            raise WasapiError("WASAPI is not available")
        _com_on_thread()
        dev = _resolve(dataflow, name)
        try:
            friendly, _ = _endpoint_info(dev)
            client = _P()
            _check(_call(dev, 3, _ACTIVATE, ctypes.byref(_IID_CLIENT),
                         _CLSCTX_ALL, None, ctypes.byref(client)),
                   "IMMDevice::Activate(IAudioClient)")
            try:
                fmt = _WaveFormatEx(1, 1, RATE, RATE * 2, 2, 16, 0)
                _check(_call(client, 3, _INITIALIZE, _SHARE_SHARED,
                             _AUTOCONVERT | extra_flags, _BUFFER_HNS, None,
                             ctypes.byref(fmt), None),
                       "IAudioClient::Initialize")
                capture = _P()
                _check(_call(client, 14, _GET_SERVICE,
                             ctypes.byref(_IID_CAPCLIENT),
                             ctypes.byref(capture)),
                       "IAudioClient::GetService(IAudioCaptureClient)")
                try:
                    _check(_call(client, 10, _CLIENT_START),
                           "IAudioClient::Start")
                except WasapiError:
                    _release(capture)
                    raise
            except WasapiError:
                _release(client)
                raise
        except WasapiError:
            _release(dev)
            raise
        return _Source(client, capture, dev, friendly or name)

else:
    class _Source:  # pragma: no cover - never constructed off Windows
        def __init__(self, *args):
            raise WasapiError("WASAPI is Windows-only")


def _pick(name, endpoints, default):
    """id of the endpoint to use: empty name means the default one.

    An exact name wins; otherwise matched case-insensitively as a
    substring, because what Settings stored may be an old DirectShow
    spelling of the same physical device. Exact first, so a stored full
    name cannot land on a similarly-named sibling endpoint.
    """
    if not name:
        if not default:
            raise WasapiError("no default audio endpoint")
        return default
    low = name.lower()
    for friendly, dev_id in endpoints:
        if friendly.lower() == low:
            return dev_id
    for friendly, dev_id in endpoints:
        if low in friendly.lower() or friendly.lower() in low:
            return dev_id
    raise WasapiError(f"no audio device matching {name!r}")


_avail_cache = None
_avail_lock = threading.Lock()


def available():
    """Can this process talk to WASAPI at all? Cached per process."""
    global _avail_cache
    if not _WIN:
        return False
    with _avail_lock:
        if _avail_cache is not None:
            return _avail_cache
        try:
            _com_on_thread()
            enum = _enumerator()
            _release(enum)
            _avail_cache = True
        except (WasapiError, OSError, ValueError):
            _avail_cache = False
    return _avail_cache


def reset_cache():
    """Forget the availability answer (used when audio caches invalidate)."""
    global _avail_cache
    with _avail_lock:
        _avail_cache = None


def render_outputs():
    """[(friendly name, id)] of every active output endpoint."""
    if not _WIN:
        return []
    return _endpoints(_RENDER)


def capture_inputs():
    """[(friendly name, id)] of every active capture endpoint."""
    if not _WIN:
        return []
    return _endpoints(_CAPTURE)


def default_render_name():
    """Friendly name of whatever is playing sound right now, or ''."""
    if not _WIN:
        return ""
    try:
        name, _ = _default_endpoint(_RENDER)
        return name
    except WasapiError:
        return ""


def default_capture_name():
    if not _WIN:
        return ""
    try:
        name, _ = _default_endpoint(_CAPTURE)
        return name
    except WasapiError:
        return ""


def open_capture(name=""):
    """The microphone to record, by friendly name or the default one."""
    return _open(_CAPTURE, 0, name)


def open_loopback(name=""):
    """An output endpoint captured as it plays, by name or the default."""
    return _open(_RENDER, _LOOPBACK, name)
