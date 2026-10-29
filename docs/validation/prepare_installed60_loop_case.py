"""Derive a strictly installed CLI60 actual loop case with complete source comparison."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def main():
    text=(ROOT/'docs/validation/run_music_loop_case.py').read_text(encoding='utf-8')
    text=text.replace('Real source60 music fragment','Real independently installed60 music fragment')
    text=text.replace("parser.add_argument('--run',required=True);a=parser.parse_args()", "parser.add_argument('--run',required=True);parser.add_argument('--installed',type=Path,required=True);a=parser.parse_args()")
    text=text.replace("    gate=load(BASE/'targeted-r1/verification.json')", "    installed=a.installed.resolve()\n    assert installed.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())\n    gate=load(BASE/'installed60-loop-r1/verification.json')")
    text=text.replace("    assert all(sha(ROOT/name)==pin for name,pin in gate['file_hashes'].items())", "    assert gate['source_and_installed_equal']\n    assert all(sha(ROOT/name)==pin for name,pin in gate['file_hashes'].items())",1)
    text=text.replace("'music-loop60-case-'", "'music-loop60-installed-case-'")
    text=text.replace("('actual-case-'+a.run)", "('installed-actual-case-'+a.run)")
    text=text.replace("argv=[PYTHON,'-E','-B','-u','-X','utf8',str(ROOT/'scripts/run_source_editor.py'),*map(str,args)]", "argv=[PYTHON,'-I','-S','-B','-u','-X','utf8',str(installed/'run.py'),*map(str,args)]")
    needle="        np.testing.assert_array_equal(pcm(replay/again['asset']['uri']),fixed)"
    text=text.replace(needle,needle+"\n        reference=load(BASE/'actual-case-r1/verification.json')\n        assert reference['status']=='passed'\n        assert fixed.nbytes==reference['complete_repaired_PCM_bytes']\n        assert hashlib.sha256(fixed.tobytes()).hexdigest()==reference['complete_repaired_PCM_sha256']")
    text=text.replace("source_only=True,source_fallback=False", "source_only=False,source_fallback=False,installed=str(installed),complete_source_installed_PCM_equal=True")
    path=ROOT/'docs/validation/run_installed60_loop_case.py';assert not path.exists()
    compile(text,str(path),'exec');path.write_text(text,encoding='utf-8')
    print('Prepared installed-only loop case; full source PCM comparison required.')

if __name__=='__main__':main()
