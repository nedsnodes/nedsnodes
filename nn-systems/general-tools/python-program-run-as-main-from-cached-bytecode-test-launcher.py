#!/usr/bin/env python3
"""Run a Python program as `python3 <program> <arguments>` would, but load it through the import system,
so its compiled bytecode is cached in its __pycache__ and reused by every later run.

usage: python3 python-program-run-as-main-from-cached-bytecode-test-launcher.py <program> [arguments...]

Python never caches the bytecode of the script it is given, so a suite that starts a program of several
thousand lines hundreds of times compiles it each time. A suite starts its program through this launcher
instead, to pay that compile once. The program runs as __main__ with the sys.argv, __file__, sys.path[0]
and __spec__ a direct run gives it, and its exit status and signals pass through as from a direct run; an
uncaught exception's traceback holds one more frame, this launcher's, above the program's own. Only the program's own top-level file is affected: the modules it loads are cached as
they always are.
"""
import importlib.machinery
import os
import sys
import types

if len(sys.argv) < 2:
    sys.stderr.write("python-program-run-as-main-from-cached-bytecode-test-launcher.py ran nothing: it was given "
                     "no program.\nGive the program's path first, then the program's own arguments: python3 "
                     "python-program-run-as-main-from-cached-bytecode-test-launcher.py <program> [arguments...]\n")
    sys.exit(2)
program = os.path.abspath(sys.argv[1])
sys.argv = sys.argv[1:]
# A direct run puts the directory of the script, with its symbolic links resolved, first on sys.path.
sys.path[0] = os.path.dirname(os.path.realpath(program))
loader = importlib.machinery.SourceFileLoader("__main__", program)
module = types.ModuleType("__main__")
# As for a script run by path: no __spec__, which argparse reads to name the program in its usage line.
module.__spec__ = None
module.__file__ = program
module.__loader__ = loader
module.__builtins__ = __builtins__
sys.modules["__main__"] = module
code = loader.get_code("__main__")
del importlib, types, loader
exec(code, module.__dict__)
