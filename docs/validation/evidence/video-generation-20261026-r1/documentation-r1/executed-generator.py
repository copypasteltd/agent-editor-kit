"""Publish current trilingual workflow without deleting historical evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/video-generation-20261026-r1'
BASELINE='d5d8e7f8915b23f1e67103f44469bccd0dd0e1de'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def load(path):return json.loads(Path(path).read_bytes())
def write(path,text):(ROOT/path).write_text(text,encoding='utf8',newline='\n')
def rows(text,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}
def previous(path):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','show',BASELINE+':'+path],cwd=ROOT).decode('utf-8-sig')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);parser.add_argument('--case-run',default='r1');a=parser.parse_args()
    assert a.run.replace('-','').isalnum() and a.case_run.replace('-','').isalnum()
    out=BASE/('documentation-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    installation=load(BASE/'installation-final-r1/verification.json');case=load(BASE/('case-'+a.case_run)/'verification.json')
    assert installation['cli_version']=='0.1.33' and installation['source_file_count']==227
    assert case['status']=='passed_actual_four_mode_cuda_transport_and_editable_package' and len(case['modes'])==4
    assert all(c['ok'] for c in case['checks']) and not case['synthetic_worker']
    rendered=load(BASE/'render-roundtrip-r1/verification.json')
    assert rendered['status']=='passed' and rendered['registered_skill']
    assert rendered['decoded_equal_frames']==170 and rendered['source_and_imported_pixels_equal']
    tests={}
    for key,path in [('generation','generation-installed-r1'),('conversion','conversion-installed-r1'),('legacy','legacy-installed-r1'),('vace_source','vace-source-r1')]:
        value=load(BASE/path/'verification.json');assert value['status']=='passed'
        tests[key]=value['tests']
    assert tests==dict(generation=14,conversion=83,legacy=192,vace_source=160)
    descriptions={
        '':'新增本地 GPU 文生、图生、尾帧与首尾帧视频生成：显式条件、原文提示词、seed/采样和窗口参数，产出无声视频资产，并可直接作为普通可编辑片段入轨。复用现有 VACE 原生内核、GPU 内存准入、权利依赖与事务恢复。',
        '.zh-TW':'新增本地 GPU 文生、圖生、尾幀與首尾幀影片生成：明確條件、原文提示詞、seed/取樣與視窗參數，產出無聲影片資產，並可直接作為普通可編輯片段入軌。重用既有 VACE 原生核心、GPU 記憶體准入、權利依賴與交易恢復。',
        '.en':'Local GPU generation now accepts text, a first image, a last image or a first/last pair. Explicit prompt, seed/sampling and bounded windows produce silent video assets and ordinary editable timeline clips, reusing the native VACE engine, GPU admission, rights dependencies and transactional recovery.'}
    boundaries={
        '':'四种模式均有真实 CUDA 输出、全部17帧解码与工程包往返记录；每个端点另做解码哈希核验。保留端点不证明模型运动/身份质量；模型与生成内容权利、自然质量、完整播放及完整剪映等价仍未验收。模型成片/GIF/工程包保留本机；下图仅是自行绘制的 CC0 条件图，不是生成输出。',
        '.zh-TW':'四種模式皆有真實 CUDA 輸出、全部17幀解碼與工程包往返記錄；每個端點另做解碼雜湊核驗。端點保留不能證明模型運動/身分品質；模型與生成內容權利、自然品質、完整播放及完整剪映等價仍未驗收。模型成片/GIF/工程包保留本機；下圖僅為自行繪製的 CC0 條件圖，並非生成輸出。',
        '.en':'All four modes have real CUDA outputs, complete 17-frame decoding and project-package roundtrips; each supplied endpoint has an independent decoded hash check. Retained endpoints do not establish generated motion/identity quality. Model/output rights, natural quality, continuous playback and full CapCut equivalence remain unaccepted. Actual movies/GIFs/packages stay local; the image below shows original CC0 conditions only.'}
    entries={
        '':[
            'CLI0.1.33/local.31：227产品文件/schema与源码一致；安装版生成14、转换83、旧流程192通过；另有源码VACE/修复/抠像/恢复160通过，分组不合并计数。',
            'C43四种模式各实际CUDA推理1个17帧窗口，全部68个RGBA帧独立解码；输入形状、provider、GPU准入、采样与冷启动耗时留证；合成协议worker不计真实生成。',
            '首/尾/双端点共4个条件帧独立解码摘要一致；可编辑入轨、权利/配方工程包往返；已注册Skill实际渲染原/迁移工程，30FPS的170帧逐帧解码摘要相同；片段组重用会重绑图像ID/配方摘要。',
            '模型和输出权利保持unverified/internal，rights.check预期拒绝；实际MP4/GIF和可编辑工程包保留本机，公开目录只含自行绘制CC0条件图，不以输入图冒充生成结果。',
            '统一Skill新增按需生成工作流，维持1入口/17模块；74 Skill文件和r34 kit114文件；独立注册/安装版核验；模型包校验期限可配置，强制超时保留此前两份配置，无源码回退。',
            '三语README及61功能/20服务/75声明、使用流程、案例/模型限制和安装包同步；229历史R记录与38项原关闭条件保留，开发失败独立留证。'],
        '.zh-TW':[
            'CLI0.1.33/local.31：227產品檔案/schema與原始碼一致；安裝版生成14、轉換83、舊流程192通過；另有原始碼VACE/修復/摳像/恢復160通過，分組分別記錄。',
            'C43四模式各實際CUDA推理1個17幀視窗，全部68個RGBA幀獨立解碼；輸入形狀、provider、GPU准入、取樣與冷啟動耗時留證；合成協議worker不計真實生成。',
            '首/尾/雙端點共4個條件幀獨立解碼雜湊一致；可編輯入軌、權利/配方工程包往返；已註冊Skill實際渲染原/遷移工程，30FPS的170幀解碼雜湊逐幀相同；片段組重用重綁圖像ID/配方雜湊。',
            '模型與輸出權利維持unverified/internal，rights.check預期拒絕；實際MP4/GIF與可編輯工程包保留本機，公開目錄僅含自行繪製CC0條件圖，不以輸入圖冒充生成結果。',
            '統一Skill新增按需生成流程，維持1入口/17模組；74 Skill檔案與r34 kit114檔案；獨立註冊/安裝版核驗；模型包校驗期限可設定，強制逾時保留先前兩份設定，無原始碼回退。',
            '三語README及61功能/20服務/75宣告、流程、案例/模型限制與安裝包同步；229歷史R列及38原關閉條件保留，開發失敗獨立留證。'],
        '.en':[
            'CLI0.1.33/local.31:227 product files/schema equal source; installed groups14 generation,83 conversion and192 legacy pass. Source VACE/repair/matting/recovery160 also passes; groups are not combined.',
            'C43:one real17-frame CUDA window per mode; all68 RGBA frames independently decoded. Input shapes,provider,GPU admission,sampling and cold costs retained. Synthetic protocol workers are excluded from real generation.',
            'Four supplied endpoint frames independently match decoded hashes. Editable clips,rights and recipes survive packaging; the registered Skill renders original/imported projects with170 matching decoded frames at30FPS. Fragment reuse rebinds image IDs and recipe digests.',
            'Model/output rights remain unverified/internal and rights.check rejects as expected. Actual MP4/GIF/editable package stay local; public assets contain original CC0 conditions only.',
            'Unified Skill adds generation: one entry,17 modules,74 Skill files and114-file r34 kit. Isolated registration uses the installed CLI without source fallback. Pack verification has a configurable deadline; a forced timeout preserves both prior configuration files.',
            'Full trilingual READMEs,61 functions/20 services/75 declarations,workflow,cases/model limits and bundle updated;229 historical R rows and38 original closure cells retained. Failed development attempts recorded separately.']}
    targets=['installation-final-r1/verification.json',f'case-{a.case_run}/verification.json','render-roundtrip-r1/verification.json',f'case-{a.case_run}/rights-expected-reject.stdout.json','kit-r2/verification.json','development-attempts-r1/verification.json']
    f61={
        '':'| F61 | 本地GPU视频生成 | 文生、图生、尾帧/首尾帧；原文提示/采样、真实模型窗口、可编辑入轨、端点核验、可移植配方和受管恢复。 | `media adapter; media generate` | 已有原生VACE/CUDA依赖；无声8bit SDR；条件端点合成保留；自然质量/生成权利/全部剪映AI待验收。 |',
        '.zh-TW':'| F61 | 本地GPU影片生成 | 文生、圖生、尾幀/首尾幀；原文提示/取樣、真實模型視窗、可編輯入軌、端點核驗、可移植配方與受管恢復。 | `media adapter; media generate` | 既有原生VACE/CUDA依賴；無聲8bit SDR；條件端點合成保留；自然品質/生成權利/完整剪映AI待驗收。 |',
        '.en':'| F61 | Local GPU video generation | Text,image,last/first-last conditions; prompt/sampling,real model windows,editable clips,endpoint proofs,portable recipes and managed recovery. | `media adapter; media generate` | Existing native VACE/CUDA required;silent8bit SDR;known endpoints retained;natural quality,output rights and complete CapCut AI unaccepted. |'}
    for suffix,name in [('','README.md'),('.zh-TW','README.zh-TW.md'),('.en','README.en.md')]:
        text=(ROOT/name).read_text('utf-8-sig');old=rows(previous(name),'R');assert len(old)==229
        text=re.sub(r'<!-- video-generation-in-progress -->.*?<!-- /video-generation-in-progress -->\s*','',text,count=1,flags=re.S)
        assert len(rows(text,'R'))==229 and 'video-generation-current' not in text
        text=text.replace('**CLI0.1.32 / alpha.4-local.30 / r33 kit','**Historical / 历史 / 歷史：CLI0.1.32 / alpha.4-local.30 / r33 kit',1)
        block='<!-- video-generation-current -->\n\n**CLI0.1.33 / alpha.4-local.31 / r34 kit · 1 Skill / 17 modules.**\n\n'+descriptions[suffix]+'\n\n'
        block+='```powershell\n& $avk media generate --project $avkProject --adapter-id $vaceAdapterId `\n  --asset-id generated-shot-01 --mode first-last-to-video `\n  --first-asset-id $firstAssetId --last-asset-id $lastAssetId `\n  --width 256 --height 144 --frames 17 --fps 12 --image-fit contain `\n  --prompt $reviewedPrompt --inference-steps 18 --window-frames 17 `\n  --window-overlap 4 --apply --track-id track_video_1\n```\n\n'
        block+='[Workflow](docs/product/VIDEO_GENERATION.md) · [C43](docs/product/CASES.md#c43-video-generation) · [Install](docs/releases/CLI_0.1.33_LOCAL.md) · [Evidence](docs/validation/本地GPU视频生成实测_2026-10-26.md)\n\n'
        block+=boundaries[suffix]+'\n\n![Original CC0 first/last conditions only](docs/assets/video-generation-20261026-'+a.case_run+'/conditions.png)\n\n<!-- /video-generation-current -->\n\n'
        text=text.replace('<!-- tracking-bake-current -->',block+'<!-- tracking-bake-current -->',1)
        last=re.search(r'^\| F60\s*\|.*$',text,re.M);assert last;text=text[:last.end()]+'\n'+f61[suffix]+text[last.end():]
        last=re.search(r'^\| R229\s*\|.*$',text,re.M);assert last
        additions=['| R'+str(230+i)+' | 2026-10-26 local GPU generation | '+value+' | [Evidence](docs/validation/evidence/video-generation-20261026-r1/'+target+') |' for i,(value,target) in enumerate(zip(entries[suffix],targets))]
        text=text[:last.end()]+'\n'+'\n'.join(additions)+text[last.end():]
        text='\n'.join(line.replace('local.30/final-r3/installed','local.31/final-r1/installed').replace('CLI 0.1.32','CLI 0.1.33')
            if not line.startswith('| R') and 'local.30/final-r3/installed' in line else line for line in text.splitlines())+'\n'
        assert len(rows(text,'R'))==235 and all(rows(text,'R')[k]==v for k,v in old.items());write(name,text)
        for path in ('docs/product/SKILLS'+suffix+'.md','docs/skills/UNIFIED_SKILL'+suffix+'.md'):
            link='VIDEO_GENERATION.md' if '/product/' in path else '../product/VIDEO_GENERATION.md'
            current='<!-- community-current -->\n\n**CLI0.1.33 / alpha.4-local.31 / r34 kit · 1 Skill / 17 modules / 74 files.**\n\n'+descriptions[suffix]+'\n\n[Video generation workflow]('+link+')\n\n<!-- /community-current -->'
            write(path,re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',lambda _:current,(ROOT/path).read_text('utf8'),count=1,flags=re.S))
    release='# CLI0.1.33 · local GPU generation · local.31\n\n唯一 `$agent-ffmpeg-local-editor` / one Skill with17 internal modules. Public alpha.3 downloads remain unchanged.\n\n'
    release+='| Item | Verified value |\n|---|---|\n'
    for key,value in [('Runtime','v0.1.0-alpha.4-local.31/final-r1/installed'),('ZIP',installation['archive']),('Bytes',installation['archive_bytes']),('SHA256',installation['archive_sha256']),('Manifest SHA256',installation['manifest_sha256']),('CLI/wheel','0.1.33'),('Product','227 Python files/schema equal source'),('Skill','1 entry/17 modules/74 files;r34 kit114 files')]:release+='| '+key+' | `'+str(value)+'` |\n'
    release+='\n'+descriptions['']+'\n\n'+boundaries['']+'\n\n[Workflow](../product/VIDEO_GENERATION.md) · [Installation](../product/COMMUNITY_LOCAL_DELIVERY.md) · [Actual evidence](../validation/本地GPU视频生成实测_2026-10-26.md) · [r34 kit](../skills/agent-editor-kit-community-unified-skill-r34.zip) · [Kit digest](../skills/community-unified-skill-package-0.1.33-r34.json).\n'
    release+='\nModel-pack activation now uses a configurable per-pack deadline: default600 seconds, range1–3600 via `--verify-timeout-seconds`. Full verification remains mandatory. The independent kit check forces a one-second timeout and confirms that both prior runtime configuration files remain byte-identical. Initial180-second failure and the unaccepted candidate archive are retained in development evidence.\n'
    write('docs/releases/CLI_0.1.33_LOCAL.md',release)
    doc='# 本地GPU视频生成实测 · 2026-10-26\n\nCLI0.1.33/local.31/r34；原生Windows，已有本地VACE1.3B模型，没有虚拟化或模型下载。\n\n'+boundaries['']+'\n\n'
    doc+='| Scope | Evidence |\n|---|---|\n'
    for title,path in [('Install','installation-final-r1/verification.json'),('Actual four modes',f'case-{a.case_run}/verification.json'),('Installed generation14','generation-installed-r1/verification.json'),('Installed conversion83','conversion-installed-r1/verification.json'),('Installed legacy192','legacy-installed-r1/verification.json'),('Source VACE160','vace-source-r1/verification.json'),('Activation','activation-final-r1/activation-and-registration.json'),('Fresh kit','kit-r2/verification.json'),('Development attempts','development-attempts-r1/verification.json')]:doc+='| '+title+' | [Record](evidence/video-generation-20261026-r1/'+path+') |\n'
    for title,path in [('Actual registered Skill render and imported render','render-roundtrip-r1/verification.json'),('MP4/GIF timing and six packaged assets','media-inspection-r1/verification.json'),('Static frame review only','static-review-r1.json')]:doc+='| '+title+' | [Record](evidence/video-generation-20261026-r1/'+path+') |\n'
    doc+='\nEach actual mode:256×144,17 frames,12 FPS,18 steps,17-frame window/4 overlap,one real CUDA VACE window. Endpoint checks:0/1/1/2. All68 raw RGBA frames independently match worker hashes. Small controlled conditions do not certify natural footage, prompt adherence or long-window continuity.\n\n'
    doc+='## Actual local outputs and measured cost\n\n| Mode | Complete CLI seconds | Generation phase seconds | Model window seconds | Local MP4 / GIF | SHA256 |\n|---|---:|---:|---:|---|---|\n'
    for row in case['modes']:
        call=next(call for call in case['calls'] if call['name']==row['mode']+'-actual')
        doc+='| '+row['mode']+' | '+str(round(call['seconds'],3))+' | '+str(round(row['elapsed_seconds'],3))+' | '+str(round(sum(row['model_execution']['window_seconds']),3))+' | `'+row['preview']+'` / `'+row['gif']+'` | `'+row['output_sha256']+'` |\n'
    doc+='\nThese are measured cold command executions, including repeated weight verification/loading. The model-window timing alone is not end-to-end latency. No persistent model host or general throughput acceptance is included.\n'
    doc+='\nActual model outputs remain local pending publication rights. Rights gate rejection is retained. Frame decoding,static inspection,continuous playback and human review are separate. Full transformer forward counts are not inferred from four pipeline-window calls.\n'
    doc+='\n## Editable delivery roundtrip\n\nThe registered local Skill renders all four clips in the original project and independently renders the imported project. Both outputs are256×144,30FPS,170 frames over17/3 seconds; every decoded RGBA frame matches between the two renders. No new model inference is involved. Source generation remains17 frames per clip at12FPS; the authored project display clock is30FPS. This is a decoded-pixel delivery check, not natural-quality or listening acceptance.\n\n'
    for row in rendered['outputs']:doc+='- Local rendered movie: `'+row['path']+'`, SHA256 `'+row['sha256']+'`.\n'
    doc+='- Local combined GIF: `'+rendered['gif']+'`, '+str(rendered['gif_frames'])+' encoded GIF frames, '+str(rendered['gif_duration_ms'])+'ms, SHA256 `'+rendered['gif_sha256']+'`. GIF delays are quantized to10ms.\n'
    write('docs/validation/本地GPU视频生成实测_2026-10-26.md',doc)
    example='\n<a id="c43-video-generation"></a>\n\n## C43：本地GPU四模式生成 / Four-mode local GPU generation\n\n'+descriptions['']+'\n\n'+boundaries['']+'\n\n'
    example+='[Actual responses/paths/hashes](../validation/本地GPU视频生成实测_2026-10-26.md) · [Workflow](VIDEO_GENERATION.md) · [Reproduction script](../../scripts/run_video_generation_case_20261026.py) · [CC0 source](../assets/video-generation-20261026-'+a.case_run+'/SOURCE.txt).\n\n![CC0 conditions only](../assets/video-generation-20261026-'+a.case_run+'/conditions.png)\n'
    write('docs/product/CASES.md',(ROOT/'docs/product/CASES.md').read_text('utf8')+example)
    path='docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=(ROOT/path).read_text('utf8');old=load(ROOT/'docs/validation/evidence/tracking-bake-20261026-r1/installation-final-r3/verification.json')
    footer=re.search(r'^CLI0\.1\.32/local\.30/r33：.*$',text,re.M)
    if footer:text=text[:footer.start()]+'GENERATION_PREVIOUS_FOOTER'+text[footer.end():]
    for before,after in [('local.30/final-r3/installed','local.31/final-r1/installed'),('local.30/candidate-r3/bundle.zip','local.31/candidate-r1/bundle.zip'),('CLI 0.1.32','CLI 0.1.33'),('alpha.4-local.30','alpha.4-local.31'),('r33.zip','r34.zip'),('0.1.32-r33.json','0.1.33-r34.json'),(old['archive_sha256'],installation['archive_sha256']),(old['manifest_sha256'],installation['manifest_sha256'])]:text=text.replace(before,after)
    if footer:text=text.replace('GENERATION_PREVIOUS_FOOTER','Historical / 历史：'+footer[0])
    footer_current='CLI0.1.33/local.31/r34：[GPU生成流程](VIDEO_GENERATION.md) · [版本/摘要](../releases/CLI_0.1.33_LOCAL.md)。VACE大权重与已有原生Torch/Diffusers运行时独立登记，不包含在四个配音/翻译模型包中。'
    if footer_current not in text:text+='\n'+footer_current+'\n'
    write(path,text)
    path='docs/README.md';text=(ROOT/path).read_text('utf8').replace('Current local / 当前本地 / 目前本地：**CLI0.1.32','Historical / 历史 / 歷史：**CLI0.1.32',1)
    write(path,text.replace('\n','\n\nCurrent local / 当前本地 / 目前本地：**CLI0.1.33 / local.31 / r34 kit** · [GPU generation](product/VIDEO_GENERATION.md) · [Install](releases/CLI_0.1.33_LOCAL.md) · [C43](product/CASES.md#c43-video-generation).\n',1))
    for path in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md'):
        text=(ROOT/path).read_text('utf8').replace('当前本地 **CLI0.1.32','此前本地 **CLI0.1.32',1);first=text.index('\n')+1
        text=text[:first]+'\n当前本地 **CLI0.1.33 / alpha.4-local.31 / r34 kit**：[本地GPU四模式生成](VIDEO_GENERATION.md)、可编辑入轨/配方迁移/受管恢复及真实模型结果已留证；自然质量、模型与输出权利及38项原关闭条件继续保留。\n'+text[first:];write(path,text)
    path='docs/product/GOAL_GAPS_20261025.md';text=(ROOT/path).read_text('utf8');match=re.search(r'^\| G23\s*\|.*$',text,re.M);assert match
    cells=match[0].split('|');cells[3]=' CLI0.1.33统一media.generate已接通文生/图生/尾帧/首尾帧，GPU真实4模式、可编辑入轨、配方迁移/端点核验/恢复；[C43](CASES.md#c43-video-generation)留证 '
    cells[4]=' 依赖显式已有原生VACE/CUDA与大权重；自然提示遵循/身份/运动/窗口连续性、冷读取成本和模型/输出发布权利未验收；首尾保留不代替生成质量 '
    text=text[:match.start()]+'|'.join(cells)+text[match.end():]
    match=re.search(r'^\| G38\s*\|.*$',text,re.M);cells=match[0].split('|');cells[3]=cells[3].replace('local.30-final-r3/CLI0.1.32/r33','local.31-final-r1/CLI0.1.33/r34');text=text[:match.start()]+'|'.join(cells)+text[match.end():];write(path,text)
    path='docs/product/IMPLEMENTATION_PLAN_20261025.md';text=(ROOT/path).read_text('utf8');
    for key,new in [('W04','CLI0.1.33本地GPU四模式生成、真实模型/可编辑入轨/迁移恢复已接通；自然质量、生成权利及其他高级AI条件保留'),('W09','当前CLI0.1.33/local.31-final-r1/r34本地安装并加载；完整三语流程/功能/服务/Skill与实际证据同步，公开旧发行保持')]:
        match=re.search(r'^\| '+key+r'[^\n]+$',text,re.M);assert match;cells=match[0].split('|');cells[-2]=' '+new+' ';text=text[:match.start()]+'|'.join(cells)+text[match.end():]
    write(path,text)
    (out/'verification.json').write_text(json.dumps(dict(status='documented',historical_rows_preserved=229,current_rows=235,function_rows=61,service_rows=20,skill_modules=17,tests=tests),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(status='documented',historical_R_rows=229,current_R_rows=235),ensure_ascii=False))


if __name__=='__main__':main()
