"""Build the frozen offline Windows text profile with native MSVC, no installation."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/shaping69-20261107-r1'
VCVARS = Path('C:/Program Files (x86)/Microsoft Visual Studio/2019/BuildTools/VC/Auxiliary/Build/vcvars64.bat')
COMPILER = VCVARS.parents[2] / 'Tools/MSVC/14.29.30133/bin/Hostx64/x64/cl.exe'
FT_BASE = ['ftsystem', 'ftinit', 'ftdebug', 'ftbase', 'ftbbox', 'ftglyph', 'ftbitmap',
           'ftmm', 'ftfstype', 'ftgasp', 'ftcid', 'ftstroke', 'ftsynth', 'fttype1', 'ftwinfnt']
FT_MODULES = [('autofit', 'autofit_module_class', 'FT_Module_Class'),
              ('truetype', 'tt_driver_class', 'FT_Driver_ClassRec'),
              ('cff', 'cff_driver_class', 'FT_Driver_ClassRec'),
              ('psaux', 'psaux_module_class', 'FT_Module_Class'),
              ('psnames', 'psnames_module_class', 'FT_Module_Class'),
              ('pshinter', 'pshinter_module_class', 'FT_Module_Class'),
              ('sfnt', 'sfnt_module_class', 'FT_Module_Class'),
              ('smooth', 'ft_smooth_renderer_class', 'FT_Renderer_Class'),
              ('raster', 'ft_raster1_renderer_class', 'FT_Renderer_Class')]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def validator():
    spec = importlib.util.spec_from_file_location('shaping69_freeze_guard', ROOT / 'docs/validation/validate_shaping69.py')
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--freeze-run', default='r1')
    parser.add_argument('--source-run', default='r3')
    args = parser.parse_args()
    assert all(value.isalnum() and len(value) <= 32 for value in vars(args).values())
    valid = validator()
    frozen_path = BASE / ('freeze-' + args.freeze_run) / 'verification.json'
    frozen = json.loads(frozen_path.read_bytes())
    valid.guard(frozen)
    stage = ROOT / ('local/agent-ffmpeg/shaping69-native-20261107-' + args.run)
    assert stage.drive.upper() == 'E:' and not stage.exists()
    stage.mkdir()
    build, runtime = stage / 'build', stage / 'runtime'
    build.mkdir()
    runtime.mkdir()
    (build / 'tmp').mkdir()
    upstream = ROOT / ('local/agent-ffmpeg/shaping69-20261106-' + args.source_run) / 'upstream'
    assert sha(upstream.parent / 'sources.json') == frozen['source_manifest_sha256']
    ft, hb, sb = (upstream / name for name in ('freetype-2.15.0', 'harfbuzz-15.1.0', 'sheenbidi-v3.0.0'))
    assert VCVARS.is_file() and COMPILER.is_file()
    include = build / 'include'
    shutil.copytree(ft / 'include', include)
    module_path = include / 'freetype/config/ftmodule.h'
    module_path.write_text('/* Agent editor kit grayscale TrueType/CFF profile. Original sources unchanged. */\n'
        + '\n'.join('FT_USE_MODULE( ' + cls + ', ' + name + ' )' for _, name, cls in FT_MODULES) + '\n', encoding='ascii')
    option_path = include / 'freetype/config/ftoption.h'
    options = option_path.read_text('utf-8')
    # No environmental configuration or optional compressed/SVG/color font loader.
    for option in ('ENVIRONMENT_PROPERTIES', 'USE_LZW', 'USE_ZLIB', 'SVG'):
        options = options.replace('#define FT_CONFIG_OPTION_' + option, '#undef FT_CONFIG_OPTION_' + option)
    option_path.write_text(options, encoding='utf-8', newline='\n')
    units = [('ft-' + name, ft / ('src/base/' + name + '.c'), 'c') for name in FT_BASE]
    units += [('ft-' + folder, ft / ('src/' + folder + '/' + folder + '.c'), 'c') for folder, _, _ in FT_MODULES]
    units += [('sheenbidi', sb / 'Source/SheenBidi.c', 'c'), ('harfbuzz', hb / 'src/harfbuzz.cc', 'cpp'),
              ('aek', ROOT / 'development/shaping69/native/aek_text_native.cpp', 'cpp')]
    objects, commands = [], []
    common = ['/nologo', '/c', '/O2', '/MT', '/utf-8', '/Brepro', '/D_CRT_SECURE_NO_WARNINGS',
              '/DWIN32_LEAN_AND_MEAN', '/DNOMINMAX', '/DSB_CONFIG_UNITY', '/DFT2_BUILD_LIBRARY',
              '/DHAVE_FREETYPE', '/I' + str(include), '/I' + str(hb / 'src'), '/I' + str(sb / 'Headers'), '/I' + str(sb / 'Source')]
    for number, (name, source, language) in enumerate(units):
        assert source.is_file(), source
        obj = build / (name + '.obj')
        objects.append(obj)
        arguments = [*common, *(['/TP', '/EHsc', '/std:c++17', '/bigobj'] if language == 'cpp' else ['/TC']),
                     '/Fo' + str(obj), str(source)]
        response = build / (f'compile-{number:02}.rsp')
        response.write_text('\n'.join(subprocess.list2cmdline([value]) for value in arguments) + '\n', encoding='utf-8-sig')
        commands.append('cl @' + response.name)
    binary = runtime / 'aek_text_native.dll'
    link = ['/NOLOGO', '/DLL', '/Brepro', '/INCREMENTAL:NO', '/OUT:' + str(binary),
            '/IMPLIB:' + str(build / 'aek_text_native.lib'), *map(str, objects)]
    (build / 'link.rsp').write_text('\n'.join(subprocess.list2cmdline([value]) for value in link) + '\n', encoding='utf-8-sig')
    commands.append('link @link.rsp')
    batch = build / 'build.cmd'
    batch.write_text('@echo off\nchcp 65001 >nul\ncall "' + str(VCVARS) + '" >vcvars.stdout 2>vcvars.stderr\n'
        'if errorlevel 1 exit /b 1\n' + '\n'.join('echo BUILD_STEP ' + str(index) + '\n' + command + '\nif errorlevel 1 exit /b 1'
        for index, command in enumerate(commands)) + '\nexit /b 0\n', encoding='utf-8', newline='\r\n')
    env = dict(os.environ, TEMP=str(build / 'tmp'), TMP=str(build / 'tmp'))
    started = datetime.now(timezone.utc).isoformat()
    with (build / 'build.stdout').open('xb') as stdout, (build / 'build.stderr').open('xb') as stderr:
        result = subprocess.run([str(Path('C:/Windows/System32/cmd.exe')), '/d', '/c', 'build.cmd'], cwd=build,
            env=env, stdout=stdout, stderr=stderr, timeout=2400, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        save(BASE / ('build-' + args.run) / 'verification.json', dict(status='build-failed', exit_code=result.returncode,
            freeze_sha256=sha(frozen_path), stage=str(stage), started_at_utc=started, native_library_loaded=False))
        print((build / 'build.stdout').read_text('utf-8', errors='replace')[-10000:])
        return 1
    assert binary.is_file()
    licenses = runtime / 'licenses'
    licenses.mkdir()
    for source, name in [(sb / 'LICENSE', 'SheenBidi-Apache-2.0.txt'), (hb / 'COPYING', 'HarfBuzz-COPYING.txt'),
                         (ROOT / 'LICENSE', 'Agent-editor-kit-MIT.txt'),
                         (ft / 'LICENSE.TXT', 'FreeType-LICENSE.txt'), (ft / 'docs/FTL.TXT', 'FreeType-FTL.txt'),
                         (ROOT / 'development/text68/src/aek_unicode17/LICENSE_UNICODE.txt', 'Unicode-LICENSE.txt'),
                         (ROOT / 'development/text68/src/aek_unicode17/LICENSE_UNISEG.txt', 'uniseg-MIT.txt')]:
        shutil.copyfile(source, licenses / name)
    font_rows = {}
    source_fonts = [('latin', upstream / 'fonts/notoserif/NotoSerif-Regular.ttf'),
                    ('arabic', upstream / 'fonts/notosansarabic/NotoSansArabic-Regular.ttf'),
                    ('hebrew', upstream / 'fonts/notosanshebrew/NotoSansHebrew-Regular.ttf'),
                    ('devanagari', upstream / 'fonts/notosansdevanagari/NotoSansDevanagari-Regular.ttf'),
                    ('cjk', ROOT / 'product/src/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf')]
    (runtime / 'fonts').mkdir()
    for role, source in source_fonts:
        target = runtime / ('fonts/' + role + '.ttf')
        shutil.copyfile(source, target)
        license_source = (ROOT / 'product/src/ai_ad_editor/material_data/licenses/google-notosanssc.txt') if role == 'cjk' else source.parent / 'OFL.txt'
        shutil.copyfile(license_source, licenses / (role + '-OFL.txt'))
        font_rows[role] = dict(path=target.relative_to(runtime).as_posix(), sha256=sha(target), license='OFL-1.1')
    python = runtime / 'python'
    python.mkdir()
    for source in [ROOT / 'development/shaping69/src/aek_shaping', ROOT / 'development/text68/src/aek_unicode17']:
        shutil.copytree(source, python / source.name, ignore=shutil.ignore_patterns('__pycache__'))
    (runtime / 'run.py').write_text("from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parent/'python'))\nfrom aek_shaping.cli import main\nraise SystemExit(main())\n", encoding='utf-8')
    (runtime / 'NOTICE.txt').write_text('Agent editor kit independent text development runtime; not the installed product.\n'
        'Portions of this software are copyright 2026 The FreeType Project (https://freetype.org). All rights reserved.\n'
        'SheenBidi Apache-2.0; HarfBuzz Old MIT; FreeType FTL; Noto OFL-1.1; Unicode and uniseg notices are in licenses/.\n'
        'Native Windows x64, grayscale scalable TrueType/CFF, explicit SHA-pinned fonts. No system fallback or runtime download.\n', encoding='utf-8')
    manifest = dict(format='aek-shaping69-native-v1', binary_filename=binary.name, binary_sha256=sha(binary),
        versions=dict(sheenbidi='3.0.0', harfbuzz='15.1.0', freetype='2.15.0'), fonts=font_rows,
        compiler=dict(path=str(COMPILER), sha256=sha(COMPILER), static_crt=True),
        freeze_sha256=sha(frozen_path), source_manifest_sha256=frozen['source_manifest_sha256'],
        ft_module_profile=sha(module_path), ft_option_profile=sha(option_path),
        product_integrated=False, formal_skill_modified=False, runtime_network=False)
    save(runtime / 'native.json', manifest)
    payload = {path.relative_to(runtime).as_posix(): sha(path) for path in runtime.rglob('*') if path.is_file()}
    save(runtime / 'payload.json', dict(format='aek-shaping69-payload-v1', files=payload))
    archive = stage / 'aek-shaping69-windows-x64.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(runtime.rglob('*')):
            if path.is_file():
                zipped.write(path, path.relative_to(runtime).as_posix())
    valid.guard(frozen)
    proof = dict(status='built-not-yet-functionally-validated', started_at_utc=started,
        observed_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=0, freeze_sha256=sha(frozen_path),
        runtime=str(runtime), archive=str(archive), archive_sha256=sha(archive), payload_files=len(payload) + 1,
        native_binary_sha256=sha(binary), compiler=manifest['compiler'], compiled_units=len(units),
        no_packages_installed=True, no_virtualization=True, temporary_directory=str(build / 'tmp'),
        native_library_loaded=False, formal_skill_modified=False, full_goal_closed=False)
    save(BASE / ('build-' + args.run) / 'verification.json', proof)
    print(json.dumps(proof, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
