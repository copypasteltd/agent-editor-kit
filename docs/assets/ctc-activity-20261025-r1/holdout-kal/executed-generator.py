"""New KAL voice/words held out from the v1 diagnosis and v2 design."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import shutil
import subprocess
import wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/assets/ctc-activity-20261025-r1/holdout-kal'
WORDS='MOTION SIGNAL EDITING TIMELINE SAVES CLEAN FINAL OUTPUT'.split()
GAPS=[2240,5440,1440,4000,6560,2560,4480,1920]


def main():
    assert not OUT.exists()
    OUT.mkdir(parents=True)
    def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    pieces=[];words=[];sources=[];cursor=0
    for word,gap in zip(WORDS,GAPS):
        path=OUT/(word.lower()+'-kal-raw.wav')
        command=[shutil.which('ffmpeg'),'-v','error','-nostdin','-n','-f','lavfi','-i',
                 'flite=text='+word.lower()+':voice=kal','-ar','16000','-ac','1','-c:a','pcm_s16le',str(path)]
        subprocess.run(command,capture_output=True,check=True,timeout=60)
        with wave.open(str(path),'rb') as stream:
            signal=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2')
        active=np.flatnonzero(np.abs(signal.astype(np.int32))>=32)
        assert len(active)
        start,end=int(active[0]),int(active[-1])+1
        pieces.extend([np.zeros(gap,dtype='<i2'),signal[start:end]])
        cursor+=gap
        words.append(dict(word=word,start_sample=cursor,end_sample=cursor+end-start));cursor+=end-start
        sources.append(dict(word=word,path=path.name,sha256=sha(path),trim_start=start,trim_end=end,command=command))
    pieces.append(np.zeros(3520,dtype='<i2'))
    signal=np.concatenate(pieces)
    def write(name,pcm):
        with wave.open(str(OUT/name),'wb') as stream:
            stream.setparams((1,2,16000,0,'NONE','not compressed'));stream.writeframes(pcm.astype('<i2').tobytes())
    write('input.wav',signal)
    (OUT/'transcript.txt').write_text(' '.join(WORDS),encoding='utf-8')
    record=dict(format='ctc-activity-authored-blocks-v1',created_at_utc=datetime.now(timezone.utc).isoformat(),
        frozen_before_v2_candidate_execution=True,voice='kal',sample_rate=16000,samples=len(signal),words=words,
        gaps_before_words_samples=GAPS,trailing_gap_samples=3520,original_word_sources=sources,
        reference='authored abs>=32 trimmed word blocks, not natural phonetic annotations',boundary_error_seconds_max=2/30,
        contract_sha256=sha(ROOT/'docs/specs/CTC声学活动边界契约_20261025.md'),generator_sha256=sha(Path(__file__)),
        rights=dict(authored_text_and_placement='CC0-1.0',speech='FFmpeg Flite KAL; retain original CMU attribution and license; not blanket CC0'),
        files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in OUT.iterdir()})
    (OUT/'input-provenance.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    (OUT/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(words=len(WORDS),samples=len(signal),no_candidate_executed=True)))


if __name__=='__main__':main()
