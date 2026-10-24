"""Build optional NVIDIA packs from verified upstream binaries and local models.

CUDA/cuDNN remain separately installed system dependencies under NVIDIA terms.
The CPU Ruy path is packaged separately. This script never downloads inputs.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'product/.runtime/materials-20261024'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def build(kind, output, cpu_packs):
    cpu_id = 'kokoro-zh-en-int8' if kind == 'voice' else 'opus-zh-en-cpu-int8'
    source = cpu_packs.resolve() / cpu_id
    shutil.copytree(source, output)
    manifest = json.loads((output / 'manifest.json').read_bytes())
    if kind == 'voice':
        ident = 'kokoro-zh-en-cuda13'
        model = WORK / 'gpu-sources-r1/kokoro-multi-lang-v1_1/kokoro-multi-lang-v1_1'
        native = WORK / 'gpu-sources-r1/sherpa-onnx-v2.0.0-cuda-13.x-cudnn-9.x-onnxruntime1.28.2-win-x64-cuda'
        archive = WORK / 'downloads/kokoro-multi-lang-v1_1.tar.bz2'
        assert sha(archive) == 'a3f4c73d043860e3fd2e5b06f36795eb81de0fc8e8de6df703245edddd87dbad'
        binary_archive = WORK / 'downloads/sherpa-onnx-v2.0.0-cuda-13.x-cudnn-9.x-onnxruntime1.28.2-win-x64-cuda.tar.bz2'
        assert sha(binary_archive) == '9ebf79f814d3c26df501647042cc08383121b473d3a43d22a17c4f35d524b128'
        target = output / 'models/kokoro'
        (target / 'model.int8.onnx').unlink()
        for f in model.iterdir():
            if f.is_file():
                shutil.copyfile(f, target / f.name)
        dlls = list(native.rglob('*.dll'))
        assert any(f.name == 'onnxruntime_providers_cuda.dll' for f in dlls)
        names = {}
        for file in dlls:
            if file.name in names and names[file.name] != sha(file):
                raise ValueError('Conflicting upstream native DLL: ' + file.name)
            names[file.name] = sha(file)
            shutil.copyfile(file, output / 'bin' / file.name)
        extension_dir = output / 'site/sherpa_onnx/lib'
        for file in extension_dir.glob('*.dll'):
            replacement = output / 'bin' / file.name
            if not replacement.is_file():
                raise ValueError('GPU binary lacks Python extension dependency')
            # Load the GPU DLLs from bin so ONNX Runtime finds its CUDA
            # provider beside onnxruntime.dll, without two 267 MB copies.
            file.unlink()
        for file in native.rglob('*'):
            if file.is_file() and any(t in file.name.upper() for t in ('LICENSE', 'COPYING', 'NOTICE')):
                t = output / 'licenses/gpu-upstream' / file.relative_to(native)
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, t)
        manifest['models']['kokoro'].update(path='models/kokoro/model.onnx', sha256=sha(target/'model.onnx'),
            source_archive=archive.name, source_archive_sha256=sha(archive), transformation='Unquantized upstream ONNX model for CUDA execution')
        manifest['engine'] = dict(id='kokoro-sherpa-cuda13-v1', sherpa_onnx='2.0.0', onnxruntime='1.28.2', provider='cuda')
        manifest['gpu_source'] = dict(archive=binary_archive.name, sha256=sha(binary_archive), source='https://github.com/k2-fsa/sherpa-onnx/releases/tag/v2.0.0')
    else:
        ident = 'opus-zh-en-cuda12-int8'
        metadata = json.loads((ROOT/'sources/materials-20261024/research/ctranslate2.json').read_bytes())
        row = next(r for r in metadata['urls'] if r['filename'].endswith('cp313-cp313-win_amd64.whl'))
        archive = WORK / 'downloads' / row['filename']
        assert sha(archive) == row['digests']['sha256']
        with zipfile.ZipFile(archive) as zipped:
            for info in zipped.infolist():
                if info.is_dir() or info.filename.endswith('cudnn64_9.dll'):
                    continue
                if not info.filename.startswith(('ctranslate2/', 'ctranslate2-')):
                    raise ValueError('Unexpected CTranslate2 wheel path')
                target = output / 'site' / info.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zipped.read(info))
        (output / 'bin/ct2-translator.exe').unlink()
        notices = ROOT / 'sources/materials-20261024/vendor-notices/ctranslate2-4.8.3-win'
        provenance = json.loads((notices / 'provenance.json').read_bytes())
        if sha(output / 'site/ctranslate2/libiomp5md.dll') != provenance['libiomp5md_sha256']:
            raise ValueError('The optional Intel runtime differs from the original license receipt')
        for record in provenance['downloads']:
            for notice in record.get('notices', [record] if 'path' in record else []):
                if sha(ROOT / 'sources/materials-20261024' / notice['path']) != notice['sha256']:
                    raise ValueError('Original third-party notice changed')
        shutil.copytree(notices, output / 'licenses/optional-gpu-numerical-runtime')
        (output / 'GPU-DEPENDENCIES.txt').write_text(
            'Optional GPU numerical dependencies\n\n'
            'CTranslate2 itself retains its MIT license. This upstream Windows binary also links Intel MKL/oneDNN '
            'and ships Intel OpenMP libiomp5md.dll. These dependencies are not licensed by the agent editor kit license.\n'
            'The Intel executable redistributable remains subject to the original Intel EULA, including its '
            'prohibition on reverse engineering, decompiling or disassembly of that Intel redistributable. '
            'This restriction does not apply to the open-source agent editor kit or CTranslate2 source code.\n'
            'Read licenses/optional-gpu-numerical-runtime/intel-openmp/LICENSE.txt, mkl/LICENSE.txt, '
            'oneDNN-3.1.1/LICENSE and THIRD-PARTY-PROGRAMS, and provenance.json in that directory.\n'
            'NVIDIA driver/CUDA/cuBLAS/cuDNN are separately installed and retain NVIDIA terms; '
            'no NVIDIA system runtime files are copied into this pack.\n'
            'The separate source-built Ruy CPU translation pack does not include these Intel/MKL/CUDA backends.\n',
            encoding='utf8', newline='\n')
        manifest['original_wheels'].append(dict(name='ctranslate2', version='4.8.3', filename=archive.name,
            source_url=row['url'], sha256=sha(archive), publisher_hash_verified=True))
        manifest['engine'] = dict(id='opus-ctranslate2-cuda12-v1', ctranslate2='4.8.3', provider='cuda', compute_type='int8_float16')
        manifest['optional_dependency_notice'] = 'GPU-DEPENDENCIES.txt'
        manifest['intel_openmp_official_wheel_matches'] = provenance['official_wheel_dll_matches']
    manifest['id'] = ident
    manifest['gpu_runtime_terms'] = ('Optional GPU acceleration uses separately installed proprietary NVIDIA CUDA/cuBLAS/cuDNN libraries and driver; '
        'these are not represented as open-source bundled assets. Upstream Windows GPU dependencies retain their supplied licenses, including Intel runtime where present. '
        'Use the separate CPU Ruy path when requiring a deployment without proprietary numerical backends.')
    manifest['files'] = [dict(path=p.relative_to(output).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
                         for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'manifest.json']
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n', encoding='utf8', newline='\n')
    return dict(id=ident,path=str(output),manifest_sha256=sha(output/'manifest.json'),files=len(manifest['files']),bytes=sum(r['bytes'] for r in manifest['files']))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=['voice','translation'],required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cpu-packs',type=Path,default=ROOT/'local/agent-ffmpeg/community-packs-r2')
    args=p.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise ValueError('Use a new owned output; preserve prior packs')
    print(json.dumps(build(args.kind,output,args.cpu_packs),ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
