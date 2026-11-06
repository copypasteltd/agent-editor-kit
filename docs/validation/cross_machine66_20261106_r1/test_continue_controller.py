"""Protocol contracts only; no remote contact or product execution."""
import copy
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC=importlib.util.spec_from_file_location('aek_cross_machine_controller',Path(__file__).with_name('continue_controller.py'))
controller=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)


class ControllerContracts(unittest.TestCase):
    def setUp(self):
        self.owner={'owner_id':'contract-owned-run'}
        self.value=dict(actual_process_live=True,downloads_verified=False,verification_present=False,
            failure_present=False,state={'phase':'downloading'},launch=dict(pid=42,creation_filetime=123456,
            executable=controller.REMOTE_PYTHON,root=controller.REMOTE_ROOT,owner_id=self.owner['owner_id']))

    def test_running_process_dominates_apparent_terminal(self):
        self.value.update(verification_present=True,state={'phase':'passed'})
        self.assertEqual(controller.classify(self.value,self.owner),'running')

    def test_exact_dead_passed_terminal(self):
        self.value.update(actual_process_live=False,downloads_verified=True,verification_present=True,state={'phase':'passed'})
        self.assertEqual(controller.classify(self.value,self.owner),'passed')

    def test_passed_without_downloads_rejected(self):
        self.value.update(actual_process_live=False,verification_present=True,state={'phase':'passed'})
        with self.assertRaises(ValueError):controller.classify(self.value,self.owner)

    def test_dead_without_terminal_is_not_success(self):
        self.value.update(actual_process_live=False,state={'phase':'running'})
        self.assertEqual(controller.classify(self.value,self.owner),'stopped-without-terminal')

    def test_absent_launch_is_bootstrap_pending(self):
        self.value.update(actual_process_live=False,launch=None,state=None)
        self.assertEqual(controller.classify(self.value,self.owner),'bootstrap-pending')

    def test_failure_dominates_passed_state(self):
        self.value.update(actual_process_live=False,failure_present=True,verification_present=True,state={'phase':'passed'})
        self.assertEqual(controller.classify(self.value,self.owner),'failed')

    def test_foreign_or_malformed_identity_rejected(self):
        for key,value in [('owner_id','foreign'),('pid',True),('pid',0),('creation_filetime',0),
                          ('root','C:/dev/other'),('executable','C:/other/python.exe')]:
            with self.subTest(key=key,value=value):
                candidate=copy.deepcopy(self.value);candidate['launch'][key]=value
                with self.assertRaises(ValueError):controller.classify(candidate,self.owner)

    def test_nonboolean_status_flags_rejected(self):
        for key in ('actual_process_live','downloads_verified','verification_present','failure_present'):
            candidate=copy.deepcopy(self.value);candidate[key]='false'
            with self.subTest(key=key),self.assertRaises(ValueError):controller.classify(candidate,self.owner)

    def test_live_without_identity_rejected(self):
        self.value['launch']=None
        with self.assertRaises(ValueError):controller.classify(self.value,self.owner)

    def test_client_observation_waits_same_handle_before_another_rpc(self):
        base=controller.PROJECT/'local/agent-ffmpeg'
        with tempfile.TemporaryDirectory(prefix='cross-controller-contract-',dir=base) as raw:
            operation=Path(raw)
            process=mock.Mock(pid=42)
            process.wait.side_effect=[controller.subprocess.TimeoutExpired('fixture-client',30),0]
            def spawn(*args,**kwargs):
                kwargs['stdout'].write(b'{"actual_process_live":true}')
                kwargs['stdout'].flush()
                return process
            with mock.patch.object(controller,'OPERATION',operation),mock.patch.object(controller,'BOOT',
                {'process_identity':lambda pid:dict(pid=pid,creation_filetime=123,executable='fixture-client')},create=True),\
                mock.patch.object(controller.subprocess,'Popen',side_effect=spawn) as launch:
                result=controller.run_action('fixture',Path('fixture-client.py'))
            self.assertTrue(result['actual_process_live'])
            self.assertEqual(launch.call_count,1)
            self.assertEqual(process.wait.call_count,2)

    def test_live_client_budget_expiry_is_not_a_retryable_remote_observation(self):
        base=controller.PROJECT/'local/agent-ffmpeg'
        with tempfile.TemporaryDirectory(prefix='cross-controller-contract-',dir=base) as raw:
            process=mock.Mock(pid=42)
            process.wait.side_effect=controller.subprocess.TimeoutExpired('fixture-client',30)
            with mock.patch.object(controller,'OPERATION',Path(raw)),mock.patch.object(controller,'BOOT',
                {'process_identity':lambda pid:dict(pid=pid,creation_filetime=123,executable='fixture-client')},create=True),\
                mock.patch.object(controller.subprocess,'Popen',return_value=process) as launch,\
                mock.patch.object(controller.time,'monotonic',side_effect=[0,301,302]):
                with self.assertRaises(controller.ClientStillRunning):
                    controller.run_action('fixture',Path('fixture-client.py'))
            self.assertEqual(launch.call_count,1)
            self.assertFalse(issubclass(controller.ClientStillRunning,RuntimeError))

    def test_allowed_roles(self):
        for name in ['verification.json','job.stderr','registration-upgrade66.json',
                     'case-final66/verification.json','case-before63/logs/render.stdout',
                     'case-rollback63/imported/renders/cross-host.mp4']:
            with self.subTest(name=name):self.assertEqual(controller.relative(name).as_posix(),name)

    def test_escape_and_private_roles_rejected(self):
        for name in ['../verification.json','/verification.json','C:/x','case-final66/../../x',
                     'case-final66\\verification.json','transfer.json','ownership.json','device.json',
                     'case-final66//verification.json','case-final66/./verification.json',
                     'case-unknown/verification.json','verification.json\0x']:
            with self.subTest(name=name),self.assertRaises(ValueError):controller.relative(name)

    def test_public_return_rejects_private_material_before_publishing(self):
        base=controller.PROJECT/'local/agent-ffmpeg'
        with tempfile.TemporaryDirectory(prefix='cross-controller-contract-',dir=base) as raw:
            root=Path(raw);source=root/'source';source.mkdir()
            (source/'verification.json').write_text('{"private":"fixture-secret-marker"}',encoding='utf-8')
            with mock.patch.object(controller,'PUBLIC',root/'public'):
                with self.assertRaises(ValueError):controller.publish_return(source,['fixture-secret-marker'])
                self.assertFalse(controller.PUBLIC.exists())

    def test_public_return_preserves_existing_evidence(self):
        base=controller.PROJECT/'local/agent-ffmpeg'
        with tempfile.TemporaryDirectory(prefix='cross-controller-contract-',dir=base) as raw:
            root=Path(raw);source=root/'source';source.mkdir()
            (source/'verification.json').write_text('{"fixture":true}',encoding='utf-8')
            with mock.patch.object(controller,'PUBLIC',root/'public'):
                self.assertEqual(controller.publish_return(source,[]),1)
                before=(controller.PUBLIC/'verification.json').read_bytes()
                with self.assertRaises(FileExistsError):controller.publish_return(source,[])
                self.assertEqual((controller.PUBLIC/'verification.json').read_bytes(),before)

    def test_preflight_requires_fresh_owned_host_and_exact_reviewed_image(self):
        base=controller.PROJECT/'local/agent-ffmpeg'
        with tempfile.TemporaryDirectory(prefix='cross-controller-contract-',dir=base) as raw:
            image=Path(raw)/'screen.png';image.write_bytes(b'fixture-screen-only')
            now=dt.datetime.now(dt.timezone.utc)
            summary=dict(ok=True,control={'state':'ready'},startedAt=now.isoformat(),
                device=dict(computerName='DESKTOP-TE44HE1',inputDesktop={'opened':True,'name':'Default'},
                            foregroundOwner={'Name':'application.exe'}),
                calls=[{'name':'Screenshot','images':[str(image)]}])
            pin=hashlib.sha256(image.read_bytes()).hexdigest()
            self.assertEqual(controller.validate_preflight(summary,pin,now),image)
            bad_cases=[]
            foreign=copy.deepcopy(summary);foreign['device']['computerName']='OTHER';bad_cases.append(foreign)
            locked=copy.deepcopy(summary);locked['device']['foregroundOwner']['Name']='LockApp.exe';bad_cases.append(locked)
            security=copy.deepcopy(summary);security['device']['inputDesktop']['name']='Winlogon';bad_cases.append(security)
            stale=copy.deepcopy(summary);stale['startedAt']=(now-dt.timedelta(seconds=901)).isoformat();bad_cases.append(stale)
            future=copy.deepcopy(summary);future['startedAt']=(now+dt.timedelta(seconds=1)).isoformat();bad_cases.append(future)
            busy=copy.deepcopy(summary);busy['control']['state']='user';bad_cases.append(busy)
            absent=copy.deepcopy(summary);absent['calls']=[];bad_cases.append(absent)
            for candidate in bad_cases:
                with self.subTest(candidate=candidate),self.assertRaises(ValueError):
                    controller.validate_preflight(candidate,pin,now)
            with self.assertRaises(ValueError):controller.validate_preflight(summary,'0'*64,now)

    def test_returned_movie_and_all_four_replays_are_required(self):
        base=controller.PROJECT/'local/agent-ffmpeg'
        with tempfile.TemporaryDirectory(prefix='cross-controller-contract-',dir=base) as raw:
            root=Path(raw)
            parcels={'files':[{'name':'application.zip','sha256':'fixture-archive-pin'}]}
            report=dict(status='cross-machine-cli66-cpu-upgrade-rollback-passed',cli_version='0.1.66',
                remote_hostname='DESKTOP-TE44HE1',old_application_modules=283,new_application_modules=289,
                actual_registration_transitions=list(controller.VERSIONS.values()),
                downloads_verified={'application.zip':'fixture-archive-pin'},cases={})
            for key in ('actual_offline_install','actual_base_only_configuration','actual_isolated_registration',
                'registration_conflict_preserved','old_archive_files_unchanged','old_private_configuration_unchanged',
                'new_archive_files_unchanged','cross_machine','cli66_cpu_upgrade_accepted'):report[key]=True
            for key in ('generic_delivery_controller_tested','global_registration_changed','global_PATH_changed',
                'gpu_render','model_inference','human_listening','natural_quality_accepted','clean_host',
                'full_G34_accepted','full_goal_closed'):report[key]=False
            references={}
            for label,version in controller.VERSIONS.items():
                directory=root/('case-'+label);movie=directory/'imported/renders/cross-host.mp4'
                movie.parent.mkdir(parents=True);movie.write_bytes(('fixture-media-'+version).encode())
                decoded={'RGBA':'SHA256='+version,'PCM':'SHA256='+version}
                video={'nb_read_frames':'60'}
                case=dict(status='cross-host-baseline-passed',cli_version=version,
                    complete_RGBA_PCM_equal=True,complete_master_assets_equal=True,actual_registered_Skill=True,
                    source_fallback=False,actual=dict(decoded=decoded,video=video,audio={'finite_non_silent':True},
                    movie_sha256=hashlib.sha256(movie.read_bytes()).hexdigest()),
                    expected=dict(complete_decoded=decoded,video=video))
                (directory/'verification.json').write_text(json.dumps(case),encoding='utf-8')
                report['cases'][label]=case
                references[version]=copy.deepcopy(case['expected'])
            def write_report():
                (root/'verification.json').write_text(json.dumps(report),encoding='utf-8')
            write_report()
            self.assertEqual(controller.validate_acceptance(root,parcels,references),report)
            report['full_G34_accepted']=True;write_report()
            with self.assertRaises(ValueError):controller.validate_acceptance(root,parcels,references)
            report['full_G34_accepted']=False;write_report()
            wrong=copy.deepcopy(references);wrong['0.1.66']['complete_decoded']['PCM']='tampered-reference'
            with self.assertRaises(ValueError):controller.validate_acceptance(root,parcels,wrong)
            (root/'case-final66/imported/renders/cross-host.mp4').write_bytes(b'changed-output')
            with self.assertRaises(ValueError):controller.validate_acceptance(root,parcels,references)


if __name__=='__main__':unittest.main(verbosity=2)
