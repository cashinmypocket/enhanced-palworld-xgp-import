import os
import uuid
import datetime
from io import BytesIO
from typing import BinaryIO, List, NamedTuple, Optional
from steam_xbox_importer.utils import (
    read_u32, read_utf16_string, read_u64, read_u8, read_utf16_fixed_string,
    write_u32, write_utf16_fixed_string, write_utf16_string, write_u8, write_u64,
    NotSupportedError
)

class FileTime:
    """Represents a Windows FILETIME (100-nanosecond intervals since January 1, 1601)."""
    def __init__(self, value: int):
        self.value = value

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> 'FileTime':
        return cls(read_u64(stream))

    @classmethod
    def from_timestamp(cls, timestamp: float) -> 'FileTime':
        # 116444736000000000 is the offset between Unix epoch (1970) and NTFS epoch (1601) in 100ns units
        return cls(int(timestamp * 10_000_000 + 116444736000000000))

    def to_bytes(self) -> bytes:
        return self.value.to_bytes(8, "little")

    def to_timestamp(self) -> float:
        return (self.value - 116444736000000000) / 10_000_000
    
    def __repr__(self):
        try:
            return f"<FileTime {datetime.datetime.fromtimestamp(self.to_timestamp())}>"
        except (ValueError, OSError):
            return f"<FileTime value={self.value}>"


class Container:
    """Represents a single container entry in the containers.index file."""
    def __init__(self, *, container_name: str, cloud_id: str, seq: int, flag: int, 
                 container_uuid: uuid.UUID, mtime: FileTime, size: int):
        self.container_name = container_name
        self.cloud_id = cloud_id
        self.seq = seq
        self.flag = flag
        self.container_uuid = container_uuid
        self.mtime = mtime
        self.size = size

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> 'Container':
        container_name = read_utf16_string(stream)
        container_name_null_term = read_utf16_string(stream) # In some docs this is repeated name
        
        # Original code check
        if container_name != container_name_null_term:
             # Just a warning or strict check? Original raised error.
             # Ideally we keep strict to be safe.
             raise NotSupportedError(f"Container name mismatch: '{container_name}' != '{container_name_null_term}'")

        cloud_id = read_utf16_string(stream)
        seq = read_u8(stream)
        flag = read_u32(stream)
        
        # Validation checks
        if (cloud_id == "" and flag & 4 == 0) or (cloud_id != "" and flag & 4 != 0):
             raise NotSupportedError("Mismatch between cloud_id existence and flag bit 4")

        container_uuid = uuid.UUID(bytes=stream.read(16))
        mtime = FileTime.from_stream(stream)
        unknown = read_u64(stream)
        if unknown != 0:
            raise NotSupportedError(f"Unexpected non-zero padding data: {unknown}")
            
        size = read_u64(stream)
        
        return cls(
            container_name=container_name,
            cloud_id=cloud_id,
            seq=seq,
            flag=flag,
            container_uuid=container_uuid,
            mtime=mtime,
            size=size
        )

    def to_bytes(self) -> bytes:
        output = BytesIO()
        write_utf16_string(output, self.container_name)
        write_utf16_string(output, self.container_name)
        write_utf16_string(output, self.cloud_id)
        write_u8(output, self.seq)
        write_u32(output, self.flag)
        output.write(self.container_uuid.bytes)
        output.write(self.mtime.to_bytes())
        write_u64(output, 0) # unknown padding
        write_u64(output, self.size)
        return output.getvalue()

    def __repr__(self):
        return f"<Container name='{self.container_name}' uuid={self.container_uuid} size={self.size}>"


