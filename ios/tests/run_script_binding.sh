#!/bin/bash
set -e
cd "$(dirname "$0")/../.."
mkdir -p ios/build/host-script-binding
sources=(ios/tests/script_binding.cpp external/simplesquirrel/source/*.cpp external/simplesquirrel/libs/squirrel/squirrel/*.cpp external/simplesquirrel/libs/squirrel/sqstdlib/*.cpp)
flags=(-arch i386 -std=c++1y -stdlib=libc++ -O0 -Iexternal/simplesquirrel/include -Iexternal/simplesquirrel/libs/squirrel/include)
clang++ "${flags[@]}" "${sources[@]}" -o ios/build/host-script-binding/before
set +e
ios/build/host-script-binding/before > ios/build/host-script-binding/before.log 2>&1
before=$?
set -e
if [ "$before" -eq 0 ]; then echo 'ERROR: old 32-bit binding unexpectedly passed'; exit 2; fi
echo 'Confirmed: existing 32-bit binding fails the integer-return regression.'
/usr/bin/python - <<'PY'
p = 'external/simplesquirrel/include/simplesquirrel/binding.hpp'
s = open(p).read()
s = s.replace('struct funcBinding<offset, SQInteger, DefaultArgumentsImpl<DefaultArgs...>, Args...> {', 'struct funcBinding<offset, SQInteger, DefaultArgumentsImpl<DefaultArgs...>, HSQUIRRELVM, Args...> {')
s = s.replace('FuncPtr<SQInteger(Args...)>* funcPtr;', 'FuncPtr<SQInteger(HSQUIRRELVM, Args...)>* funcPtr;')
open(p, 'w').write(s)
PY
clang++ "${flags[@]}" "${sources[@]}" -o ios/build/host-script-binding/after
ios/build/host-script-binding/after
