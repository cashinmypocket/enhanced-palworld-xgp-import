# Steam -> Xbox Save Importer (Palworld)

This tool allows you to transfer your **Palworld** save files from the Steam version to the Xbox (Game Pass) version. It handles the complex conversion to Microsoft's Xbox storage container format automatically.

## 🚀 Features

*   **Smart Detection**: Automatically finds your Xbox save containers.
*   **Safety First**: Checks if the game is running to prevent save corruption.
*   **Automatic Backup**: Creates a full backup of your Xbox saves before making any changes.
*   **Multi-Account Support**: Supports computers with multiple Xbox accounts logged in.
*   **Memory Efficient**: Handles large save files without slowing down your system.

## 📖 How to Use

1.  **Prerequisite**: Ensure you have installed Palworld on Xbox/Game Pass and **launched it at least once** (create a world and save) to generate the necessary file structure.
2.  Run the `SteamXboxImporter.exe` file.
3.  **Select Steam Save**:
    *   Press `1` in the menu.
    *   Locate your Steam save folder (usually `%LOCALAPPDATA%\Pal\Saved\SaveGames\<SteamID>\<InstanceID>`).
    *   **Drag and drop** that folder into the terminal window and press Enter.
4.  **Confirm Target**: The tool shows the detected Xbox save folder. If multiple are found, select the one with the correct date.
5.  **Start Import**: Press `3` to begin.
6.  Once finished, open Palworld on Xbox. Your world should appear in the world selection menu.

## 🔧 Troubleshooting

### "CRITICAL SAFETY WARNING" / Game is running
*   **Problem**: The tool detected that Palworld or Gaming Services are running.
*   **Solution**: Close the game completely. You may need to check Task Manager for `Palworld-Win64-Shipping.exe` or `GamingServices.exe` and end them.

### "No valid save container found"
*   **Problem**: The tool cannot find where Xbox stores the saves.
*   **Solution**: You must run the Xbox version of Palworld at least once and create a dummy save so the folder structure is created on your disk.

### "Level.sav not found" error
*   **Problem**: You selected the wrong folder.
*   **Solution**: Make sure you drag the folder that **contains** the `.sav` files (like `Level.sav`), not the main `SaveGames` folder.

## ⚠️ Disclaimer
Always keep a backup of your original Steam save files. While this tool creates backups of the Xbox target, your source files are your responsibility.
