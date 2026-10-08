# Compression license provenance

Windows Python 3.14.4 bundles zlib-ng 2.2.4 and Zstandard 1.5.7 according to its official build inputs:
https://github.com/python/cpython/blob/v3.14.4/PCbuild/get_externals.bat

- zlib DLL 1.3.1, included with Tcl/Tk: https://github.com/madler/zlib/blob/v1.3.1/LICENSE
- zlib-ng 2.2.4: https://github.com/zlib-ng/zlib-ng/blob/2.2.4/LICENSE.md
- Zstandard 1.5.7 (BSD option): https://github.com/facebook/zstd/blob/v1.5.7/LICENSE

These notices supplement the build Python's LICENSE.txt. Runtime libraries are bundled unchanged; no compression source modifications.
