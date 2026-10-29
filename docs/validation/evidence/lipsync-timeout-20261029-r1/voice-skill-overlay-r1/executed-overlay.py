"""Prepare a strictly documentation-only Skill overlay from actual103 auditions."""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
VOICE=ROOT/'docs/validation/evidence/voice-auditions-20261029-r1/r2/verification.json'
REFERENCE='references/community-materials.md'
OLD='''`voice list` lists 103 upstream named Kokoro voices. Three voices (`zf_001`,
`zm_009`, `af_maple`) have actual generated auditions; the remaining mappings
are verified but not individually inferred or listened to. Do not invent age,
tone or commercial suitability from IDs. Generate the actual client's text and
show the local WAV before recording their selection.'''
NEW='''`voice list` lists 103 upstream named Kokoro voices. Installed CLI0.1.61
actually generated all 103 auditions (100 Chinese, three English), with one
explicit CUDA initialization per language batch and complete PCM package replay.
CUDA provider loading was verified; per-operator GPU placement was not profiled.
These samples remain internal/unverified and have not passed human listening,
pronunciation, emotional delivery or naturalness acceptance. Do not invent age,
tone or commercial suitability from IDs.

On the development machine, the local selection gallery is under the project
root at `local/agent-ffmpeg/voice-preview61-r2/preview/index.html`; its 103 WAVs
and `voices.json` are separate local outputs, not bundled in the Skill kit.
Show the client candidate WAVs, record their exact `voice_id`, then generate
the actual task text before recording approval. On other machines use
`voice list` and `voice synthesize --project PROJECT --voice VOICE_ID
--input TEXT_FILE --device cuda --asset-id NEW_ID` with explicitly configured
local packs; do not assume this machine's gallery or accept an audition by ID.
For editable subtitle dubbing, provide the original cue IDs in `--voice-map`
JSON `{"cues":{"1":"zf_001"}}`; this is explicit casting, not speaker detection.
Full generated-sample metadata, local preview and reproduction workflow:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/validation/CLI61全音色试听_2026-10-29.md'''


def digest(content):return hashlib.sha256(content).hexdigest()


def prepare(stage,tested_files,proof):
    assert proof['status']=='passed' and proof['voices']==103 and proof['Chinese_voices']==100 and proof['English_voices']==3
    assert proof['actual_CUDA_generations']==103 and proof['total_model_initializations']==2
    assert proof['explicit_local_voice_packs'] and proof['all_full_PCM_package_replay_equal']
    assert not proof['audio_published'] and not proof['human_listening'] and not proof['naturalness_accepted']
    assert proof['rights']=='internal-unverified'
    gallery=Path(proof['local_gallery']).resolve()
    assert gallery.is_relative_to((ROOT/'local/agent-ffmpeg').resolve()) and gallery.is_file()
    records=proof['voice_records'];assert len(records)==103 and len({r['voice_id'] for r in records})==103
    for row in records:
        audio=(gallery.parent/row['preview']).resolve()
        assert audio.is_relative_to(gallery.parent) and digest(audio.read_bytes())==row['WAV_sha256']
        assert row['full_package_PCM_equal'] and row['rights']=='internal-unverified' and not row['human_listening']
    contents={name:(stage/name).read_bytes() for name in tested_files}
    assert len(contents)==93 and {name:digest(data) for name,data in contents.items()}==tested_files
    text=contents[REFERENCE].decode('utf-8');assert text.count(OLD)==1
    contents[REFERENCE]=text.replace(OLD,NEW,1).encode('utf-8')
    registered={name:digest(data) for name,data in contents.items()}
    assert {name for name in registered if registered[name]!=tested_files[name]}=={REFERENCE}
    overlay=dict(kind='documentation-only',changed_paths=[REFERENCE],
                 before_sha256=tested_files[REFERENCE],after_sha256=registered[REFERENCE],
                 tested_other92_files_byte_equal=True,voice_evidence_path=VOICE.relative_to(ROOT).as_posix(),
                 voice_evidence_sha256=digest(VOICE.read_bytes()),actual_voice_samples=103,
                 overlay_helper_sha256=digest(Path(__file__).read_bytes()),
                 human_listening=False,naturalness_accepted=False)
    return contents,registered,overlay


def validate_registered(stage,activation):
    original=stage['candidate_files']
    assert activation['tested_candidate_files']==original
    registered=activation['registered_files'];overlay=activation['documentation_overlay']
    assert len(registered)==len(original)==93 and set(registered)==set(original)
    assert {name for name in registered if registered[name]!=original[name]}=={REFERENCE}
    assert overlay['kind']=='documentation-only' and overlay['changed_paths']==[REFERENCE]
    assert overlay['before_sha256']==original[REFERENCE] and overlay['after_sha256']==registered[REFERENCE]
    assert overlay['actual_voice_samples']==103 and overlay['tested_other92_files_byte_equal']
    assert digest(VOICE.read_bytes())==overlay['voice_evidence_sha256']
    return {**stage,'candidate_files':registered}
