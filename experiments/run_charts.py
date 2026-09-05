"""Windows-safe entry point for the Matplotlib experiment charts."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from generate_charts import main

if __name__ == "__main__":
    main()
