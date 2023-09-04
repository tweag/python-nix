// gcc ./examples/plugin.c $(pkg-config nix-expr-c --libs --cflags) $(python3.10-config --cflags --embed --ldflags) -shared -o plugin.so
// PYTHONPATH=$PWD/examples:$PWD/result/lib/python3.10/site-packages:$PYTHONPATH nix --plugin-files ./plugin.so repl

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <dlfcn.h>

void nix_plugin_entry() {
  /* linker hack: nix loads plugins as RTLD_LOCAL
   * but, we need libpython3.10.so.1.0 to be linked in globally
   * so that extension loading works */
  void *handle = dlopen("libpython3.10.so.1.0", RTLD_NOW | RTLD_GLOBAL);
  if (!handle) {
    fprintf(stderr, "could not open plugin.so, %s", dlerror());
    exit(1);
  }
  //Py_SetProgramName(program);
  Py_Initialize();
  PyRun_SimpleString("import plugin_entry");
}
