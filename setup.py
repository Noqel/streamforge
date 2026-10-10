# setup.py
import os

# Wichtig: st_zig patcht setuptools, damit es den Zig-Compiler verwendet
from st_zig import enforce_via_build_ext
enforce_via_build_ext()

from setuptools import setup
from Cython.Build import cythonize

setup(
    name="pow_cython",
    ext_modules=cythonize(
        "src/pow/pow_cython.pyx",  # Pfad ggf. anpassen
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
            "cdivision": True,
            "initializedcheck": False,
            "nonecheck": False,
        },
    ),
)