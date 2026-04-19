import time
import os
import signal
import sys
import subprocess
import logging
import shutil
from pynput import keyboard

# Setup logging
logging.basicConfig(
    filename="daemon.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

class Daemon:
    def __init__(self, pid_file="/tmp/pardus_ai_daemon.pid"):
        self.pid_file = pid_file
        self.running = False
        self.listener = None

    def start(self):
        """Starts the daemon."""
        if os.path.exists(self.pid_file):
            print("Daemon already running.")
            return

        print("Starting Pardus AI Daemon...")
        print("Listening for Global Shortcut: <ctrl>+<alt>+m")
        logging.info("Daemon started. Listening for <ctrl>+<alt>+m")
        
        self.running = True
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

        try:
            self.run_loop()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Stops the daemon."""
        print("Stopping Daemon...")
        logging.info("Daemon stopping...")
        self.running = False
        if self.listener:
            self.listener.stop()
        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)
        sys.exit(0)

    def on_activate(self):
        """Triggered when the shortcut is pressed."""
        print("Shortcut triggered! Launching assistant...")
        logging.info("Shortcut triggered <ctrl>+<alt>+m")
        
        try:
            cwd = os.getcwd()
            python_executable = os.path.abspath("./venv/bin/python3")
            script_path = os.path.abspath("main.py")
            cmd_args = f"{python_executable} {script_path} --chat"
            
            # Detect available terminal
            terminal = self.detect_terminal()
            if not terminal:
                logging.error("No suitable terminal emulator found.")
                return

            logging.info(f"Launching in {terminal} with: {cmd_args}")
            
            if "gnome-terminal" in terminal:
                command = ["gnome-terminal", "--", "bash", "-c", f"{cmd_args}; exec bash"]
            elif "xfce4-terminal" in terminal:
                command = ["xfce4-terminal", "--execute", "bash", "-c", f"{cmd_args}; exec bash"]
            elif "x-terminal-emulator" in terminal:
                command = ["x-terminal-emulator", "-e", f"bash -c '{cmd_args}; exec bash'"]
            else:
                # Fallback for others (xterm etc.)
                command = [terminal, "-e", f"bash -c '{cmd_args}; exec bash'"]
            
            subprocess.Popen(command, cwd=cwd)
            logging.info("Subprocess launched successfully.")
            
        except Exception as e:
            msg = f"Error launching terminal: {e}"
            print(msg)
            logging.error(msg)

    def detect_terminal(self):
        """Checks for common terminal emulators."""
        terminals = ["gnome-terminal", "xfce4-terminal", "x-terminal-emulator", "konsole", "xterm", "terminator"]
        for term in terminals:
            if shutil.which(term):
                return term
        return None

    def run_loop(self):
        """Main loop with keyboard listener."""
        logging.info("Starting listener...")
        try:
            # Non-blocking listener using join()
            with keyboard.GlobalHotKeys({
                '<ctrl>+<alt>+m': self.on_activate
            }) as h:
                self.listener = h
                logging.info("Listener active. Waiting for input...")
                h.join()
        except Exception as e:
            logging.error(f"Listener failed: {e}")
            print(f"Listener failed: {e}")

if __name__ == "__main__":
    daemon = Daemon()
    daemon.start()
