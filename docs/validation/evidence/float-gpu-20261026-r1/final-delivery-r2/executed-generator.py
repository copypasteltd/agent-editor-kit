"""Verify delivered GPU bytes, actual evidence, documentation and original goals."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/float-gpu-20261026-r1'
INSTALL = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.22/final-r4/installed'
BASELINE = '2fab08e5403ecb41ef09f7bc4fdd7609a5addbfc'
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def sha(p):
    with Path(p).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(p): return json.loads(Path(p).read_bytes())
def rows(s, prefix): return {m[1]: m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$', s, re.M)}
def git(*args): return subprocess.check_output([GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args], cwd=ROOT)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',default='r2');args=parser.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*',args.run)
    out = BASE/('final-delivery-'+args.run); out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def save(name, value): (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    report = {'status': 'running', 'goal_closed': False, 'virtualization': False, 'source_fallback': False}
    # The README links to this receipt. Publish a running status first so the
    # self-link is checked without claiming a result before checks finish.
    save('verification.json', report)
    try:
        install = load(BASE/'installation-final-r4/verification.json')
        assert install['source_and_installed_equal'] and install['cli_version'] == '0.1.24' and install['source_file_count'] == 217
        product = {p.name: sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(product) == 217 and product == {p.name: sha(p) for p in (INSTALL/'site/ai_ad_editor').glob('*.py')}
        assert product == {p['path']: p['sha256'] for p in install['source_files']}
        save('product-files.json', product)
        groups = {}
        for name in ('gpu', 'text', 'float', 'audio', 'render', 'legacy', 'text-legacy'):
            proof = load(BASE/(name+'-installed-final-r1/verification.json'))
            assert proof['status'] == 'passed' and proof['skipped'] == 0 and proof['frozen_equal'] and proof['product_files'] == product
            assert Path(proof['installed']).resolve() == INSTALL.resolve()
            groups[name] = proof['tests']
        assert groups == {'gpu': 23, 'text': 26, 'float': 98, 'audio': 64, 'render': 44, 'legacy': 191, 'text-legacy': 72}
        manifest = load(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert manifest['release'] == 'v0.1.0-alpha.4-local.22' and manifest['cli_version'] == '0.1.24'
        assert len(manifest['files']) == 71 and manifest['skill_count'] == 1 and manifest['module_count'] == 17
        for row in manifest['files']:
            assert sha(ROOT/row['path']) == row['sha256'] and (ROOT/row['path']).stat().st_size == row['bytes']
        runtime = load(ROOT/'local/agent-ffmpeg/runtime.json'); assert Path(runtime['installed_directory']).resolve() == INSTALL.resolve()
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve() == (ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation = load(BASE/'activation-final-r1/activation-and-registration.json')
        assert activation['status'] == 'passed' and len(activation['activation']['verified_packs']) == 4
        registered = load(BASE/'activation-final-r1/registration-current.json')
        assert registered['namespace_manifest_sha256'] == sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert registered['skill_count'] == 1 and registered['module_count'] == 17
        assert Path(registered['runtime_directory']).resolve() == INSTALL.resolve()
        case, four, bench = [load(BASE/(name+'/verification.json')) for name in ('case-r1', '4k-r1', 'benchmark-r1')]
        assert case['status'] == four['status'] == bench['status'] == 'passed'
        assert Path(case['installed']).resolve() == INSTALL.resolve()
        assert case['actual_frames'] == 72 and case['max_pcm_error'] <= 3e-7 and all(c['ok'] for c in case['checks'])
        assert four['registered_skill'] and (four['width'], four['height'], four['actual_frames'], four['fps']) == (3840, 2160, 8, 4)
        assert four['original_authoring_unchanged'] and four['font_license_preserved']
        for value in (four['GPU_receipt'], load(BASE/'case-r1/gpu-receipt.json'), bench['actual_GPU_receipt']):
            assert value['status'] == 'verified' and value['worker_closed'] and value['shared_handles_closed']
            assert value['native']['device']['name'] == 'NVIDIA GeForce RTX 3060'
            assert all(value['operations'].get(k, 0) > 0 for k in ('over', 'affine', 'paint', 'select'))
            assert value['probe']['subnormal_over_bit_exact'] and value['probe']['subnormal_affine_bit_exact']
        for folder, value in [('case-r1', case), ('4k-r1', four), ('benchmark-r1', bench)]:
            for call in value['calls']:
                for channel in ('stdout', 'stderr'):
                    assert sha(BASE/folder/(call['name']+'.'+channel+'.log')) == call[channel+'_sha256']
            for row in value.get('public_files', []):
                assert sha(ROOT/row['path']) == row['sha256'] and (ROOT/row['path']).stat().st_size == row['bytes']
        assert bench['actual_renders'] == 2 and len(bench['rounds']) == 2 and bench['frames_per_render'] == 8
        assert bench['all_8_frame_clocks_equal'] and bench['full_decoded_PCM_equal'] and bench['maximum_decoded_8bit_code_error'] <= 1
        assert not bench['exclusive_host'] and not bench['peak_RSS_measured'] and len(bench['logical_CPU_affinity']) == 4
        package = load(BASE/'package-r1/verification.json')
        assert package['status'] == 'passed' and package['registered_skill'] and package['font_license_preserved'] and len(package['checked_frames']) == 3 and all(v['equal'] for v in package['checked_frames'])
        for folder in ('case-r1', '4k-r1'):
            observed = load(BASE/folder/'visual-observation.json')
            assert not observed['continuous_playback'] and not observed['human_listening'] and not observed['natural_quality_accepted']
        kit = load(ROOT/'docs/skills/community-unified-skill-package-0.1.24-r25.json')
        assert kit['files'] == 102 and kit['skill_count'] == 1 and kit['module_count'] == 17
        archive = ROOT/kit['archive']; assert sha(archive) == kit['sha256'] and archive.stat().st_size == kit['bytes']
        with zipfile.ZipFile(archive) as z:
            assert len(z.namelist()) == len(set(z.namelist())) == 102
            assert sum(Path(name).name == 'SKILL.md' for name in z.namelist()) == 1
            for row in json.loads(z.read('KIT-FILES.json'))['files']:
                data = z.read(row['path']); assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
                if row['path'].startswith('skills/'): assert data == (ROOT/row['path']).read_bytes()
        isolated = load(BASE/'kit-r1/verification.json'); assert isolated['status'] == 'passed' and not isolated['real_discovery_changed']
        caps = load(ROOT/'docs/product/float-gpu-capabilities-cli-0.1.24.json')['data']['capabilities']; assert len(caps) == 75
        assert caps['hardware_acceleration']['float32_projection']['engine'] == 'render-owned-float32-opencl-v1'
        for name in ('README.md', 'README.zh-TW.md', 'README.en.md'):
            current = (ROOT/name).read_text('utf-8-sig'); historic = rows(git('show', BASELINE+':'+name).decode('utf-8-sig'), 'R')
            assert len(historic) == 170 and len(rows(current, 'R')) == 178 and all(rows(current, 'R')[k] == v for k, v in historic.items())
            assert len(rows(current, 'F')) == 57 and len(rows(current, 'S')) == 20 and len(rows(current, 'K')) == 17
        for suffix in ('', '.zh-TW', '.en'):
            m = (ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf-8-sig')
            assert len(rows(m, 'F')) == 57 and len(rows(m, 'S')) == 20
            for key, value in caps.items():
                match = re.search(r'^### `'+re.escape(key)+r'`\s*\n\s*```json\n(.*?)\n```', m, re.M|re.S)
                assert match and json.loads(match[1]) == value, key
        name = 'docs/product/GOAL_GAPS_20261025.md'
        old, new = rows(git('show', BASELINE+':'+name).decode('utf-8-sig'), 'G'), rows((ROOT/name).read_text('utf-8-sig'), 'G')
        assert len(new) == 38 and all(new[k].split('|')[5] == v.split('|')[5] for k, v in old.items())
        assert 'local.22-final-r4/CLI0.1.24/r25' in new['G38'].split('|')[3]
        assert 'GPU文字4K/8帧成片' in new['G32'].split('|')[3]
        guides = ['README.md', 'README.zh-TW.md', 'README.en.md', 'docs/product/FLOAT_GPU.md',
            'docs/product/COMMUNITY_LOCAL_DELIVERY.md', 'docs/product/CASES.md', 'docs/releases/CLI_0.1.24_LOCAL.md',
            'docs/validation/浮点GPU执行层实测_2026-10-26.md']
        missing = []; count = 0
        for name in guides:
            path = ROOT/name
            for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)', path.read_text('utf-8-sig')):
                if re.match(r'^[a-z]+:', target, re.I) or target.startswith('#'): continue
                count += 1
                if not (path.parent/unquote(target.split('#')[0])).resolve().exists(): missing.append([name, target])
        assert not missing, missing
        request = urllib.request.Request('https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10', headers={'User-Agent': 'agent-editor-kit-delivery-audit'})
        with urllib.request.urlopen(request, timeout=30) as response: releases = json.load(response); assert response.status == 200
        save('public-releases.json', releases); assert releases and releases[0]['tag_name'] == 'v0.1.0-alpha.3'
        assert git('branch', '--show-current').decode().strip() == 'main'
        assert git('remote', 'get-url', 'origin').decode().strip() == 'git@github.com:copypasteltd/agent-editor-kit.git'
        changed=set(git('diff','HEAD','--name-only','-z').decode('utf8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0'))
        inventory=[]
        for name in sorted(changed):
            if not name or (ROOT/name).is_relative_to(out): continue
            path=ROOT/name;assert path.is_file() and path.stat().st_size<95*1024**2,name
            inventory.append(dict(path=name,sha256=sha(path),bytes=path.stat().st_size))
        report.update(status='passed', product_files=217, skill_files=71, modules=17, test_groups=groups,
            functions=57, services=20, declarations=75, historical_rows_preserved=170, readme_rows=178,
            original_goal_closures_preserved=38, local_links_checked=count, public_release='v0.1.0-alpha.3',
            actual_4K_frames=8, paired_4K_renders=2, observed_speedup=bench['observed_speedup'], kit_sha256=kit['sha256'],files=inventory)
        save('verification.json', report); print(json.dumps({k:v for k,v in report.items() if k!='files'}), flush=True)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc)); save('verification.json', report); raise


if __name__ == '__main__': main()
