from setuptools import setup

setup(
    setup_requires=["cffi>=1.0.0"],
    cffi_modules=["buildFFI.py:libutil", "buildFFI.py:libstore", "buildFFI.py:libexpr"],
    install_requires=["cffi>=1.0.0"]
    )
