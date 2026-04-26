import subprocess
import os

def run_git_add():
    try:
        # Update gitignore was already done by model
        # Try to add everything that is not ignored
        result = subprocess.run(["git", "add", "."], capture_output=True, text=True)
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        
        result = subprocess.run(["git", "commit", "-m", "Include qwen_free, kimi_free and config files"], capture_output=True, text=True)
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    run_git_add()
