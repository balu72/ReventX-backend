import imp
import os
import sys
import importlib.util

sys.path.insert(0, os.path.dirname(__file__))

# Load run.py dynamically
spec = importlib.util.spec_from_file_location("run", os.path.join(os.path.dirname(__file__), "run.py"))
wsgi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wsgi)

application = wsgi.app
