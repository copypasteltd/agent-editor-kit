"""Set final receipt references and retain failed media without rewriting history."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
p=ROOT/'scripts/document_speech_enhancement_20261027.py';s=p.read_text('utf8')
for a,b in [('installation-final-r2','installation-final-r3'),('source-enhancement-r5','source-enhancement-r6'),
            ('installed-enhancement-r2','installed-enhancement-r3'),('installed-compat-r2','installed-compat-r3'),
            ('quality-and-cancel-r2','quality-and-cancel-r4'),('final-r2/','final-r3/'),('candidate-r2/','candidate-r3/'),
            ("'source-enhancement-r6',32","'source-enhancement-r6',33"),("'installed-enhancement-r3',32","'installed-enhancement-r3',33"),
            ('32项','33项'),('32項','33項'),('32 source','33 source'),('32 installed','33 installed'),('32源码','33源码'),('32安装','33安装')]:s=s.replace(a,b)
s=s.replace('取消超时及临时响应文件原子替换竞态','取消超时、持久诊断及临时响应文件原子替换竞态')
s=s.replace('取消逾時及暫存回應檔原子替換競態','取消逾時、持久診斷及暫存回應檔原子替換競態')
s=s.replace('real worker,cancel/deadline and atomic receipt removal race','real worker,cancel/deadline,persistent rollback diagnostics and atomic receipt removal race')
s=s.replace('首轮成功测试针对旧冻结字节，不算修复版通过数。','片段首次选择音轨目标被既有视频容器API拒绝，改用正确目标后重绑通过。真实取消发现原validation诊断被事务删除，已接入持久诊断库并增补事务回滚回归；最终安装版重跑英语/中文与公开WAV逐字节相同，再实测取消及诊断读取。首轮成功测试针对旧冻结字节，不算修复版通过数。')
p.write_text(s,encoding='utf8',newline='\n')
public=ROOT/'docs/assets/native-speech-enhancement-20261027-r1'
report=dict(case='C53-retained-incomplete-first-attempt',status='failed-stereo-atomic-receipt-race',human_listening=False,
    original_attempt='docs/validation/evidence/native-speech-enhancement-20261027-r1/case-r1/verification.json',
    files=[dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(public.iterdir()) if p.name!='media-manifest.json' and p.is_file()])
(public/'media-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
public=ROOT/'docs/assets/native-speech-enhancement-20261027-r2'
(BASE/'static-review.json').write_text(json.dumps(dict(status='static-figures-inspected',human_listening=False,continuous_playback=False,
    finding='Labels and actual waveforms/spectra readable; enhanced English has reduced broadband background. Static review cannot establish speech intelligibility or musical quality.',
    files={n:hashlib.sha256((public/n).read_bytes()).hexdigest() for n in ('comparison.png','spectra-and-waveforms.png')}),indent=2)+'\n',encoding='utf8')
p=ROOT/'scripts/publish_speech_enhancement_20261027.py';s=(ROOT/'scripts/publish_interpolation_20261027.py').read_text('utf8')
for a,b in [('r43','r44'),('native-interpolation-kit-build-r1','native-speech-enhancement-kit-build-r1'),('0.1.42','0.1.43'),('130','132')]:s=s.replace(a,b)
p.write_text(s,encoding='utf8',newline='\n')
print(json.dumps(dict(status='final-receipt-references-prepared',source_checks=33,installed_checks=33,compatibility_checks=156,failed_media_inventory=True)))
