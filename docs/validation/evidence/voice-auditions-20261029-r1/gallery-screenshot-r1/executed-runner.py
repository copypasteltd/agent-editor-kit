"""Capture the actual local audition gallery; close the owned headless browser."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/voice-auditions-20261029-r1'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    accepted=json.loads((BASE/'r2/verification.json').read_bytes())
    assert accepted['status']=='passed' and accepted['voices']==103
    page=Path(accepted['local_gallery']);assert page.is_file()
    assert page.read_text(encoding='utf-8').count('<audio controls preload="none"')==103
    out=BASE/'gallery-screenshot-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    artifact=ROOT/'docs/assets/voice-gallery61-20261029-r1';artifact.mkdir(exist_ok=False)
    browser=Path('C:/Program Files/Google/Chrome/Application/chrome.exe');assert browser.is_file()
    profile=page.parent.parent/'browser-profile';assert not profile.exists()
    destination=artifact/'actual.png'
    command=[str(browser),'--headless=new','--disable-gpu','--disable-background-networking',
             '--disable-component-update','--disable-sync','--disable-default-apps','--no-first-run',
             '--no-default-browser-check','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost',
             '--hide-scrollbars','--window-size=1440,1000','--force-device-scale-factor=1',
             '--user-data-dir='+str(profile),'--screenshot='+str(destination),page.as_uri()]
    process=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        stdout,stderr=process.communicate(timeout=90)
    except BaseException:
        subprocess.run(['taskkill.exe','/PID',str(process.pid),'/T','/F'],capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        process.communicate(timeout=30)
        raise
    (out/'browser.stdout').write_bytes(stdout);(out/'browser.stderr').write_bytes(stderr)
    assert process.returncode==0 and destination.is_file(),stderr[-1800:]
    # This browser used a dedicated E-drive profile. Check its remaining owned
    # browser processes without affecting any unrelated interactive browser.
    query="Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object { $_.CommandLine -like '*voice-preview61-r2*browser-profile*' } | Select-Object ProcessId,CommandLine | ConvertTo-Json"
    check=subprocess.run(['powershell.exe','-NoProfile','-Command',query],capture_output=True,timeout=30,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'remaining-browser.stdout').write_bytes(check.stdout)
    (out/'remaining-browser.stderr').write_bytes(check.stderr)
    assert check.returncode==0 and not check.stdout.strip(),check.stdout
    import struct
    raw=destination.read_bytes();assert raw[:8]==b'\x89PNG\r\n\x1a\n'
    assert struct.unpack('>II',raw[16:24])==(1440,1000)
    (artifact/'SOURCE.txt').write_text('Actual native Chrome headless screenshot of the locally generated Agent Editor Kit voice-audition gallery. UI/text authored for this project; screenshot CC0-1.0. The 103 generated audio files are internal/unverified and are NOT included or licensed by this notice. This screenshot is not playback/listening/naturalness acceptance. Browser profile and all temporary files remain on E:. Owned headless browser exited and no matching browser process remained.\n',encoding='utf-8')
    report=dict(status='passed',actual_headless_browser=True,browser_exit_code=0,
                owned_browser_processes_remaining=0,interactive_tabs_opened=0,
                source_page=str(page),source_page_sha256=sha(page),source_audio_elements=103,
                screenshot=destination.relative_to(ROOT).as_posix(),screenshot_sha256=sha(destination),
                width=1440,height=1000,audio_published=False,human_listening=False,naturalness_accepted=False,
                command=command)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
