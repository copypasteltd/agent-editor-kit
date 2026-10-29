"""Describe the independently byte-verified candidate without promoting it."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'

def main():
    r=json.loads((BASE/'installation-candidate-r1/verification.json').read_bytes())
    assert r['status']=='installed-and-byte-verified' and r['cli_version']=='0.1.60'
    assert r['source_file_count']==283 and r['exact_product_payload']['payload_files']==1707
    assert hashlib.sha256(Path(r['archive']).read_bytes()).hexdigest()==r['archive_sha256']
    records={
      'README.md':'| R473 | CLI60/local58独立原生候选 | 已从ZIP解包安装，1707载荷／283应用模块／8原生资源逐字节核对，版本和能力查询成功；[包位置、摘要与使用流程](docs/validation/CLI60独立安装交付_2026-10-29.md)。安装功能回归进行中，正式Skill仍59 |',
      'README.en.md':'| R473 | CLI60/local58 native candidate | Independently extracted/installed ZIP;1707 payloads,283 application modules and8 native resources byte-verified;version/capabilities succeeded;[local package,hashes and workflow](docs/validation/CLI60独立安装交付_2026-10-29.md).Installed functional checks ongoing,registered Skill remains59 |',
      'README.zh-TW.md':'| R473 | CLI60/local58獨立原生候選 | 已從ZIP解包安裝，1707載荷／283應用模組／8原生資源逐位元組核對，版本與能力查詢成功；[包位置、摘要與使用流程](docs/validation/CLI60独立安装交付_2026-10-29.md)。安裝功能回歸進行中，正式Skill仍59 |'}
    for name,row in records.items():
        p=ROOT/name;lines=p.read_text(encoding='utf-8').splitlines()
        history=[x for x in lines if re.match(r'^\| R\d+ \|',x)];assert len(history)==472
        i=next(i for i,x in enumerate(lines) if x.startswith('| R472 |'));lines.insert(i+1,row)
        text='\n'.join(lines)+'\n';assert all(x in text for x in history);p.write_text(text,encoding='utf-8')
    p=ROOT/'docs/product/MUSIC_LOOP.md';text=p.read_text(encoding='utf-8')
    text=text.replace('安装版验收与 Skill 切换另行执行，旧发布包不覆盖。',
        'CLI60/local58独立候选包已构建并安装，功能回归与Skill切换另行执行；[候选包位置、摘要和使用流程](../validation/CLI60独立安装交付_2026-10-29.md)。旧发布包不覆盖。')
    p.write_text(text,encoding='utf-8')
    p=ROOT/'docs/validation/CLI60循环修复_2026-10-29.md';text=p.read_text(encoding='utf-8')
    text=text.replace('CLI60/local58离线包正在独立构建；正式Skill保持59。',
        'CLI60/local58离线ZIP已独立解包安装并逐字节核对；[候选使用流程](CLI60独立安装交付_2026-10-29.md)。安装功能回归运行中，正式Skill保持59。')
    p.write_text(text,encoding='utf-8')
    out=BASE/'candidate-docs-r1';out.mkdir(exist_ok=False)
    (out/'verification.json').write_text(json.dumps(dict(status='passed',preserved_R_rows=472,
        current_R_rows=473,cli_candidate='0.1.60',formal_skill='0.1.59',
        candidate_archive_sha256=r['archive_sha256'],activation=False),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='passed',current_R_rows=473)),flush=True)

if __name__=='__main__':main()
