"""Synthetic Steam account/client fixtures only. Own work: djultra64."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock

BASE=76561197960265728

class SteamAccountTests(unittest.TestCase):
    def make_root(self,folder,users):
        root=Path(folder);(root/'config').mkdir(parents=True)
        text='"users"\n{\n'
        for account,name,recent,timestamp in users:
            (root/'userdata'/str(account)).mkdir(parents=True)
            text+='"'+str(BASE+account)+'" { "AccountName" "PRIVATE_LOGIN_NEVER_DISPLAY" "PersonaName" "'+name+'" "MostRecent" "'+str(recent)+'" "Timestamp" "'+str(timestamp)+'" }\n'
        (root/'config/loginusers.vdf').write_text('\ufeff// Synthetic fixture\n'+text+'}\n',encoding='utf-8')
        return root

    def test_discovery_uses_id32_and_selects_unique_most_recent_without_exposing_login(self):
        from launcher.steam_client import discover_accounts,select_account
        with tempfile.TemporaryDirectory() as d:
            root=self.make_root(d,[(17,'Older',0,90),(29,'Current',1,100)])
            # A SteamID64-looking directory is not an account-id32 profile.
            (root/'userdata'/str(BASE+17)).mkdir()
            accounts=discover_accounts([root,root])
            self.assertEqual(len(accounts),2)
            selected=select_account(accounts,platform='linux')
            self.assertEqual((selected.account_id,selected.display_name),('29','Current'))
            self.assertEqual(selected.shortcuts_path,root/'userdata/29/config/shortcuts.vdf')
            self.assertNotIn('PRIVATE_LOGIN',repr(accounts))
            self.assertFalse(selected.shortcuts_path.exists())

    def test_timestamp_resolves_recent_tie_but_equal_scores_remain_ambiguous(self):
        from launcher.steam_client import discover_accounts,select_account
        with tempfile.TemporaryDirectory() as d:
            root=self.make_root(d,[(17,'A',1,90),(29,'B',1,100)])
            self.assertEqual(select_account(discover_accounts([root]),platform='linux').account_id,'29')
            text=(root/'config/loginusers.vdf').read_text().replace('"100"','"90"')
            (root/'config/loginusers.vdf').write_text(text)
            self.assertIsNone(select_account(discover_accounts([root]),platform='linux'))

    def test_userdata_only_single_account_and_zero_are_handled(self):
        from launcher.steam_client import discover_accounts,select_account
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for value in ['0','7',str(BASE+7),'not-a-number']:(root/'userdata'/value).mkdir(parents=True)
            accounts=discover_accounts([root])
            self.assertEqual(len(accounts),1)
            self.assertEqual(select_account(accounts,platform='linux').account_id,'7')

    def test_comments_escapes_and_malformed_vdf(self):
        from launcher.steam_client import discover_accounts
        with tempfile.TemporaryDirectory() as d:
            root=self.make_root(d,[(17,'A',1,90)])
            file=root/'config/loginusers.vdf'
            file.write_text('"users" /* outside */ { "'+str(BASE+17)+'" { "PersonaName" "A \\"quoted\\" \\\\ name // literal" // comment\n "MostRecent" "1" } }')
            self.assertEqual(discover_accounts([root])[0].display_name,'A "quoted" \\ name // literal')
            file.write_text('"users" { "'+str(BASE+17)+'" { "PersonaName" "{" } }')
            self.assertEqual(discover_accounts([root])[0].display_name,'{')
            for invalid in ['"users" {','"users" { "x" "unterminated','"users" {} #include "private.vdf"','"users" { /* unfinished']:
                file.write_text(invalid)
                with self.subTest(vdf=invalid),self.assertRaisesRegex(ValueError,'loginusers'):
                    discover_accounts([root])

    def test_windows_active_user_can_override_stale_recent_flag(self):
        from launcher.steam_client import discover_accounts,select_account
        with tempfile.TemporaryDirectory() as d:
            root=self.make_root(d,[(17,'A',1,100),(29,'B',0,90)])
            with patch('launcher.steam_client._windows_active_account',return_value=('29',root)):
                self.assertEqual(select_account(discover_accounts([root]),platform='win32').account_id,'29')

    def test_ambiguous_recent_accounts_do_not_select_a_newer_nonrecent_account(self):
        from launcher.steam_client import SteamAccount,select_account
        root=Path('/synthetic/Steam')
        accounts=[SteamAccount(root,'1','A',True,100),SteamAccount(root,'2','B',True,100),
                  SteamAccount(root,'3','C',False,200)]
        self.assertIsNone(select_account(accounts,platform='linux'))
        self.assertEqual(select_account([SteamAccount(root,'1','A',False,90),
                                         SteamAccount(root,'2','B',False,100)],platform='linux').account_id,'2')

    def test_active_linux_native_root_overrides_other_installations_recent_metadata(self):
        from launcher.steam_client import SteamAccount,select_account
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);native=root/'native';flatpak=root/'flatpak';proc=root/'proc';pid=proc/'42'
            pid.mkdir(parents=True);(pid/'comm').write_text('steam\n')
            (pid/'status').write_text('State:\tS (sleeping)\n')
            (pid/'exe').symlink_to(native/'ubuntu12_32/steam')
            accounts=[SteamAccount(native,'1','A'),SteamAccount(flatpak,'2','B',True,100)]
            with patch('launcher.steam_client.PROC_ROOT',proc):
                self.assertEqual(select_account(accounts,platform='linux').account_id,'1')
            with patch('launcher.steam_client.PROC_ROOT',proc),patch('launcher.steam_client.os.getuid',return_value=os.getuid()+1):
                self.assertEqual(select_account(accounts,platform='linux').account_id,'2')

class SteamClientLifecycleTests(unittest.TestCase):
    def test_native_shutdown_waits_gracefully_and_cleans_private_runtime_environment(self):
        from launcher.steam_client import close_steam
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'steam.sh').touch();(root/'steam.sh').chmod(0o755)
            private=str(root/'portable/runtime/python')
            env={'PYTHONHOME':private,'PYTHONPATH':'private','TK_LIBRARY':'private','TCL_LIBRARY':'private',
                 'LD_PRELOAD':'private.so','LD_LIBRARY_PATH':private+'/lib64:/usr/lib64','PATH':'/usr/bin'}
            proc=root/'proc';proc.mkdir()
            with patch.dict(os.environ,env,clear=True),patch('launcher.steam_client.PROC_ROOT',proc), \
                 patch('launcher.steam_client.Path.home',return_value=root/'SyntheticHome'), \
                 patch('launcher.steam_client.steam_is_running',side_effect=[True,True,False]), \
                 patch('launcher.steam_client.subprocess.Popen',return_value=Mock(poll=Mock(return_value=0))) as start, \
                 patch('launcher.steam_client.time.sleep'):
                self.assertTrue(close_steam(root,platform='linux'))
            args=start.call_args.args[0];child=start.call_args.kwargs['env']
            self.assertEqual(args,[str(root/'steam.sh'),'-shutdown'])
            self.assertEqual(child['LD_LIBRARY_PATH'],'/usr/lib64')
            for key in ['PYTHONHOME','PYTHONPATH','TK_LIBRARY','TCL_LIBRARY','LD_PRELOAD']:self.assertNotIn(key,child)

    def test_timeout_does_not_force_kill_and_stopped_client_is_not_started(self):
        from launcher.steam_client import close_steam
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'steam.exe').touch()
            with patch('launcher.steam_client.steam_is_running',return_value=False),patch('launcher.steam_client.subprocess.Popen') as start:
                self.assertFalse(close_steam(root,platform='win32'));start.assert_not_called()
            with patch('launcher.steam_client.steam_is_running',return_value=True), \
                 patch('launcher.steam_client.time.monotonic',side_effect=[0,0,46]), \
                 patch('launcher.steam_client.time.sleep'),patch('launcher.steam_client.subprocess.Popen',return_value=Mock()) as start:
                with self.assertRaisesRegex(TimeoutError,'Steam'):close_steam(root,platform='win32')
                self.assertEqual(start.call_args.args[0],[str(root/'steam.exe'),'-shutdown'])
                start.return_value.kill.assert_not_called();start.return_value.terminate.assert_not_called()

    def test_flatpak_reopen_uses_the_app_command_without_forced_kill(self):
        from launcher.steam_client import reopen_steam
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'.var/app/com.valvesoftware.Steam/.local/share/Steam';root.mkdir(parents=True)
            with patch('launcher.steam_client.shutil.which',return_value='/usr/bin/flatpak'), \
                 patch('launcher.steam_client.subprocess.Popen',return_value=Mock()) as start:
                reopen_steam(root,platform='linux')
            self.assertEqual(start.call_args.args[0],['/usr/bin/flatpak','run','com.valvesoftware.Steam'])


class SteamProcessScopeTests(unittest.TestCase):
    def test_windows_query_is_scoped_to_current_session(self):
        from launcher.steam_client import steam_is_running
        with patch('launcher.steam_client._windows_session_id',return_value=3), \
             patch('launcher.steam_client.subprocess.run',return_value=Mock(stdout='"steam.exe","55","Console","3","100 K"\n')) as run:
            self.assertTrue(steam_is_running('win32'))
        self.assertIn('SESSION eq 3',run.call_args.args[0])

    def test_linux_does_not_treat_another_users_steam_as_this_users_client(self):
        from launcher.steam_client import steam_is_running
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);pid=root/'42';pid.mkdir()
            (pid/'comm').write_text('steam\n');(pid/'status').write_text('State:\tS (sleeping)\n')
            with patch('launcher.steam_client.PROC_ROOT',root),patch('launcher.steam_client.os.getuid',return_value=os.getuid()+1):
                self.assertFalse(steam_is_running('linux'))
            with patch('launcher.steam_client.PROC_ROOT',root):self.assertTrue(steam_is_running('linux'))
            (pid/'status').write_text('State:\tZ (zombie)\n')
            with patch('launcher.steam_client.PROC_ROOT',root):self.assertFalse(steam_is_running('linux'))


class SteamShutdownCompletionTests(unittest.TestCase):
    def make_process(self,proc,pid=42,*,comm='steam',start=100,executable=None):
        directory=proc/str(pid);directory.mkdir(parents=True,exist_ok=True)
        (directory/'comm').write_text(comm+'\n')
        (directory/'status').write_text('State:\tS (sleeping)\n')
        # Linux stat fields 3..22: state, eighteen other fields, starttime.
        (directory/'stat').write_text(str(pid)+' ('+comm+') S '+'0 '*18+str(start)+'\n')
        if executable is not None:(directory/'exe').symlink_to(executable)
        return directory

    def remove_process(self,directory):
        for path in directory.iterdir():path.unlink()
        directory.rmdir()

    def test_close_waits_for_original_pid_after_steam_comm_disappears(self):
        from launcher.steam_client import close_steam
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);proc=root/'proc';pid=self.make_process(proc)
            sleeps=[]
            def advance(_delay):
                sleeps.append(True)
                if len(sleeps)==1:(pid/'comm').write_text('shutting-down\n')
                else:self.remove_process(pid)
            with patch('launcher.steam_client.PROC_ROOT',proc), \
                 patch('launcher.steam_client._start_client',return_value=Mock(poll=Mock(return_value=0))), \
                 patch('launcher.steam_client.time.sleep',side_effect=advance):
                self.assertTrue(close_steam(root,platform='linux'))
            self.assertEqual(len(sleeps),2,'Shutdown must wait for PID exit, not only disappearance of the steam name')

    def test_live_target_pid_file_is_checked_even_after_process_name_changes(self):
        from launcher.steam_client import close_steam
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);proc=root/'proc';steam=root/'Steam';steam.mkdir()
            pid=self.make_process(proc,comm='shutting-down',executable=steam/'ubuntu12_32/steam')
            (steam/'steam.pid').write_text('42\n')
            with patch('launcher.steam_client.PROC_ROOT',proc), \
                 patch('launcher.steam_client._start_client',return_value=Mock(poll=Mock(return_value=0))) as start, \
                 patch('launcher.steam_client.time.sleep',side_effect=lambda _:self.remove_process(pid)):
                self.assertTrue(close_steam(steam,platform='linux'))
            self.assertTrue(start.call_args.kwargs['shutdown'])

    def test_shutdown_request_process_finishes_before_close_returns(self):
        from launcher.steam_client import close_steam
        with tempfile.TemporaryDirectory() as temporary:
            proc=Path(temporary)/'proc';proc.mkdir()
            child=Mock(poll=Mock(side_effect=[None,None,0]))
            with patch('launcher.steam_client.PROC_ROOT',proc), \
                 patch('launcher.steam_client.steam_is_running',side_effect=[True,False,False,False]), \
                 patch('launcher.steam_client._start_client',return_value=child), \
                 patch('launcher.steam_client.time.sleep') as sleep:
                self.assertTrue(close_steam(Path(temporary),platform='linux'))
            self.assertEqual(sleep.call_count,2)

    def test_recycled_original_pid_does_not_block_shutdown(self):
        from launcher.steam_client import close_steam
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);proc=root/'proc';pid=self.make_process(proc)
            def recycle(_delay):
                (pid/'comm').write_text('other-app\n')
                (pid/'stat').write_text('42 (other-app) S '+'0 '*18+'999\n')
            with patch('launcher.steam_client.PROC_ROOT',proc), \
                 patch('launcher.steam_client._start_client',return_value=Mock(poll=Mock(return_value=0))), \
                 patch('launcher.steam_client.time.sleep',side_effect=recycle) as sleep:
                self.assertTrue(close_steam(root,platform='linux'))
            self.assertEqual(sleep.call_count,1)

    def test_timeout_still_refuses_changes_without_killing_lingering_pid(self):
        from launcher.steam_client import close_steam
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);proc=root/'proc';steam=root/'Steam';steam.mkdir()
            self.make_process(proc,comm='shutting-down',executable=steam/'ubuntu12_32/steam')
            (steam/'steam.pid').write_text('42\n');child=Mock(poll=Mock(return_value=0))
            with patch('launcher.steam_client.PROC_ROOT',proc), \
                 patch('launcher.steam_client._start_client',return_value=child), \
                 patch('launcher.steam_client.time.monotonic',side_effect=[0,46]):
                with self.assertRaises(TimeoutError):close_steam(steam,platform='linux')
            child.kill.assert_not_called();child.terminate.assert_not_called()

    def test_stale_pid_file_does_not_wait_for_a_game_under_the_steam_root(self):
        from launcher.steam_client import close_steam
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);proc=root/'proc';steam=root/'Steam';steam.mkdir()
            self.make_process(proc,comm='other-game',executable=steam/'steamapps/common/Other/game')
            (steam/'steam.pid').write_text('42\n')
            with patch('launcher.steam_client.PROC_ROOT',proc), \
                 patch('launcher.steam_client._start_client',return_value=Mock(poll=Mock(return_value=0))) as start, \
                 patch('launcher.steam_client.time.monotonic',side_effect=[0,46]):
                self.assertFalse(close_steam(steam,platform='linux'))
            start.assert_not_called()
