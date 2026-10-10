from setuptools import setup
from Cython.Build import cythonize

setup(
    name="pow_cython",
    ext_modules=cythonize(
        "pow_cython.pyx",
        compiler_directives={
            "boundscheck":      False,
            "wraparound":       False,
            "cdivision":        True,
            "initializedcheck": False,
            "nonecheck":        False,
            "language_level":   3,
        },
    ),
)