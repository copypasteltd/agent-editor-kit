"""Build a new immutable, CPU-only optional model pack from verified inputs."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'product/.runtime/materials-20261024'
DOWNLOADS = WORK / 'downloads'
NOTICES = ROOT / 'sources/materials-20261024/notices'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['voice', 'translation'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--zh-en', type=Path, default=WORK / 'translation-zh-en-r1')
    parser.add_argument('--en-zh', type=Path, default=WORK / 'translation-en-zh-r1')
    parser.add_argument('--native', type=Path, default=WORK / 'ct2-native-build-r1')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError('Model pack must stay inside this E: project')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'site').mkdir()
    (output / 'bin').mkdir()
    wheels = (['sherpa-onnx', 'sherpa-onnx-core'] if args.kind == 'voice'
              else ['sentencepiece', 'pyyaml', 'opencc-python-reimplemented'])
    origins, omitted = [], []
    for name in wheels:
        metadata = json.loads((ROOT / 'sources/materials-20261024/research' / (name + '.json')).read_bytes())
        row = next(f for f in metadata['urls'] if f['filename'].endswith('cp313-cp313-win_amd64.whl')
                   or (name == 'sherpa-onnx-core' and f['filename'].endswith('py3-none-win_amd64.whl'))
                   or (name == 'opencc-python-reimplemented' and f['filename'].endswith('.whl')))
        wheel = DOWNLOADS / row['filename']
        assert sha(wheel) == row['digests']['sha256']
        origins.append(dict(name=name, version=metadata['info']['version'], filename=wheel.name,
                            source_url=row['url'], sha256=sha(wheel), publisher_hash_verified=True))
        with zipfile.ZipFile(wheel) as archive:
            assert archive.testzip() is None
            for info in archive.infolist():
                if info.is_dir():
                    continue
                path = PurePosixPath(info.filename)
                assert not path.is_absolute() and '..' not in path.parts and '\\' not in info.filename and ':' not in info.filename
                if info.filename.endswith('cudnn64_9.dll'):
                    omitted.append(dict(wheel=wheel.name, member=info.filename, reason='GPU runtime excluded from the CPU pack'))
                    continue
                parts = path.parts
                if '.data' in parts[0]:
                    assert parts[1:3] == ('data', 'Scripts')
                    target = output / 'bin' / parts[-1]
                else:
                    target = output / 'site' / info.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as handle:
                    handle.write(archive.read(info))
    license_dir = output / 'licenses'
    license_dir.mkdir()
    # Wheels lacking notices receive the exact upstream notices from the
    # matching release tag, including ONNX Runtime third-party terms.
    for name in (['sherpa-src-r1', 'onnxruntime-src-r1'] if args.kind == 'voice'
                 else ['ctranslate2-src-r1', 'sentencepiece-src-r1']):
        for file in (NOTICES / name).rglob('*'):
            if file.is_file() and file.name not in {'CMakeLists.txt'}:
                target = license_dir / name / file.relative_to(NOTICES / name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, target)
    shutil.copyfile(NOTICES / 'sources.json', license_dir / 'upstream-commits.json')
    models = {}
    if args.kind == 'voice':
        source = WORK / 'native-r2/models/kokoro-int8-multi-lang-v1_1'
        target = output / 'models/kokoro'
        target.mkdir(parents=True)
        for name in ('model.int8.onnx', 'voices.bin', 'tokens.txt', 'lexicon-zh.txt', 'lexicon-us-en.txt',
                     'lexicon-gb-en.txt', 'date-zh.fst', 'number-zh.fst', 'phone-zh.fst', 'LICENSE', 'README.md'):
            shutil.copyfile(source / name, target / name)
        model_archive = DOWNLOADS / 'kokoro-int8-multi-lang-v1_1.tar.bz2'
        assert sha(model_archive) == 'a1e94694776049035c4f2c6529f003aaece993c76aae9a78995831c3c4dcafc6'
        confirmed = set()
        with tarfile.open(model_archive, 'r:bz2') as archive:
            for info in archive:
                if info.isfile() and PurePosixPath(info.name).parent.as_posix() == 'kokoro-int8-multi-lang-v1_1':
                    file = target / PurePosixPath(info.name).name
                    if file.is_file():
                        assert hashlib.sha256(archive.extractfile(info).read()).hexdigest() == sha(file)
                        confirmed.add(file.name)
        assert confirmed == {f.name for f in target.iterdir()}
        models['kokoro'] = dict(id='Kokoro-82M-v1.1-zh', creator='hexgrad; sherpa-onnx conversion by k2-fsa',
                                  source_url='https://huggingface.co/hexgrad/Kokoro-82M-v1.1-zh',
                                  source_archive='kokoro-int8-multi-lang-v1_1.tar.bz2',
                                  source_archive_sha256=sha(DOWNLOADS / 'kokoro-int8-multi-lang-v1_1.tar.bz2'),
                                  path='models/kokoro/model.int8.onnx', sha256=sha(target / 'model.int8.onnx'),
                                  license='Apache-2.0', license_path='models/kokoro/LICENSE',
                                  obligations=['Preserve model source and notices when redistributing model files.'])
        omitted.append(dict(source='kokoro-int8-multi-lang-v1_1', members=['dict/', 'espeak-ng-data/'],
                            reason='Unused by sherpa-onnx 2.0.0 lexicon-based path; actual zh/en inference tested without these data.'))
        ident, engine = 'kokoro-zh-en-int8', {'id': 'kokoro-sherpa-cpu-v1', 'sherpa_onnx': '2.0.0', 'onnxruntime': '1.28.2'}
    else:
        build = json.loads((args.native / 'build.json').read_bytes())
        binary = Path(build['binary'])
        assert sha(binary) == build['sha256'] and build['backend'] == 'Ruy'
        assert not any(build[key] for key in ('mkl', 'intel_openmp', 'cuda', 'cudnn'))
        shutil.copyfile(binary, output / 'bin/ct2-translator.exe')
        shutil.copyfile(args.native / 'build.json', license_dir / 'native-build.json')
        native_source = WORK / 'ctranslate2-src-r1'
        # This MIT dependency is a header-only library compiled into the
        # executable. Preserve its original notice verbatim, not just CT2's.
        half = (native_source / 'include/half_float/half.hpp').read_text('utf-8').split('// Version', 1)[0]
        (license_dir / 'half-float-MIT.txt').write_text(half, encoding='utf-8', newline='\n')
        for part in ('third_party/cpu_features', 'third_party/cxxopts', 'third_party/ruy',
                     'third_party/spdlog', 'third_party/ruy/third_party/cpuinfo'):
            for file in (native_source / part).rglob('*'):
                if file.is_file() and '.git' not in file.parts and any(token in file.name.upper() for token in ('LICENSE', 'COPYING', 'NOTICE')):
                    target = license_dir / 'native-dependencies' / file.relative_to(native_source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(file, target)
        toolchain = next((WORK / 'toolchains/llvm-mingw').glob('*/LICENSE.TXT')).parent
        for file in [toolchain / 'LICENSE.TXT', *(toolchain / 'x86_64-w64-mingw32/share/mingw32').glob('COPYING*')]:
            target = license_dir / 'native-toolchain' / file.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)
        origins.append(dict(name='ctranslate2-native-ruy', version='4.8.3', sha256=build['sha256'],
                            source_commit=build['upstream_commit'], backend='Ruy',
                            original_windows_wheel_redistributed=False))
        for pair, directory, license in [('zh-en', args.zh_en, 'CC-BY-4.0'), ('en-zh', args.en_zh, 'CC-BY-4.0')]:
            directory = directory.resolve()
            verification = json.loads((directory / 'verification.json').read_bytes())
            assert verification['status'] == 'passed' and verification['pair'] == pair
            source = directory / 'converted'
            assert (source / 'LICENSE').read_text('utf-8').startswith('Attribution 4.0 International')
            target = output / 'models' / pair
            target.mkdir(parents=True)
            for file in verification['files']:
                assert sha(source / file['path']) == file['sha256']
                shutil.copyfile(source / file['path'], target / file['path'])
            models[pair] = dict(id='OPUS-MT-' + pair + '-2020-07-17-int8', creator='Helsinki-NLP / OPUS-MT',
                                source_url='https://huggingface.co/Helsinki-NLP/opus-mt-' + pair,
                                source_archive=verification['model_source_archive'],
                                source_archive_sha256=verification['model_source_archive_sha256'],
                                transformation='CTranslate2 4.8.3 OpusMTConverter int8',
                                path='models/' + pair + '/model.bin', sha256=sha(target / 'model.bin'),
                                license=license, license_path='models/' + pair + '/LICENSE',
                                obligations=['Retain model attribution and license; note int8 conversion.'])
        ident, engine = 'opus-zh-en-cpu-int8', {'id': 'opus-ctranslate2-ruy-cpu-v1', 'ctranslate2': '4.8.3', 'backend': 'Ruy', 'sentencepiece': '0.2.2', 'opencc': '0.1.7'}
    files = [dict(path=p.relative_to(output).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
             for p in sorted(output.rglob('*')) if p.is_file()]
    manifest = dict(protocol='agent-community-cpu-v1', id=ident, format_version='1.0.0',
                     generated_at_utc=datetime.now(timezone.utc).isoformat(), runtime='cp313-win_amd64',
                     engine=engine, models=models, original_wheels=origins, omitted=omitted,
                     files=files, network=False, virtual_environment=False)
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(id=ident, path=str(output), manifest_sha256=sha(output / 'manifest.json'),
                           files=len(files), uncompressed_bytes=sum(f['bytes'] for f in files))), flush=True)


if __name__ == '__main__':
    main()
