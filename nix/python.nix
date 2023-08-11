{ wasmtime, python-wasi, writeShellScriptBin }:

writeShellScriptBin "python-wasi" ''
   ${wasmtime}/bin/wasmtime run ${python-wasi}/python.wasm \
     --env PYTHONHOME=${python-wasi} \
     --env PYTHONPATH="./:./.wasm-deps" \
     --dir ${python-wasi} \
     --dir . \
     -- "$@"
''
