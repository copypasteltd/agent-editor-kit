"""Build the native open-source-only CPU translation executable, without VMs.

Requires the explicitly acquired publisher-hash-verified native toolchains and
the matching checked-out CTranslate2 submodules. Does not download anything.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'product/.runtime/materials-20261024'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(WORK) or output.exists():
        raise ValueError('Select a new owned native-build output')
    source = WORK / 'ctranslate2-src-r1'
    tools = WORK / 'toolchains'
    compiler = next((tools / 'llvm-mingw').glob('*/bin/x86_64-w64-mingw32-clang.exe'))
    cmake = next((tools / 'cmake').rglob('bin/cmake.exe'))
    ninja = next((tools / 'ninja').rglob('ninja.exe'))
    output.mkdir()
    environment = {**os.environ, 'PATH': str(compiler.parent) + os.pathsep + os.environ['PATH']}
    commands = [
        [str(cmake), '-S', str(source), '-B', str(output / 'build'), '-G', 'Ninja',
         '-DCMAKE_MAKE_PROGRAM=' + ninja.as_posix(), '-DCMAKE_C_COMPILER=' + compiler.as_posix(),
         '-DCMAKE_CXX_COMPILER=' + compiler.with_name('x86_64-w64-mingw32-clang++.exe').as_posix(),
         '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
         '-DWITH_MKL=OFF', '-DWITH_DNNL=OFF', '-DWITH_CUDA=OFF', '-DWITH_CUDNN=OFF',
         '-DWITH_RUY=ON', '-DOPENMP_RUNTIME=NONE', '-DBUILD_TESTS=OFF',
         '-DBUILD_SHARED_LIBS=OFF', '-DBUILD_CLI=ON', '-DCMAKE_EXE_LINKER_FLAGS=-static'],
        [str(cmake), '--build', str(output / 'build'), '--parallel', '4'],
    ]
    for index, argv in enumerate(commands):
        with (output / (str(index) + '.log')).open('wb') as log:
            completed = subprocess.run(argv, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                       timeout=1200, creationflags=subprocess.CREATE_NO_WINDOW)
        if completed.returncode:
            raise RuntimeError((output / (str(index) + '.log')).read_text('utf8', errors='replace')[-6000:])
    binary = output / 'build/cli/ct2-translator.exe'
    with binary.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    report = dict(status='built-not-inference-accepted', upstream_commit='8d91aa08225004755360daa43deb62b35b1ed65d',
                  commands=commands, binary=str(binary), sha256=digest, bytes=binary.stat().st_size,
                  backend='Ruy', mkl=False, intel_openmp=False, cuda=False, cudnn=False,
                  network=False, virtual_environment=False)
    (output / 'build.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