class ContainerIndex:
    """Represents the 'containers.index' file."""
    def __init__(self, *, flag1: int, package_name: str, mtime: FileTime, flag2: int, 
                 index_uuid: str, unknown: int, containers: List[Container]):
        self.flag1 = flag1
        self.package_name = package_name
        self.mtime = mtime
        self.flag2 = flag2
        self.index_uuid = index_uuid
        self.unknown = unknown
        self.containers = containers

    @classmethod
    def from_file(cls, path: str) -> 'ContainerIndex':
        with open(path, "rb") as f:
            return cls.from_stream(f)

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> 'ContainerIndex':
        version = read_u32(stream)
        if version != 0xe:
            raise NotSupportedError(f"Unsupported container index version: {version:#x} (expected 0xE)")
            
        file_count = read_u32(stream)
        flag1 = read_u32(stream)
        package_name = read_utf16_string(stream)
        mtime = FileTime.from_stream(stream)
        flag2 = read_u32(stream)
        index_uuid = read_utf16_string(stream)
        unknown = read_u64(stream)
        
        containers = []
        for _ in range(file_count):
            containers.append(Container.from_stream(stream))
            
        return cls(
            flag1=flag1,
            package_name=package_name,
            mtime=mtime,
            flag2=flag2,
            index_uuid=index_uuid,
            unknown=unknown,
            containers=containers
        )

    def write_file(self, path: str):
        target = os.path.join(path, "containers.index")
        with open(target, "wb") as output_file:
            write_u32(output_file, 0xe) # Version
            write_u32(output_file, len(self.containers))
            write_u32(output_file, self.flag1)
            write_utf16_string(output_file, self.package_name)
            output_file.write(self.mtime.to_bytes())
            write_u32(output_file, self.flag2)
            write_utf16_string(output_file, self.index_uuid)
            write_u64(output_file, self.unknown)
            for container in self.containers:
                output_file.write(container.to_bytes())


class ContainerFile:
    """Represents a file *inside* a container. Supports in-memory data or streaming from disk."""
    def __init__(self, name: str, uuid: uuid.UUID, data: Optional[bytes] = None, source_path: Optional[str] = None):
        self.name = name
        self.uuid = uuid
        self.data = data
        self.source_path = source_path

    def get_size(self) -> int:
        if self.data is not None:
            return len(self.data)
        if self.source_path and os.path.exists(self.source_path):
            return os.path.getsize(self.source_path)
        return 0


class ContainerFileList:
    """Represents the 'container.X' file which lists files inside the container."""
    def __init__(self, *, seq: int, files: List[ContainerFile]):
        self.seq = seq
        self.files = files

    @classmethod
    def from_stream(cls, stream: BinaryIO) -> 'ContainerFileList':
        # Infer sequence from filename if possible, otherwise rely on caller?
        # The original used filename.
        try:
            filename = os.path.basename(stream.name)
            ext = os.path.splitext(filename)[1] # .2
            seq = int(ext[1:]) # 2
        except (ValueError, IndexError):
            # Fallback
            seq = 0 

        path = os.path.dirname(stream.name)
        version = read_u32(stream)
        if version != 4:
            raise NotSupportedError(f"Unsupported container file list version: {version}")

        file_count = read_u32(stream)
        files = []
        for _ in range(file_count):
            file_name = read_utf16_fixed_string(stream, 64)
            file_cloud_uuid_bytes = stream.read(16) # Unused?
            file_uuid = uuid.UUID(bytes=stream.read(16))
            
            # The actual file content is in a separate file named by the UUID
            file_content_path = os.path.join(path, file_uuid.bytes_le.hex().upper())
            
            if not os.path.exists(file_content_path):
                # For robust reading, maybe we warn instead of fail?
                # But original fails. Let's fail.
                raise NotSupportedError(f"Container content file missing: {file_content_path}")
                
            with open(file_content_path, "rb") as f:
                file_data = f.read()
                
            files.append(ContainerFile(name=file_name, uuid=file_uuid, data=file_data))
            
        return cls(seq=seq, files=files)

    def write_container(self, path: str):
        """Writes the container.X file and the associated content files (UUID named)."""
        container_file_path = os.path.join(path, f"container.{self.seq}")
        
        with open(container_file_path, "wb") as output_file:
            write_u32(output_file, 4) # Version
            write_u32(output_file, len(self.files))
            
            for file in self.files:
                write_utf16_fixed_string(output_file, file.name, 64)
                output_file.write(b"\0" * 16) # Cloud UUID placeholders?
                output_file.write(file.uuid.bytes)
                
                # Write the actual content file
                content_path = os.path.join(path, file.uuid.bytes_le.hex().upper())
                
                if file.source_path:
                    # Stream from disk (Memory Efficient)
                    with open(file.source_path, "rb") as source, open(content_path, "wb") as dest:
                        import shutil
                        shutil.copyfileobj(source, dest, length=1024*1024) # 1MB chunks
                elif file.data is not None:
                    # Write from memory
                    with open(content_path, "wb") as cf:
                        cf.write(file.data)
                else:
                    # Empty file?
                    with open(content_path, "wb") as cf:
                        pass
