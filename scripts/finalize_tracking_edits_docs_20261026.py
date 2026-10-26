"""Update only current delivery references; retain actual r3 execution history."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-edits-20261026-r1'

def main():
    installation=json.loads((BASE/'installation-final-r4/verification.json').read_bytes())
    old_zip='68106d1def22cf0ec6d5f3bcafceebcfe2e46a590b332cdc28bcee5c852b654c'
    old_manifest='51d5cdafdc877cc470b28fd3c4742fc7b65b2cd1a12155dc0c90d0cad0e8ba71'
    names=['README.md','README.en.md','README.zh-TW.md','docs/releases/CLI_0.1.27_LOCAL.md',
        'docs/validation/跟踪剪辑实测_2026-10-26.md','docs/product/COMMUNITY_LOCAL_DELIVERY.md',
        'docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md']
    for name in names:
        path=ROOT/name;text=path.read_text('utf-8-sig')
        text=text.replace('local.25/final-r3/installed','local.25/final-r4/installed').replace('local.25-final-r3','local.25-final-r4')
        text=text.replace('local.25/candidate-r3/bundle.zip','local.25/candidate-r4/bundle.zip')
        text=text.replace(old_zip,installation['archive_sha256']).replace(old_manifest,installation['manifest_sha256'].removeprefix('sha256:'))
        text=text.replace('tracking-edits-20261026-r1/installation-final-r3/verification.json','tracking-edits-20261026-r1/installation-final-r4/verification.json')
        text=text.replace('tracking-edits-20261026-r1/activation-final-r3/activation-and-registration.json','tracking-edits-20261026-r1/activation-final-r4/activation-and-registration.json')
        text=text.replace('tracking-edits-20261026-r1/kit-r1/verification.json','tracking-edits-20261026-r1/kit-r2/verification.json')
        if name.startswith('README'):
            lines=text.splitlines()
            for i,line in enumerate(lines):
                if line.startswith('| R194 '):
                    lines[i]=line.replace(' | [Evidence]', '; final-r4 fixes wheel metadata only, 220 executable files and all resource bytes equal tested final-r3; [distribution proof](docs/validation/evidence/tracking-edits-20261026-r1/distribution-r1/verification.json) | [Evidence]')
            text='\n'.join(lines)+'\n'
        path.write_text(text,encoding='utf8',newline='\n')
    note='''
## 最终发行元数据 / Final distribution metadata

功能回归、C37 和独立队列的实际执行目录是 **final-r3**。后续打包检查发现其 CLI 为
0.1.27，wheel 的发行元数据仍为 0.1.26，r28 发布门禁拒绝了这个候选；未发布该错误包。
最终 **final-r4** 修正 wheel 元数据为 0.1.27，并为构建和 Skill 固定步骤增加版本一致性检查。
220 个可执行 Python 文件、全部产品资源字节及七个依赖 wheel 与 final-r3 相同。
最终已注册入口另外执行版本/能力/Schema/校验及实际预览，RGBA64 解码与原预览相同。

Functional tests, C37 and the independent queue actually ran on **final-r3**.
Final **final-r4** corrects distribution metadata, with identical executable and
resource payloads and seven identical dependency wheels. The final registered
entry separately checks version/capabilities/schema/validation and decodes a new
preview. Earlier failed kit metadata and the incomplete kit-r1 attempt remain
excluded; final r28 acceptance is **kit-r2**. This is a metadata repack, not another
full regression or model inference claim.

'''
    for name,prefix in [('docs/releases/CLI_0.1.27_LOCAL.md','../validation/'),
        ('docs/validation/跟踪剪辑实测_2026-10-26.md',''),('docs/product/TRACKING_EDITS.md','../validation/')]:
        path=ROOT/name;text=path.read_text('utf8')
        assert '## 最终发行元数据 / Final distribution metadata' not in text
        text+=note+'[Distribution and actual final-entry proof]('+prefix+'evidence/tracking-edits-20261026-r1/distribution-r1/verification.json).\n'
        path.write_text(text,encoding='utf8',newline='\n')
    print('Current delivery is final-r4; actual final-r3 functional execution paths retained.')

if __name__=='__main__':main()
