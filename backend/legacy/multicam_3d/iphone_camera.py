# file only used for iPhone cameras, triggered by main.py run with --camera iphone
# other cameras use --fov guess in calibrate_person.py instead
#
# grabs lens data from iPhone videos (.MOV)'s metadata! 
# so camera matrix is computed instead of guessed from fov
# additionally, uses recorded variable frame rate to match videos bt frame

import struct
import sys

import numpy as np

# grabbed from iPhone video's metadata
FOCAL_35MM_KEY = "com.apple.quicktime.camera.focal_length.35mm_equivalent"
MODEL_KEY = "com.apple.quicktime.model"
LENS_KEY = "com.apple.quicktime.camera.lens_model"

# diagonal of a 35mm film frame (36 x 24 mm)
FULL_FRAME_DIAGONAL_MM = 43.27

class IPhoneMetadataError(Exception):
    pass

# function to walk the atoms of a QuickTime file
#   using type, payload start, and payload end
def _atoms(data, start, end):
    pos = start

    while pos + 8 <= end:
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        header = 8

        if size == 1:  # 64-bit size
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            header = 16
        elif size == 0:  # runs to the end of the file
            size = end - pos
        if size < header:
            break

        yield kind.decode("latin-1"), pos + header, pos + size
        pos += size

def _find(data, start, end, kind):
    for k, s, e in _atoms(data, start, end):
        if k == kind:
            return s, e
        
    return None

def _read_moov(path):
    # only the moov atom is needed, skip over the (large) video data without loading it
    with open(path, "rb") as fp:
        while True:
            header = fp.read(8)
            if len(header) < 8:
                raise IPhoneMetadataError(f"{path} has no QuickTime metadata (not a .MOV/.MP4?)")
            size, kind = struct.unpack(">I4s", header)
            header_len = 8
            if size == 1:
                size = struct.unpack(">Q", fp.read(8))[0]
                header_len = 16
            if kind == b"moov":
                return fp.read(size - header_len)
            if size == 0:
                raise IPhoneMetadataError(f"{path} has no QuickTime metadata (not a .MOV/.MP4?)")
            fp.seek(size - header_len, 1)

# read the metadata of an iPhone video into a dict
def read_metadata(path):
    moov = _read_moov(path)
    found = _find(moov, 0, len(moov), "meta")

    if found is None:
        return {}
    
    meta_start, meta_end = found

    keys_atom = _find(moov, meta_start, meta_end, "keys")
    ilst_atom = _find(moov, meta_start, meta_end, "ilst")

    if keys_atom is None or ilst_atom is None:
        return {}

    # keys: version/flags (4), count (4), then [size (4), namespace (4), name]
    s, e = keys_atom
    count = struct.unpack(">I", moov[s + 4:s + 8])[0]
    names = []
    pos = s + 8

    for _ in range(count):
        size = struct.unpack(">I", moov[pos:pos + 4])[0]
        names.append(moov[pos + 8:pos + size].decode("utf-8", "replace"))
        pos += size

    # ilst: one atom per value, its type is the 1-based key index, holding a "data" atom
    metadata = {}

    for kind, s, e in _atoms(moov, *ilst_atom):
        index = struct.unpack(">I", kind.encode("latin-1"))[0]
        data_atom = _find(moov, s, e, "data")
        if data_atom is None or not 1 <= index <= len(names):
            continue
        ds, de = data_atom
        type_code = struct.unpack(">I", moov[ds:ds + 4])[0] & 0xFFFFFF
        value = moov[ds + 8:de]
        if type_code == 1:  # UTF-8 text
            value = value.decode("utf-8", "replace")
        elif type_code in (21, 22) and len(value) in (1, 2, 4, 8):  # signed/unsigned int
            value = int.from_bytes(value, "big", signed=(type_code == 21))
        elif type_code == 23 and len(value) == 4:  # float32
            value = struct.unpack(">f", value)[0]
        elif type_code == 24 and len(value) == 8:  # float64
            value = struct.unpack(">d", value)[0]
        metadata[names[index - 1]] = value

    return metadata

# function to create camera matrix!
#   uses diagonal so it works for portrait and landscape videos
def intrinsics_from_focal(size, focal_35mm):
    width, height = size
    f = float(focal_35mm) * np.hypot(width, height) / FULL_FRAME_DIAGONAL_MM

    return np.array([[f, 0, width / 2.0],
                     [0, f, height / 2.0],
                     [0, 0, 1.0]])

# boolean function that returns true if video is from iPhone
def is_iphone_video(path):
    try:
        return bool(read_metadata(path).get(FOCAL_35MM_KEY))
    except (IPhoneMetadataError, OSError, struct.error):
        return False

# function to create camera matrix for one video
def iphone_intrinsics(path, size):
    metadata = read_metadata(path)
    focal = metadata.get(FOCAL_35MM_KEY)

    if not focal:
        raise IPhoneMetadataError(
            f"{path} has no focal length metadata (is it straight from an iPhone, not re-exported?)")
    
    return intrinsics_from_focal(size, focal), metadata


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python iphone_camera.py VIDEO [VIDEO ...]")
    
    for video in sys.argv[1:]:
        try:
            md = read_metadata(video)
        except (IPhoneMetadataError, OSError) as e:
            print(f"{video}: {e}")
            continue
        print(f"{video}: model={md.get(MODEL_KEY)}, lens={md.get(LENS_KEY)}, "
              f"focal_35mm={md.get(FOCAL_35MM_KEY)}")
