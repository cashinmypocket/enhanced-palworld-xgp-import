import os
import sys
import time
import logging
import datetime
from typing import Optional
from steam_xbox_importer.importer import PalworldImporter

# API Imports for logic
# We will use the importer class but handle the UI interaction here.

# ANSI Colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def print(text, color=ENDC, end="\n"):
        if os.name == 'nt':
            # Enable VT100 emulation for Windows 10/11 if needed, 
            # though often works in modern terminals. 
            pass 
        print(f"{color}{text}{Colors.ENDC}", end=end)

# --- ULTRATHINK SECURITY MODULE ---
import subprocess

def check_conflicting_processes() -> list:
    """Checks if known risky processes are running using native tasklist command."""
    # List of process names to check (exact match or partial)
    risky_apps = ["Palworld-Win64-Shipping.exe", "Palworld.exe", "Gamingservices.exe"]
    found = []
    
    try:
        # Run tasklist /FO CSV to get parsed output easier, or just simple text search
        # We use strict filtering
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True)
        output = result.stdout.lower()
        
        for app in risky_apps:
            if app.lower() in output:
                found.append(app)
    except Exception as e:
        # Fallback if tasklist fails for some reason
        pass
        
    return found
# ----------------------------------

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    clear_screen()
    banner = r"""
  ____       _                    _     _   __  __ ____  
 |  _ \ __ _| |_      _____  _ __| | __| |  \ \/ // ___| 
 | |_) / _` | \ \ /\ / / _ \| '__| |/ _` |   \  /| |  _  
 |  __/ (_| | |\ V  V / (_) | |  | | (_| |   /  \| |_| | 
 |_|   \__,_|_| \_/\_/ \___/|_|  |_|\__,_|  /_/\_\\____| 
                                                         
      Steam -> Xbox Save Importer (TUI Version)
    """
    Colors.print(banner, Colors.CYAN)
    print("=" * 60)

def pause():
    print()
    input(f"{Colors.BOLD}Press Enter to continue...{Colors.ENDC}")

