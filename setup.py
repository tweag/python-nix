from setuptools import setup

setup(
    setup_requires=["cffi>=1.0.0"],
    cffi_modules=["src/buildFFI.py:libutil", "src/buildFFI.py:libstore", "src/buildFFI.py:libexpr"],
    install_requires=["cffi>=1.0.0"],
    package_data={"python_nix": ["src/py.typed", "src/*.pyi"]},
    )
