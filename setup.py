import platform
import sys

from distutils.command.build import build

from setuptools import setup
from setuptools.command.install import install

CFFI_MODULES = ["src/buildFFI.py:libutil", "src/buildFFI.py:libstore", "src/buildFFI.py:libexpr"]
SETUP_REQUIRES = ["cffi"]
LIBRARIES = []

setup_requires_error = (
    "Requested setup command that needs 'setup_requires' while command line "
    "arguments implied a side effect free command or option."
)

class DummyBuild(build):
    """
    This class makes it very obvious when ``keywords_with_side_effects()`` has
    incorrectly interpreted the command line arguments to ``setup.py build`` as
    one of the 'side effect free' commands or options.
    """

    def run(self):
        raise RuntimeError(setup_requires_error)

if sys.version_info > (3,) and platform.python_implementation() == "CPython":
    try:
        import wheel.bdist_wheel
    except ImportError:
        BDistWheel = None
    else:

        class BDistWheel(wheel.bdist_wheel.bdist_wheel):
            def finalize_options(self):
                self.py_limited_api = "cp3{}".format(sys.version_info[1])
                wheel.bdist_wheel.bdist_wheel.finalize_options(self)


else:
    BDistWheel = None

class DummyInstall(install):
    """
    This class makes it very obvious when ``keywords_with_side_effects()`` has
    incorrectly interpreted the command line arguments to ``setup.py install``
    as one of the 'side effect free' commands or options.
    """

    def run(self):
        raise RuntimeError(setup_requires_error)


def keywords_with_side_effects(argv):
    """
    Get a dictionary with setup keywords that (can) have side effects.

    :param argv: A list of strings with command line arguments.

    :returns: A dictionary with keyword arguments for the ``setup()`` function.
        This setup.py script uses the setuptools 'setup_requires' feature
        because this is required by the cffi package to compile extension
        modules. The purpose of ``keywords_with_side_effects()`` is to avoid
        triggering the cffi build process as a result of setup.py invocations
        that don't need the cffi module to be built (setup.py serves the dual
        purpose of exposing package metadata).

    Stolen from pyca/cryptography.
    """
    no_setup_requires_arguments = (
        "-h",
        "--help",
        "-n",
        "--dry-run",
        "-q",
        "--quiet",
        "-v",
        "--verbose",
        "-V",
        "--version",
        "--author",
        "--author-email",
        "--classifiers",
        "--contact",
        "--contact-email",
        "--description",
        "--egg-base",
        "--fullname",
        "--help-commands",
        "--keywords",
        "--licence",
        "--license",
        "--long-description",
        "--maintainer",
        "--maintainer-email",
        "--name",
        "--no-user-cfg",
        "--obsoletes",
        "--platforms",
        "--provides",
        "--requires",
        "--url",
        "clean",
        "egg_info",
        "register",
        "sdist",
        "upload",
    )

    def is_short_option(argument):
        """Check whether a command line argument is a short option."""
        return len(argument) >= 2 and argument[0] == "-" and argument[1] != "-"

    def expand_short_options(argument):
        """Expand combined short options into canonical short options."""
        return ("-" + char for char in argument[1:])

    def argument_without_setup_requirements(argv, i):
        """Check whether a command line argument needs setup requirements."""
        if argv[i] in no_setup_requires_arguments:
            # Simple case: An argument which is either an option or a command
            # which doesn't need setup requirements.
            return True
        elif is_short_option(argv[i]) and all(
            option in no_setup_requires_arguments
            for option in expand_short_options(argv[i])
        ):
            # Not so simple case: Combined short options none of which need
            # setup requirements.
            return True
        elif argv[i - 1 : i] == ["--egg-base"]:
            # Tricky case: --egg-info takes an argument which should not make
            # us use setup_requires (defeating the purpose of this code).
            return True
        else:
            return False

    if all(
        argument_without_setup_requirements(argv, i)
        for i in range(1, len(argv))
    ):
        return {"cmdclass": {"build": DummyBuild, "install": DummyInstall}}
    else:
        cmdclass = {}
        if BDistWheel is not None:
            cmdclass["bdist_wheel"] = BDistWheel
        return {
            "setup_requires": SETUP_REQUIRES,
            "cffi_modules": CFFI_MODULES,
            "libraries": LIBRARIES,
            "cmdclass": cmdclass,
        }

if __name__ == "__main__":
    setup(
        packages=["nix"],
        package_dir={"": "src"},
        package_data={"python_nix": ["src/py.typed", "src/*.pyi"]},
        ext_package="",
        **keywords_with_side_effects(sys.argv)
    )
