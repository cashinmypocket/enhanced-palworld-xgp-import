import struct
from typing import BinaryIO

class NotSupportedError(Exception):
    """Raised when an unsupported file format or feature is encountered."""
    pass

def read_u8(stream: BinaryIO) -> int:
    """Reads a 1-byte unsigned integer."""
    data = stream.read(1)
    if not data:
        return 0
    return int.from_bytes(data, "little")

def read_u32(stream: BinaryIO) -> int:
    """Reads a 4-byte unsigned integer."""
    data = stream.read(4)
    if not data:
        return 0
    return int.from_bytes(data, "little")

def read_u64(stream: BinaryIO) -> int:
    """Reads a 8-byte unsigned integer."""
    data = stream.read(8)
    if not data:
        return 0
    return int.from_bytes(data, "little")

def read_utf16_string(stream: BinaryIO) -> str:
    """Reads a size-prefixed UTF-16 LE string."""
    length = read_u32(stream)
    if length == 0:
        return ""
    # length is number of characters, so bytes is length * 2
    return stream.read(length * 2).decode("utf-16-le")

def read_utf16_fixed_string(stream: BinaryIO, length: int) -> str:
    """Reads a fixed-length UTF-16 LE string."""
    # length is expected character count, bytes is length * 2
    raw = stream.read(length * 2)
    return raw.decode("utf-16-le").rstrip("\0")

def write_u8(stream: BinaryIO, value: int) -> None:
    """Writes a 1-byte unsigned integer."""
    stream.write(value.to_bytes(1, "little"))

def write_u32(stream: BinaryIO, value: int) -> None:
    """Writes a 4-byte unsigned integer."""
    stream.write(value.to_bytes(4, "little"))

def write_u64(stream: BinaryIO, value: int) -> None:
    """Writes a 8-byte unsigned integer."""
    stream.write(value.to_bytes(8, "little"))

def write_utf16_string(stream: BinaryIO, value: str) -> None:
    """Writes a size-prefixed UTF-16 LE string."""
    # Length of string in characters
    write_u32(stream, len(value))
    stream.write(value.encode("utf-16-le"))

def write_utf16_fixed_string(stream: BinaryIO, value: str, length: int) -> None:
    """Writes a fixed-length UTF-16 LE string, padded with nulls."""
    encoded = value.encode("utf-16-le")
    stream.write(encoded)
    # Pad with null bytes (2 bytes per char)
    padding_chars = length - len(value)
    if padding_chars > 0:
        stream.write(b"\0" * (padding_chars * 2))
