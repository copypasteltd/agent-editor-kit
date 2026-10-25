"""Keep the observed semantic upgrade rejection visible beside successful new work."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    for name, note in (
        ('README.md', '升级注意：旧语义工程固定绑定旧安装目录，直接在新版本复用会返回 `SEMANTIC_ADAPTER_INTEGRITY_FAILED`。保留旧版本可复现；新运行时需明确重新登记/建立相应索引与校准，不能静默改写旧 pin。'),
        ('README.zh-TW.md', '升級注意：舊語義專案固定綁定舊安裝目錄，直接在新版本復用會返回 `SEMANTIC_ADAPTER_INTEGRITY_FAILED`。保留舊版本可重現；新執行時需明確重新登記/建立對應索引與校準，不可靜默改寫舊 pin。'),
        ('README.en.md', 'Upgrade: old semantic projects pin their previous installation directory. Reusing them directly with the new runtime returns `SEMANTIC_ADAPTER_INTEGRITY_FAILED`. Retain the old runtime for reproduction; explicitly register/rebuild the relevant index and calibration for the new runtime. Old pins are preserved.'),
    ):
        path = ROOT/name; text = path.read_text('utf8')
        text = text.replace('ad-storyboard-20261025-r1/kit-r1/verification.json', 'ad-storyboard-20261025-r1/kit-r2/verification.json')
        text = text.replace('<!-- /ad-storyboard-current -->', note+' [Observed upgrade rejection](docs/validation/evidence/ad-storyboard-20261025-r1/kit-r1/semantic-dry-run.stdout.txt)\n\n<!-- /ad-storyboard-current -->', 1)
        path.write_text(text, encoding='utf8', newline='\n')
    path = ROOT/'docs/validation/可编辑广告分镜与返工实测_2026-10-25.md'
    text = path.read_text('utf8').replace('ad-storyboard-20261025-r1/kit-r1/verification.json', 'ad-storyboard-20261025-r1/kit-r2/verification.json')
    text += '\n独立工具包首轮仍选用了上一版 local.11 语义工程，返回 `SEMANTIC_ADAPTER_INTEGRITY_FAILED / Artifact closure changed`：模型与运行时文件本身未在本批修改，工程中的 implementation 绝对路径绑定的是旧安装目录。未放宽完整性检查、改写旧 SHA 或据此声称当前语义升级已通过。[原始拒绝](evidence/ad-storyboard-20261025-r1/kit-r1/semantic-dry-run.stdout.txt)、[首轮失败](evidence/ad-storyboard-20261025-r1/kit-r1/failure.json)。当前 r13 工具包独立目录改用本批广告工程的实际返工 dry-run/validate/recovery 核验，0 新推理/渲染，元数据/资产保持。旧语义工程应继续由对应旧安装复现；升级需明确新登记与相应索引/校准，完整 G31/G34 升级迁移继续开放。\n'
    path.write_text(text, encoding='utf8', newline='\n')
    path = ROOT/'docs/product/GOAL_GAPS_20261025.md'; text = path.read_text('utf8')
    text = text.replace('当前 0.1.13 / local.11 / r12 再补读取中的超时/取消，下表', '历史 0.1.13 / local.11 / r12 补读取中的超时/取消；当前 0.1.14 / local.12 / r13 补可编辑广告链路。下表', 1)
    text = text.replace('新目录不是新主机；Python/FFmpeg、驱动/CUDA、部分模型环境和升级回滚仍缺干净主机验证', '新目录不是新主机；本批旧语义工程因旧安装路径 pin 拒绝在新版调用，未自动改写。Python/FFmpeg、驱动/CUDA、部分模型环境和升级回滚仍缺干净主机验证', 1)
    for ident, title in [('D03', 'CPU/GPU 经验校准'), ('D04', '另组 60 条与真实 Skill'), ('D05', '原 20 条与 raw'), ('D06', '实际媒体与迁移')]:
        text = text.replace('| '+ident+' | '+title+' |', '| '+ident+' | 历史语义版本：'+title+' |', 1)
    text += '\n本批独立 kit 首次复用旧语义工程发生安装路径 pin 拒绝，[实际失败](../validation/evidence/ad-storyboard-20261025-r1/kit-r1/failure.json)保留。旧版本的语义质量/往返结论不外推成当前新安装的自动升级验收。新 kit 另验广告分镜返工，完整语义升级与 G31/G34 继续开放。\n'
    path.write_text(text, encoding='utf8', newline='\n')


if __name__ == '__main__':
    main()
