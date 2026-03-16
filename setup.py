from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext


class OptionalBuildExt(build_ext):
    def build_extension(self, ext):
        try:
            super().build_extension(ext)
        except Exception:
            print("Note: optional native code accelerator for Mutant Fish not built (no build tools available); "
                  "pure Python fallback will be used.")
            ext._optional_build_failed = True

    def copy_extensions_to_source(self):
        self.extensions = [e for e in self.extensions
                           if not getattr(e, "_optional_build_failed", False)]
        super().copy_extensions_to_source()


setup(
    ext_modules=[
        Extension(
            "hodoku.solver._fish_accel",
            sources=["src/hodoku/solver/_fish_accel.c"],
            extra_link_args=["-static-libgcc"],
        ),
        Extension(
            "hodoku.generator._gen_accel",
            sources=["src/hodoku/generator/_gen_accel.c"],
            extra_link_args=["-static-libgcc"],
        ),
    ],
    cmdclass={"build_ext": OptionalBuildExt},
)
