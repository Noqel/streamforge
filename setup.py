from setuptools import setup
from Cython.Build import cythonize

setup(
    name="pow_cython",
    build_zig=True,
    ext_modules=cythonize(
        "src/streamforge/pow/pow_cython.pyx",
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