"""Prepare reviewed Skill bytes and installation guides after real timing checks."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-control-20261025-r1'


def main():
    installation = json.loads((BASE / 'installation-r1/verification.json').read_bytes())
    faults = json.loads((BASE / 'faults-r1/verification.json').read_bytes())
    assert faults['status'] == 'passed' and len(faults['cases']) == 5
    assert installation['cli_version'] == '0.1.13' and installation['source_file_count'] == 203
    guide = ROOT / 'docs/product/COMMUNITY_LOCAL_DELIVERY.md'
    text = guide.read_text('utf-8')
    text = text.replace('v0.1.0-alpha.4-local.10', 'v0.1.0-alpha.4-local.11')
    text = text.replace('CLI 0.1.12', 'CLI 0.1.13', 1)
    text = text.replace('## CLI 0.1.12 语义任务恢复', '## CLI 0.1.12 历史语义任务恢复', 1)
    text = text.replace('0e75ed90c1aac9b8b40055a96d81b48e8aa23216a7c86ea5331aa3826057e312', installation['archive_sha256'])
    text = text.replace('sha256:4d4a9dc8d80aa45123619bf0c54cc494bb54c5cc3e7c6e6997130485d01dd3cf', installation['manifest_sha256'])
    text = text.replace('unified-skill-r11.zip', 'unified-skill-r12.zip').replace('community-unified-skill-package-0.1.12.json', 'community-unified-skill-package-0.1.13.json')
    text = text.replace('本轮增加[语义任务恢复]', '本轮增加完整性读取的超时/取消与部分摘要丢弃，保留[语义任务恢复]', 1)
    text += '\n## CLI 0.1.13 当前交付 / Current delivery\n\n' + str(installation['archive_bytes']) + ' bytes、203 个产品 Python 文件；[读取超时/取消实际核验](../validation/完整性校验超时取消实测_2026-10-25.md)。旧 local.10/r11 与原收据保留。CPU/CUDA 和统一入口验证按本批收据记录；模型仍逐命令加载，完整 G32/G33 未关闭。\n'
    guide.write_text(text, encoding='utf-8', newline='\n')
    guide = ROOT / 'docs/product/SEMANTIC_JOB_RECOVERY.md'
    text = guide.read_text('utf-8')
    text = text.replace('CLI 0.1.12 本机安装版把', 'CLI 0.1.12 起把', 1)
    old = '模型仍在每个命令内加载，尚无常驻服务；已有同步完整性检查可能使总超时响应延后，须报告实际墙钟。'
    assert old in text
    text = text.replace(old, 'CLI 0.1.13 在完整性读取之间响应超时/取消，保留原错误码、丢弃部分摘要并关闭当前句柄；完整验证文件的读锁不变。\n恢复在操作预算退出后继续完整检查输出。`adapter-list/adapter-inspect/verify` 也支持超时/取消。\n模型仍逐命令加载；操作系统阻塞的读取不能立即抢占，须报告实际墙钟与 `errors[].diagnostics`。', 1)
    text += '\n[CLI 0.1.13 真实读取超时/取消](../validation/完整性校验超时取消实测_2026-10-25.md) · [实现契约](../specs/可中断完整性校验契约_20261025.md)。\n'
    guide.write_text(text, encoding='utf-8', newline='\n')
    guide = ROOT / 'docs/product/SEMANTIC_RETRIEVAL.md'
    text = guide.read_text('utf-8').replace('This guide describes CLI 0.1.12 / `v0.1.0-alpha.4-local.10`',
        'This guide describes CLI 0.1.13 / `v0.1.0-alpha.4-local.11`', 1)
    text = text.replace('当前 CLI 0.1.12 新增受管任务恢复', 'CLI 0.1.12 新增受管任务恢复，当前 0.1.13 再补读取中的超时/取消', 1)
    text = text.replace('2026-10-25 当前 CLI 0.1.12：', '2026-10-25 历史 CLI 0.1.12：', 1)
    text += '\n当前 CLI 0.1.13 在不跳过完整摘要/读锁的前提下响应校验中的取消/超时，返回已读字节诊断。\n[实际耗时与边界](../validation/完整性校验超时取消实测_2026-10-25.md)。模型仍逐命令加载，三条原查询错误保留。\n'
    guide.write_text(text, encoding='utf-8', newline='\n')
    draft = ROOT / 'local/agent-ffmpeg/semantic-control-skill-draft-r1'
    canonical = ROOT / 'skills/agent-ffmpeg-local-editor'
    for path in draft.rglob('*'):
        if path.is_file():
            (canonical / path.relative_to(draft)).write_bytes(path.read_bytes())
    captured = BASE / 'installation-r1/capabilities.stdout.json'
    (ROOT / 'docs/product/semantic-control-capabilities-cli-0.1.13.json').write_bytes(captured.read_bytes())
    print(json.dumps(dict(status='prepared', cli_version='0.1.13', skill_files_updated=4)))


if __name__ == '__main__':
    main()
