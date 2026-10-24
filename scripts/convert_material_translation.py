"""Convert a preserved official OPUS Marian archive to native CPU int8 CT2.

No upstream shell scripts, pip, virtual environment, or network is used.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--numpy-site', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pair', choices=['zh-en', 'en-zh'], required=True)
    args = parser.parse_args()
    archive, native, output = args.archive.resolve(strict=True), args.native.resolve(strict=True), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    original = output / 'original'
    original.mkdir()
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        for info in zipped.infolist():
            name = PurePosixPath(info.filename)
            if name.is_absolute() or any(x in {'..', ''} for x in name.parts) or '\\' in info.filename or ':' in info.filename:
                raise ValueError('Unsafe model archive member')
            if info.is_dir():
                (original / info.filename).mkdir(parents=True, exist_ok=True)
                continue
            if info.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError('Model archive symlink rejected')
            target = original / info.filename
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as handle:
                handle.write(zipped.read(info))
    sys.path[:0] = [str(native / 'site'), str(args.numpy_site.resolve(strict=True))]
    dlls = os.add_dll_directory(str(native / 'bin'))
    import yaml
    import ctranslate2
    import sentencepiece as spm
    config = yaml.safe_load((original / 'decoder.yml').read_text('utf-8'))
    for path in config['models'] + config['vocabs']:
        assert (original / path).resolve().is_relative_to(original)
    os.chdir(output)
    start = time.perf_counter()
    ctranslate2.converters.OpusMTConverter('original').convert('converted', quantization='int8')
    for name in ('source.spm', 'target.spm', 'LICENSE', 'README.md', 'decoder.yml'):
        shutil.copyfile(original / name, output / 'converted' / name)
    # Load native C++ files by relative ASCII paths in a Unicode Windows root.
    source_sp = spm.SentencePieceProcessor(model_file='converted/source.spm')
    target_sp = spm.SentencePieceProcessor(model_file='converted/target.spm')
    translator = ctranslate2.Translator('converted', device='cpu', compute_type='int8', intra_threads=2, inter_threads=1)
    inputs = (['请先预览视频，再导出可编辑工程。', '保留原声、字幕和背景音乐。'] if args.pair == 'zh-en'
              else ['Preview the video before exporting the editable project.', 'Keep the original speech, subtitles, and background music.'])
    batch = [source_sp.encode(t, out_type=str) for t in inputs]
    if args.pair == 'en-zh':
        vocab = json.loads(Path('converted/shared_vocabulary.json').read_text('utf-8'))
        assert '>>cmn_Hans<<' in vocab
        batch = [['>>cmn_Hans<<', *tokens] for tokens in batch]
    results = translator.translate_batch(batch, beam_size=4, max_decoding_length=256,
                                          max_input_length=512, length_penalty=1)
    translations = [target_sp.decode(r.hypotheses[0]) for r in results]
    assert all(translations)
    files = []
    for path in sorted((output / 'converted').rglob('*')):
        if path.is_file():
            files.append({'path': path.relative_to(output / 'converted').as_posix(), 'bytes': path.stat().st_size,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    receipt = dict(status='passed', pair=args.pair, model_source_archive=archive.name,
                   model_source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                   engine='ctranslate2', engine_version=ctranslate2.__version__, device='cpu', compute_type='int8',
                   converter='OpusMTConverter', elapsed_seconds=time.perf_counter() - start,
                   input=inputs, output=translations, files=files, semantic_human_acceptance=False,
                   upstream_scripts_executed=False, network=False, virtualization=False)
    (output / 'verification.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    dlls.close()


if __name__ == '__main__':
    main()
