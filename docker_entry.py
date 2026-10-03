"""Docker entry point: `--full` runs the full experiment, anything else is passed to reproduce.py."""
import subprocess
import sys

args = [a for a in sys.argv[1:] if a != "--full"]
if "--full" in sys.argv[1:]:
    args = [a for a in args if a != "--quick"]
sys.exit(subprocess.call([sys.executable, "reproduce.py", *args]))
