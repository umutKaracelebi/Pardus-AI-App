import subprocess
import json
import os

def run_gsettings(args):
    """Runs a gsettings command and returns the output."""
    cmd = ["gsettings"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"gsettings command failed: {result.stderr}")
    return result.stdout.strip()

def setup_shortcut():
    SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
    KEY = "custom-keybindings"
    
    # 1. Get current custom keybindings
    current_bindings_str = run_gsettings(["get", SCHEMA, KEY])
    
    # Parse the GVariant format string (e.g., "['/path/to/custom0/']")
    # It looks like a python list representation, so we can try to parse it safely
    # If empty, it might be "@as []"
    if current_bindings_str == "@as []" or current_bindings_str == "[]":
        current_bindings = []
    else:
        # Remove @as if present
        if current_bindings_str.startswith("@as"):
            current_bindings_str = current_bindings_str[3:].strip()
        # Simple parsing logic or eval (safe-ish here as it comes from gsettings)
        try:
            current_bindings = eval(current_bindings_str)
        except:
            print(f"Error parsing current bindings: {current_bindings_str}")
            return

    # 2. Determine new path
    # Find a unique index
    index = 0
    while True:
        new_path = f"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom{index}/"
        if new_path not in current_bindings:
            break
        index += 1
    
    print(f"Adding new shortcut at: {new_path}")
    
    # 3. Set the new binding details
    # The path provided in the array explains WHERE the settings are stored.
    # We need to set the attributes for that path.
    # Note: custom-keybindings stores relocatable schemas.
    
    shortcut_name = "Pardus AI Assistant"
    shortcut_cmd = os.path.abspath("launch_assistant.sh")
    shortcut_binding = "<Control><Alt>m"
    
    subprocess.run(["gsettings", "set", f"{SCHEMA}.custom-keybinding:{new_path}", "name", shortcut_name], check=True)
    subprocess.run(["gsettings", "set", f"{SCHEMA}.custom-keybinding:{new_path}", "command", shortcut_cmd], check=True)
    subprocess.run(["gsettings", "set", f"{SCHEMA}.custom-keybinding:{new_path}", "binding", shortcut_binding], check=True)
    
    # 4. Append to the list
    current_bindings.append(new_path)
    
    # Convert back to string representation for gsettings
    new_bindings_str = str(current_bindings).replace("'", "\"") # gsettings expects double quotes usually or works with single
    # Actually gsettings set expects "['path1', 'path2']"
    
    subprocess.run(["gsettings", "set", SCHEMA, KEY, new_bindings_str], check=True)
    
    print(f"Successfully added shortcut: {shortcut_binding} -> {shortcut_cmd}")

if __name__ == "__main__":
    try:
        setup_shortcut()
    except Exception as e:
        print(f"Error setting up shortcut: {e}")
