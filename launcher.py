import sys
import os

# Ensure import paths work correctly in the frozen executable
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
    os.chdir(application_path)
else:
    # Add the parent directory to sys.path to allow importing 'steam_xbox_importer' modules
    # if running from inside the folder
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from steam_xbox_importer.main import TUI

if __name__ == "__main__":
    # Enable ANSI colors in Windows CMD
    os.system("") 
    
    app_instance = TUI()
    app_instance.detect_xbox()
    try:
        app_instance.main_menu()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("Critical Error. Press Enter to exit...")
