"""Reassemble checked release parts into a local ZIP using native Python only."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def assemble(directory, output):
    directory=Path(directory).resolve();output=Path(output).absolute()
    manifest=json.loads((directory/'parts.json').read_bytes())
    rows=manifest['parts']
    if not 1<=len(rows)<=16 or sum(r['bytes'] for r in rows)!=manifest['bytes']:
        raise ValueError('Invalid finite part inventory')
    if output.exists():
        if output.is_file() and sha(output)==manifest['sha256']:
            return {'ok':True,'archive':str(output),'sha256':manifest['sha256'],'already_assembled':True}
        raise ValueError('Existing output differs; it is preserved')
    for i,row in enumerate(rows,1):
        if (not re.fullmatch(r'[A-Za-z0-9_.-]+\.zip\.part\d{2}',row['name'])
                or not row['name'].endswith(f'.part{i:02}') or not 0<row['bytes']<=64*1024**2):
            raise ValueError('Invalid part name or size')
        path=directory/row['name']
        if path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:
            raise ValueError('Part SHA-256 mismatch: '+row['name'])
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_name(output.name+'.assembling')
    try:
        with temporary.open('xb') as out:
            for row in rows:
                with (directory/row['name']).open('rb') as source:
                    while chunk:=source.read(1024*1024):out.write(chunk)
        if temporary.stat().st_size!=manifest['bytes'] or sha(temporary)!=manifest['sha256']:
            raise ValueError('Reassembled ZIP digest mismatch')
        # Native Windows rename refuses an existing destination.
        if os.name!='nt':raise ValueError('Use native Windows for this release')
        temporary.rename(output)
    finally:
        if temporary.exists():temporary.unlink()
    return {'ok':True,'archive':str(output),'sha256':manifest['sha256'],'bytes':manifest['bytes'],'parts':len(rows)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(assemble(args.directory,args.output),ensure_ascii=False))
