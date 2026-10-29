"""Attach actual browser screenshots without rewriting earlier README evidence rows."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/job-enumeration-20261029-r1'


def load(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rows(text, prefix):
    return re.findall(r'^\| ' + prefix + r'\d+ \|.*$', text, re.M)


def main():
    prior_commit = ROOT / 'local/agent-ffmpeg/source63-recovery-optical-commit-r2/verification.json'
    if not prior_commit.is_file():
        print(json.dumps(dict(status='pending', missing='first normal-push receipt', mutated=False)))
        return 2
    assert load(prior_commit)['status'] == 'passed'
    proof = ROOT / 'docs/validation/evidence/optical-pack-gallery-20261029-r1/verification.json'
    report = load(proof)
    assert report['status'] == 'passed' and len(report['choices']) == 8
    assert report['second_play_pauses_first'] and report['mobile_selection_passed']
    assert report['page_errors'] == report['external_requests'] == []
    assert report['cleanup'] == dict(owned_pages_closed=1, context_closed=True, browser_closed=True)
    for item in report['screenshots']:
        assert sha(ROOT / item['path']) == item['sha256']
    installation = load(BASE / 'installation-candidate-r1/verification.json')
    assert all(sha(Path(p)) == h for p, h in installation['registered_skill_file_hashes'].items())
    assert load(ROOT / 'agent-ffmpeg-local-install-manifest.json')['cli_version'] == '0.1.59'
    goal = ROOT / 'docs/product/GOAL_GAPS_20261025.md'
    goal_pin = sha(goal)
    for name, lead, label in [
        ('README.md', '**光效选型交互已实测。** 8个按钮逐项核对模板ID／摘要，真实视频播放与切换、电脑／手机宽度截图通过；本次浏览器已关闭。', '光效选型页真实浏览器'),
        ('README.zh-TW.md', '**光效選型互動已實測。** 8個按鈕逐項核對模板ID／摘要，真實影片播放與切換、電腦／手機寬度截圖通過；本次瀏覽器已關閉。', '光效選型頁真實瀏覽器'),
        ('README.en.md', '**The optical gallery passed actual browser interaction checks.** All8 selections matched real template IDs/hashes; H.264 playback, play-one/pause-others and desktop/mobile-width screenshots passed. The owned browser was closed.', 'Optical gallery in native Chrome'),
    ]:
        path = ROOT / name
        old = path.read_text(encoding='utf-8')
        old_rows = rows(old, 'R')
        assert len(old_rows) == 524
        title, separator, rest = old.partition('\n\n')
        assert separator
        added = lead + ' [Offline gallery](docs/assets/optical-pack-20261029-r1/index.html) · [Actual screenshots and checks](docs/validation/光效选型页实测_2026-10-29.md)\n\n'
        added += '<details>\n<summary>Actual gallery screenshot / 实际页面 / 實際頁面</summary>\n\n![Actual offline optical gallery](docs/assets/optical-pack-gallery-20261029-r1/desktop.png)\n\n</details>\n\n'
        text = title + separator + added + rest
        new_row = '| R525 | ' + label + ' | All8 actual selections/IDs/SHA256/author clocks, 44 local targets, real H.264 playback, pause-others, desktop/mobile-width screenshots; owned page/browser closed. [Evidence](docs/validation/evidence/optical-pack-gallery-20261029-r1/verification.json) |'
        text = text.replace(old_rows[-1], old_rows[-1] + '\n' + new_row, 1)
        assert rows(text, 'R')[:524] == old_rows and len(rows(text, 'R')) == 525
        assert old[old.index('<!-- aek-history-summary -->'):] in text.replace('\n' + new_row, '', 1)
        path.write_text(text, encoding='utf-8', newline='\n')
    optical = ROOT / 'docs/product/OPTICAL_EFFECT_PACK.md'
    stage_is_frozen = (ROOT / 'local/agent-ffmpeg/music63-skill-stage-r1').exists()
    # A staged candidate pins this document. Do not mutate a post-test gate.
    if not stage_is_frozen:
        text = optical.read_text(encoding='utf-8')
        assert '光效选型页实测_2026-10-29.md' not in text
        text += '\n## 选型页面实际交互\n\n[真实浏览器核验与电脑／手机截图](../validation/光效选型页实测_2026-10-29.md)：8个选择按钮输出的模板ID、SHA256和作者时钟逐项一致，44个本地资源目标存在，H.264实际播放／切换通过。本次独立页面和浏览器已关闭。这里验证选型操作；客户真实素材与人类视听验收仍须另做。\n\n![真实电脑宽度选型页面](../assets/optical-pack-gallery-20261029-r1/desktop.png)\n'
        optical.write_text(text, encoding='utf-8', newline='\n')
    assert sha(goal) == goal_pin and len(rows(goal.read_text(encoding='utf-8'), 'G')) == 38
    assert all(sha(Path(p)) == h for p, h in installation['registered_skill_file_hashes'].items())
    out = ROOT / 'docs/validation/evidence/optical-pack-gallery-docs-20261029-r1'
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    receipt = dict(status='passed', README_rows=525, old_524_rows_preserved=True,
                   actual_gallery_evidence_sha256=sha(proof), formal_cli='0.1.59', formal_files_unchanged=95,
                   goal_rows_preserved=38, optical_document_updated_before_stage=not stage_is_frozen,
                   full_goal_closed=False)
    (out / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
