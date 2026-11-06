import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from updates import available_release
import update_install


class UpdatesTests(unittest.TestCase):
    def release(self):
        return {'tag_name':'v0.5.12','draft':False,'prerelease':False,'assets':[
            {'name':'LisaMacroMagic_v0.5.12.exe','state':'uploaded','size':100,'digest':'sha256:'+'a'*64}]}

    def test_numeric_comparison_and_trusted_download_path(self):
        release=self.release()
        self.assertIsNone(available_release(json.dumps(release),'0.5.12'))
        release['assets'][0]['browser_download_url']='https://example.com/wrong.exe'
        result=available_release(json.dumps(release),'0.5.9')
        self.assertEqual(result,('0.5.12','https://github.com/Able1337/LisaMacroMagic/releases/download/v0.5.12/LisaMacroMagic_v0.5.12.exe','a'*64,100))

    def test_requires_stable_release_with_digest(self):
        release=self.release()
        release['assets'][0]['digest']=None
        with self.assertRaises(ValueError): available_release(json.dumps(release),'0.5.11')
        release['prerelease']=True
        with self.assertRaises(ValueError): available_release(json.dumps(release),'0.5.11')

    def test_replace_and_restart_same_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'renamed.exe'; target.write_bytes(b'old')
            stage=Path(tmp)/'.lisa-update-test'; stage.mkdir(); (stage/'ready.exe').write_bytes(b'new')
            with patch.object(update_install,'launch') as launch:
                update_install.replace(stage,target)
                launch.assert_called_once_with(target,'--update-cleanup',stage)
            self.assertEqual(target.read_bytes(),b'new')
            self.assertEqual((stage/'backup.exe').read_bytes(),b'old')

    def test_failed_restart_restores_old_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'app.exe'; target.write_bytes(b'old')
            stage=Path(tmp)/'.lisa-update-test'; stage.mkdir(); (stage/'ready.exe').write_bytes(b'new')
            with patch.object(update_install,'launch',side_effect=[OSError('failed'),None]) as launch:
                with self.assertRaises(OSError): update_install.replace(stage,target)
                self.assertEqual(launch.call_args.args,(target,))
            self.assertEqual(target.read_bytes(),b'old')
