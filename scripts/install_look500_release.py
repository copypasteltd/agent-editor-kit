"""Install alpha.3 from its checked local release ZIP and optionally activate it."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TAG="v0.1.0-alpha.3"


def sha(path):
    with Path(path).open("rb") as handle:return hashlib.file_digest(handle,"sha256").hexdigest()


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--evidence",type=Path,required=True)
    ap.add_argument("--activate",action="store_true",help="Back up the old runtime config and select this installation")
    args=ap.parse_args()
    if os.name!="nt" or sys.prefix!=sys.base_prefix:raise ValueError("Native Windows Python is required")
    evidence=args.evidence.resolve()
    if not evidence.is_relative_to(ROOT/"docs") or evidence.exists():raise ValueError("Use a new owned docs evidence directory")
    artifacts=ROOT/"docs/releases"/TAG/"artifacts"
    archive=ROOT/'product/.runtime/look500-release-20261024/reassembled'/f"agent-editor-kit-{TAG}-cp313-win_amd64.zip"
    expected={line.split("  ",1)[1]:line.split("  ",1)[0] for line in (artifacts/"SHA256SUMS.txt").read_text("ascii").splitlines()}
    for name,digest in expected.items():
        if Path(name).name!=name or sha(artifacts/name)!=digest:raise ValueError('Release artifact hash mismatch: '+name)
    from assemble_look500_release import assemble
    assemble(artifacts,archive)
    parts=json.loads((artifacts/'parts.json').read_bytes())
    if sha(archive)!=parts['sha256']:raise ValueError("Release ZIP SHA-256 mismatch")
    version_path=artifacts/"version.json"
    if sha(version_path)!=expected["version.json"]:raise ValueError("Release version SHA-256 mismatch")
    version=json.loads(version_path.read_bytes())
    target=ROOT/"local/agent-ffmpeg"/TAG
    if target.exists():raise ValueError("Existing installation is preserved")
    with zipfile.ZipFile(archive) as zipped:
        total=0;seen=set()
        for member in zipped.infolist():
            name=member.filename.rstrip("/");path=PurePosixPath(name)
            if (not name or path.is_absolute() or path.as_posix()!=name or "\\" in name or ":" in name
                    or any(part in {".",".."} for part in path.parts) or name.casefold() in seen
                    or stat.S_ISLNK(member.external_attr>>16)):
                raise ValueError("Invalid ZIP member: "+name)
            total+=member.file_size;seen.add(name.casefold())
        if total>512*1024**2:raise ValueError("Release ZIP expansion exceeds its finite budget")
        if json.loads(zipped.read("version.json"))!=version:raise ValueError("Version inside ZIP differs")
        target.mkdir(parents=True)
        release=target/"release";zipped.extractall(release)
    evidence.mkdir(parents=True)
    installed=target/"installed"
    command=[sys.executable,"-I","-B","-X","utf8",str(release/"bundle/install.py"),"--target",str(installed),
             "--manifest-sha256",version["manifest_sha256"]]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=300,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    (evidence/"install.stdout.json").write_bytes(result.stdout)
    (evidence/"install.stderr.txt").write_bytes(result.stderr)
    if result.returncode or not json.loads(result.stdout)["ok"]:raise RuntimeError("Installation failed; evidence retained")
    runtime={"release":TAG,"python":sys.executable,"installed_directory":str(installed),
             "manifest_sha256":version["manifest_sha256"],"launcher_sha256":sha(installed/"run.py"),
             "zip_sha256":sha(archive),"native_only":True}
    if args.activate:
        config=ROOT/"local/agent-ffmpeg/runtime.json"
        if config.exists():(target/"runtime-before.json").write_bytes(config.read_bytes())
        temporary=config.with_suffix(".tmp");save(temporary,runtime);temporary.replace(config)
    for name in ("receipt.json","dependency-audit.json","install.log"):
        (evidence/name).write_bytes((installed/name).read_bytes())
    report={"ok":True,"release":TAG,"runtime":runtime,"activated":args.activate,"archive":str(archive),
            "archive_bytes":archive.stat().st_size,"network_downloads":0,"virtual_environments_created":0}
    save(evidence/"installation.json",report);save(target/"installation.json",report)
    print(json.dumps(report,ensure_ascii=False))


if __name__=="__main__":main()
