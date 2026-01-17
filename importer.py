import os
import shutil
import datetime
import uuid
import re
import logging
from typing import List, Optional
from dataclasses import dataclass

from steam_xbox_importer.xbox_fs import ContainerIndex, Container, ContainerFileList, ContainerFile, FileTime

# Set up logging
logger = logging.getLogger("SteamXboxImporter")

@dataclass
class GameDefinition:
    name: str
    package_id: str # e.g. PocketpairInc.Palworld_ad4psfrxyesvt
    wgs_folder: str = "SystemAppData/wgs"
    # Container structure regex to identify valid save containers
    container_regex: str = r"[0-9A-F]{16}_[0-9A-F]{32}$"

class PalworldImporter:
    def __init__(self, dry_run: bool = False):
        self.game = GameDefinition(
            name="Palworld",
            package_id="PocketpairInc.Palworld_ad4psfrxyesvt"
        )
        self.dry_run = dry_run

    def find_xbox_package_path(self) -> str:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise EnvironmentError("LOCALAPPDATA environment variable not found.")
        
        path = os.path.join(local_app_data, "Packages", self.game.package_id)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Package directory not found: {path}. Is the game installed on Xbox App?")
        
        return path

    def find_candidate_containers(self) -> List[str]:
        """Returns a list of all valid save containers found (Multi-User safe)."""
        package_path = self.find_xbox_package_path()
        wgs_path = os.path.join(package_path, *self.game.wgs_folder.split("/"))
        
        if not os.path.exists(wgs_path):
             # Just return empty, caller handles error
             return []

        regex = re.compile(self.game.container_regex)
        candidates = []
        for d in os.listdir(wgs_path):
            if regex.match(d):
                candidates.append(os.path.join(wgs_path, d))
        
        return candidates

    def find_active_container_path(self) -> str:
        """Legacy wrapper: Returns the first found container or raises error."""
        candidates = self.find_candidate_containers()
        if not candidates:
            raise FileNotFoundError("No valid save container found. Please run the game at least once.")
        # Return the most recently modified one ideally, or just the first
        # Let's sort by mtime to be smarter if we have to auto-pick
        candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return candidates[0]

    def import_save(self, steam_save_path: str, target_container_path: Optional[str] = None):
        # 1. Validate Steam Save
        if not os.path.exists(steam_save_path):
            raise FileNotFoundError(f"Steam save path does not exist: {steam_save_path}")
        
        # Adjust if user pointed to a file instead of folder
        if os.path.isfile(steam_save_path):
            steam_save_path = os.path.dirname(steam_save_path)

        save_name = os.path.basename(steam_save_path)
        logger.info(f"Preparing to import Steam save '{save_name}' from: {steam_save_path}")

        # 2. Locate Xbox Container
        # If no target specified, try auto-detect
        if target_container_path is None:
            container_path = self.find_active_container_path()
        else:
            container_path = target_container_path
            
        logger.info(f"Target Xbox container path: {container_path}")

        # 3. Read Container Index
        index_file_path = os.path.join(container_path, "containers.index")
        logger.info(f"Reading index: {index_file_path}")
        
        container_index = ContainerIndex.from_file(index_file_path)
        
        # Check for duplication
        target_container_prefix = f"{save_name}-"
        for c in container_index.containers:
            if c.container_name.startswith(target_container_prefix):
                logger.warning(f"A save with name '{save_name}' might already exist (Found {c.container_name}). Import might conflict.")
                # We optionally could raise error here or just proceed/overwrite

        # 4. Backup
        if not self.dry_run:
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            backup_path = f"{container_path}.backup.{timestamp}"
            logger.info(f"Creating backup at: {backup_path}")
            shutil.copytree(container_path, backup_path)

        # 5. Prepare Files to Import
        # Map Steam files to Container Names
        # Palworld specific:
        # files to copy: Level.sav, LevelMeta.sav, LocalData.sav, WorldOption.sav
        # Players folder content
        
        files_to_process = [
            ("Level.sav", "Level"),
            ("LevelMeta.sav", "LevelMeta"),
            ("LocalData.sav", "LocalData"),
            ("WorldOption.sav", "WorldOption")
        ]
        
        new_containers = []

        # Process main files
        for filename, suffix in files_to_process:
            full_path = os.path.join(steam_save_path, filename)
            if os.path.exists(full_path):
                container_name = f"{save_name}-{suffix}"
                new_c = self._create_container_entry(full_path, container_name, container_path)
                new_containers.append(new_c)
            else:
                logger.warning(f"Optional file not found: {filename}")

        # Process Players
        players_dir = os.path.join(steam_save_path, "Players")
        if os.path.exists(players_dir):
            for player_file in os.listdir(players_dir):
                if player_file.endswith(".sav"):
                    # Format: {SaveName}-Players-{GUID}
                    # steam file: {GUID}.sav
                    # suffix: Players-{GUID}
                    player_id = player_file.replace(".sav", "")
                    container_name = f"{save_name}-Players-{player_id}"
                    full_path = os.path.join(players_dir, player_file)
                    new_c = self._create_container_entry(full_path, container_name, container_path)
                    new_containers.append(new_c)

        # 6. Update Request
        logger.info(f"Adding {len(new_containers)} new containers to index...")
        
        if not self.dry_run:
             # CRITICAL FIX: Remove existing containers with conflicting names to avoid duplication/corruption
             # We filter out any container in the old list that matches the name of a new container
             new_container_names = {c.container_name for c in new_containers}
             
             # Keep only containers that we are NOT updating
             container_index.containers = [
                 c for c in container_index.containers 
                 if c.container_name not in new_container_names
             ]
             
             # Now append the new ones safely
             container_index.containers.extend(new_containers)
             
             # Update modified time
             container_index.mtime = FileTime.from_timestamp(datetime.datetime.now().timestamp())
             
             # Write Index
             container_index.write_file(container_path)
             logger.info("Updated containers.index successfully (Overwrote old entries).")
        else:
            logger.info("[DRY RUN] Would write containers.index now.")

        logger.info("Import completed successfully.")

    def _create_container_entry(self, source_file: str, container_name: str, base_xbox_path: str) -> Container:
        """Creates the physical files for a container and returns the Container metadata object."""
        
        # 2. Create internal file structure
        # Use streaming source_path for memory efficiency (Risk 3 Mitigation)
        content_uuid = uuid.uuid4()
        
        # Pass source_path directly, data=None. The writer will stream it.
        container_file = ContainerFile(name="Data", uuid=content_uuid, data=None, source_path=source_file)
        file_list = ContainerFileList(seq=1, files=[container_file])

        # 3. Create Container Metadata
        container_uuid = uuid.uuid4()
        mtime = FileTime.from_timestamp(os.path.getmtime(source_file))
        size = os.path.getsize(source_file)
        
        containers_dir_path = os.path.join(base_xbox_path, container_uuid.bytes_le.hex().upper())
        
        if not self.dry_run:
            os.makedirs(containers_dir_path, exist_ok=True)
            file_list.write_container(containers_dir_path)
            logger.info(f"Wrote container '{container_name}' to {containers_dir_path}")
        else:
            logger.info(f"[DRY RUN] Would write container '{container_name}' to {containers_dir_path}")

        return Container(
            container_name=container_name,
            cloud_id="",
            seq=1,
            flag=5, # Magic flag from original code
            container_uuid=container_uuid,
            mtime=mtime,
            size=size
        )