class TUI:
    def __init__(self):
        self.importer = PalworldImporter(dry_run=False)
        self.steam_path: Optional[str] = None
        self.xbox_path: Optional[str] = None
        self.status_msg = ""
        self.status_color = Colors.ENDC

    def detect_xbox(self):
        try:
            candidates = self.importer.find_candidate_containers()
            if not candidates:
                 self.status_msg = "Xbox Save Error: No containers found."
                 self.status_color = Colors.FAIL
                 return False
            
            if len(candidates) == 1:
                self.xbox_path = candidates[0]
                self.status_msg = "Xbox container detected."
                self.status_color = Colors.GREEN
            else:
                # Ambiguity - Multi-User Risk
                self.handle_multi_user_selection(candidates)
                
            return True
        except Exception as e:
            self.status_msg = f"Xbox Save Error: {e}"
            self.status_color = Colors.FAIL
            return False

    def handle_multi_user_selection(self, candidates):
        print("\n" * 2)
        Colors.print("!!! MULTIPLE XBOX SAVE CONTAINERS DETECTED !!!", Colors.WARNING)
        print("This usually happens if multiple Xbox accounts have signed in.")
        print("Please select the correct one (check modified dates):")
        
        for idx, path in enumerate(candidates):
            mtime = os.path.getmtime(path)
            dt = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            folder_name = os.path.basename(path)
            print(f" [{idx+1}] {folder_name} (Last Modified: {dt})")
            
        print()
        while True:
            choice = input(f"{Colors.BOLD}Select Container [1-{len(candidates)}]: {Colors.ENDC}").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(candidates):
                    self.xbox_path = candidates[idx]
                    self.status_msg = f"Selected container: {os.path.basename(self.xbox_path)}"
                    self.status_color = Colors.GREEN
                    return
            print("Invalid selection. Try again.")

    def validate_steam_path(self, path: str) -> bool:
        path = path.strip('"').strip("'")
        if not os.path.exists(path):
            self.status_msg = "Path does not exist!"
            self.status_color = Colors.FAIL
            return False
        
        if os.path.isfile(path):
            path = os.path.dirname(path)
        
        # Check for Level.sav as a sanity check for Palworld
        if not os.path.exists(os.path.join(path, "Level.sav")):
            self.status_msg = "Warning: Level.sav not found. Is this a Palworld save folder?"
            self.status_color = Colors.WARNING
            # We warn but allow, in case file name differs or structure changed
        else:
            self.status_msg = "Valid Palworld save detected."
            self.status_color = Colors.GREEN
        
        self.steam_path = path
        return True

    def main_menu(self):
        while True:
            print_banner()
            
            # Status Section
            print(f" {Colors.BOLD}STATUS:{Colors.ENDC}")
            
            # 1. Xbox Status
            if self.xbox_path:
                Colors.print(f" [Xbox] Target Container: Found", Colors.GREEN)
                # Shorten path for display
                display_path = self.xbox_path if len(self.xbox_path) < 50 else "..." + self.xbox_path[-47:]
                print(f"        Path: {display_path}")
            else:
                Colors.print(f" [Xbox] Target Container: NOT FOUND", Colors.FAIL)
            
            # 2. Steam Status
            if self.steam_path:
                Colors.print(f" [Steam] Source Folder: Selected", Colors.GREEN)
                display_path = self.steam_path if len(self.steam_path) < 50 else "..." + self.steam_path[-47:]
                print(f"        Path: {display_path}")
            else:
                Colors.print(f" [Steam] Source Folder: NOT SELECTED", Colors.WARNING)

            # 3. Dry Run Status
            dry_mode = "ON (Safe Mode)" if self.importer.dry_run else "OFF (Write Mode)"
            dry_color = Colors.CYAN if self.importer.dry_run else Colors.WARNING
            Colors.print(f" [Mode] Dry Run: {dry_mode}", dry_color)

            print("-" * 60)
            if self.status_msg:
                Colors.print(f"Message: {self.status_msg}", self.status_color)
                self.status_msg = "" # consume message
                print("-" * 60)

            # Options
            print(f" {Colors.BOLD}ACTIONS:{Colors.ENDC}")
            print(" [1] Select Steam Save Folder (Drag & Drop)")
            print(" [2] Toggle Dry Run Mode")
            print(" [3] START IMPORT")
            print(" [4] Refresh Xbox Detection")
            print(" [Q] Quit")
            print()
            
            choice = input(f" {Colors.BLUE}>> Make a selection:{Colors.ENDC} ").strip().lower()

            if choice == '1':
                self.input_steam_path()
            elif choice == '2':
                self.importer.dry_run = not self.importer.dry_run
                self.status_msg = "Dry run mode toggled."
                self.status_color = Colors.CYAN
            elif choice == '3':
                if self.run_import():
                    pause()
            elif choice == '4':
                self.detect_xbox()
            elif choice == 'q':
                print("Goodbye!")
                sys.exit(0)
            else:
                self.status_msg = "Invalid selection."
                self.status_color = Colors.FAIL

    def input_steam_path(self):
        print()
        print(f"{Colors.BOLD}Paste the full path to your Steam save folder (or drag the folder here):{Colors.ENDC}")
        path = input(">>Path: ").strip()
        if path:
            self.validate_steam_path(path)

    def run_import(self) -> bool:
        if not self.steam_path:
            self.status_msg = "Please select a Steam save folder first."
            self.status_color = Colors.FAIL
            return False
        if not self.xbox_path:
            self.status_msg = "Cannot import: Xbox container not found."
            self.status_color = Colors.FAIL
            return False

        # 0. Safety Check (Risk 1 Mitigation)
        conflicts = check_conflicting_processes()
        if conflicts:
            clear_screen()
            Colors.print("!!! CRITICAL SAFETY WARNING !!!", Colors.FAIL)
            print("The following conflicting processes are running:")
            for c in conflicts:
                print(f" - {c}")
            print()
            Colors.print("Running the import while the game is open WILL corrupt your save.", Colors.BOLD)
            print("Please close them completely and try again.")
            self.status_msg = "Aborted due to running game processes."
            self.status_color = Colors.FAIL
            return False

        print()
        Colors.print("!!! STARTING IMPORT PROCESS !!!", Colors.BOLD)
        print("See logs below for details...")
        print("-" * 60)
        
        # Capture logging to stdout for TUI visibility
        root_logger = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        # Prevent double logging if multiple handlers exist
        root_logger.setLevel(logging.INFO)

        try:
            self.importer.import_save(self.steam_path, target_container_path=self.xbox_path)
            Colors.print("\n[SUCCESS] Import finished successfully!", Colors.GREEN)
        except Exception as e:
            Colors.print(f"\n[ERROR] Import failed: {e}", Colors.FAIL)
            import traceback
            traceback.print_exc()
        
        # Cleanup handler
        root_logger.removeHandler(handler)
        print("-" * 60)
        return True

if __name__ == "__main__":
    # Windows ANSI support setup
    os.system("") 
    
    app = TUI()
    app.detect_xbox()
    try:
        app.main_menu()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
