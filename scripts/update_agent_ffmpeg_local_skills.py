"""Update the existing 17 local Skills to the reviewed alpha.3 installation."""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
TAG="v0.1.0-alpha.3"


def main():
    config=json.loads((ROOT/"local/agent-ffmpeg/runtime.json").read_bytes())
    installed=Path(config["installed_directory"])
    receipt=json.loads((installed/"receipt.json").read_bytes())
    if config["release"]!=TAG or receipt["manifest_sha256"]!=config["manifest_sha256"]:
        raise ValueError("Install and activate the reviewed alpha.3 build first")
    manifest_path=ROOT/"agent-ffmpeg-local-install-manifest.json"
    manifest=json.loads(manifest_path.read_bytes())
    if manifest.get('registration_mode') == 'single':
        raise ValueError('The split updater is historical. Maintain the unified Skill and refresh its reviewed file inventory before packaging.')
    editor=ROOT/"skills/agent-ffmpeg-local-editor"
    launcher=editor/"scripts/run.py"
    text=launcher.read_text("utf-8")
    text=re.sub(r"^MANIFEST = .*$", "MANIFEST = "+repr(config["manifest_sha256"]), text, flags=re.M)
    text=re.sub(r"^RELEASE = .*$", "RELEASE = "+repr(TAG), text, flags=re.M)
    launcher.write_text(text,encoding="utf-8",newline="\n")
    descriptions={
        "agent-ffmpeg-local-editor":"Edit local advertising videos with the installed agent editor kit CLI. Search 500 named looks, present actual filter previews and client comparison boards, then edit, render and deliver local projects.",
        "agent-ffmpeg-local-timeline":"Compose local video timelines, keyframes, camera presets, transitions, masks and speed curves. Apply 500 named built-in color looks to explicit clips or global adjustments using the installed CLI.",
        "agent-ffmpeg-local-quality":"Review locally rendered video, pixels, masks, audio, scopes and manifests. Compare the 500 offline color looks using measured gray, skin and RGB profiles, then verify actual rendered output.",
        "agent-ffmpeg-local-rights-ledger":"Record source, license, creator and local evidence for media, fonts, templates, LUTs and models. Inspect per-resource MIT, CC0 or CC-BY-SA obligations for the 500 bundled looks and project-local evidence."
    }
    for row in manifest["skills"]:
        path=ROOT/"skills"/row["name"]/"SKILL.md"
        text=path.read_text("utf-8").replace("v0.1.0-alpha.1",TAG).replace("v0.1.0-alpha.2",TAG)
        text=text.replace('Agent Video Kit','agent editor kit')
        if row["name"] in descriptions:
            text=re.sub(r"^description: .*$", "description: "+json.dumps(descriptions[row["name"]]), text, flags=re.M)
            marker="## Offline look presets"
            section=(marker+"\n\nUse `look list`, `look inspect`, `look preview` and `look apply` for 500 named offline color looks. "
                     "Inspect measured descriptions, original variants and the per-resource MIT, CC0 or CC-BY-SA license. "
                     "Read [the look workflow](../agent-ffmpeg-local-editor/references/looks.md) before choosing target, strength or delivery. "
                     "These are creative SDR looks; preview suggestions are not natural-footage acceptance.\n\n"
                     "For human-facing filter selection, read [client-look-selection.md](../agent-ffmpeg-local-editor/references/client-look-selection.md). "
                     "It maps all 500 real N002 samples to stable IDs and exports a small labeled original/candidate board with `scripts/look_gallery.py`. "
                     "Show actual images, number/name/ID, strength and license; record the chosen ID/strength/scope, then trial the target media before applying. "
                     "The samples are strength 1.0; image rights are separate from LUT rights. The runtime ZIP alone does not include the checkout gallery.\n")
            if marker in text:text=text.split(marker,1)[0].rstrip()+"\n\n"+section
            else:text+='\n'+section
        path.write_text(text,encoding="utf-8",newline="\n")
        row["skill_md_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
        ui=path.parent/'agents/openai.yaml'
        ui.write_text(ui.read_text('utf-8').replace('Agent Video Kit','agent editor kit'),encoding='utf-8',newline='\n')
    runtime=editor/"references/runtime.md"
    text=runtime.read_text("utf-8").replace("v0.1.0-alpha.1",TAG).replace("v0.1.0-alpha.2",TAG).replace("scripts/install_agent_ffmpeg_local.py", "scripts/install_look500_release.py --activate").replace("scripts/install_look_release.py", "scripts/install_look500_release.py")
    text=text.replace('## 100 offline looks','## 500 offline looks')
    text=text.replace('the pinned release ZIP is in','the pinned release ZIP parts are in')
    if "## 500 offline looks" not in text:
        text += "\n## 500 offline looks\n\nRead [looks.md](looks.md). `look apply` copies per-resource LUT/license/provenance into the project. Built-in evidence is relative; unrelated media evidence needs separate review after relocation.\n"
    runtime.write_text(text,encoding="utf-8",newline="\n")
    manifest.update(release=TAG,manifest_sha256=config["manifest_sha256"],look_catalog_version="2.0.0",look_count=500)
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps({"ok":True,"release":TAG,"updated_skills":len(manifest["skills"]),"look_presets":500}))


if __name__=="__main__":main()
