"""
Builds the QuickTime metadata boxes an iPhone writes, for tests that need
Apple's tags without real footage. The layout copies original iPhone files
(iOS 26.6.2 and 27.0): make, model, software and Cinematic mode keys in the
movie's 'meta' atom, lens model and 35 mm focal length in the video track's.
"""
import struct

DATA_TYPE = {str: 1, int: 21, bytes: 0}   # UTF-8, signed big-endian int, raw (QuickTime well-known types)


def box(kind: bytes, payload: bytes = b"") -> bytes:
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def meta_box(items: dict) -> bytes:
    """A QuickTime 'meta' atom (hdlr, keys, ilst) holding items {key: str, int or bytes}."""
    hdlr = box(b"hdlr", b"\0" * 8 + b"mdta" + b"\0" * 12 + b"\0")
    keys = box(b"keys", struct.pack(">II", 0, len(items)) + b"".join(
        struct.pack(">I4s", 8 + len(k.encode()), b"mdta") + k.encode() for k in items))
    values = []
    for i, value in enumerate(items.values(), start=1):
        raw = value.encode() if isinstance(value, str) else (
            value.to_bytes(1, "big") if isinstance(value, int) else value)
        data = box(b"data", struct.pack(">II", DATA_TYPE[type(value)], 0) + raw)
        values.append(box(struct.pack(">I", i), data))
    return box(b"meta", hdlr + keys + box(b"ilst", b"".join(values)))


def trak_box(handler: bytes, meta: dict | None = None) -> bytes:
    """A minimal 'trak': mdia/hdlr with the handler type ('vide', 'soun', 'meta'), plus a 'meta' atom."""
    hdlr = box(b"hdlr", b"\0\0\0\0" + b"mhlr" + handler + b"appl" + b"\0" * 12)
    return box(b"trak", box(b"mdia", hdlr) + (meta_box(meta) if meta else b""))


def write_mov(path, movie: dict | None = None, tracks: list[bytes] = ()) -> None:
    """A .MOV of boxes only (no decodable video): ftyp, mdat, then moov with the given traks and movie meta."""
    moov = box(b"moov", b"".join(tracks) + (meta_box(movie) if movie else b""))
    path.write_bytes(box(b"ftyp", b"qt  \0\0\0\0qt  ") + box(b"wide") + box(b"mdat", b"\0" * 16) + moov)


def _children(data: bytes, start: int, end: int):
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        yield kind, pos, pos + size
        pos += size


def add_apple_metadata(path, movie: dict, video: dict) -> None:
    """
    Writes Apple's tags into a real video: `video` into the video track's 'meta'
    atom, `movie` into the movie's. The moov must come after mdat (PyAV's
    default), so growing it moves no sample offsets.
    """
    data = path.read_bytes()
    top = list(_children(data, 0, len(data)))
    kinds = [k for k, _, _ in top]
    assert kinds.index(b"moov") > kinds.index(b"mdat"), "moov before mdat: sample offsets would move"
    _, start, end = top[kinds.index(b"moov")]

    parts = []
    for kind, s, e in _children(data, start + 8, end):
        child = data[s:e]
        if kind == b"trak" and b"hdlr" in child and child[child.index(b"hdlr") + 12:][:4] == b"vide":
            child = box(b"trak", child[8:] + meta_box(video))
        parts.append(child)
    path.write_bytes(data[:start] + box(b"moov", b"".join(parts) + meta_box(movie)) + data[end:])
