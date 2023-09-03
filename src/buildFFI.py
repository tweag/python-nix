from cffi import FFI
from pathlib import Path
import pkgconfig

ffi = FFI()

def extract_cffi(fname):
    with open(fname) as f:
        contents = f.read()
        return contents[contents.index("// cffi start"):contents.index("// cffi end")]

parsed = pkgconfig.parse("nix-expr-c nix-store-c")
nix_headers = Path(parsed["include_dirs"][0])
    
def make_ffi(name, headers, libraries, includes=[], extra_header=""):
    header_content = "\n".join([extract_cffi(nix_headers / p) for p in headers])
    if extra_header:
        header_content += "\n" + extra_header

    ffi = FFI()

    for include in includes:
        ffi.include(include)

    # Define C declarations
    ffi.cdef(header_content)

    # Set the C source file
    ffi.set_source(name, '''
    #include "nix_api_util.h"
    #include "nix_api_store.h"
    #include "nix_api_expr.h"
    #include "nix_api_value.h"
    #include "nix_api_external.h"
    ''',
                   libraries=parsed["libraries"],
                   library_dirs=parsed["library_dirs"],
                   include_dirs=parsed["include_dirs"])
    return ffi

libutil = make_ffi("nix._nix_api_util", ["nix_api_util.h"], ["nixutilc"])
libstore = make_ffi("nix._nix_api_store", ["nix_api_store.h"], ["nixstorec"], [libutil])
libexpr = make_ffi("nix._nix_api_expr", ["nix_api_expr.h", "nix_api_value.h", "nix_api_external.h"], ["nixexprc"], [libutil, libstore], """
extern "Python" void py_nix_primop_base(void*, struct nix_c_context*, struct State*, void**, void*);
extern "Python" void py_nix_finalizer(void*, void*);
extern "Python" void py_nix_external_print(void*, nix_printer*);
extern "Python" void py_nix_external_toString(void*, nix_string_return*);
extern "Python" void py_nix_external_showType(void*, nix_string_return*);
extern "Python" void py_nix_external_typeOf(void*, nix_string_return*);
extern "Python" void py_nix_external_coerceToString(void*, nix_string_context*, int, int, nix_string_return*);
extern "Python" int py_nix_external_equal(void*, void*);
""")


# Compile the CFFI extension
if __name__ == '__main__':
    libutil.compile(verbose=True)
    libstore.compile(verbose=True)
    libexpr.compile(verbose=True)
