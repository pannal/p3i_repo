import importlib.util,tempfile,pathlib,sys,unittest,fcntl,os,types
from unittest.mock import patch
ADDON=pathlib.Path(__file__).resolve().parents[1]/'omega/script.hdmi.reset/default.py'
spec=importlib.util.spec_from_file_location('hdmi_reset',ADDON);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Checks(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name)
  self.phy=self.root/'phy';self.phy.write_text('ready');self.lock=self.root/'hdmi-reset.lock';self.reports=[]
  for p in [patch.object(m,'PHY',str(self.phy)),patch.object(m,'lock_path',return_value=str(self.lock)),patch.object(m,'report',side_effect=lambda msg,error=False:self.reports.append((msg,error))),patch.object(sys,'argv',['default.py'])]:p.start();self.addCleanup(p.stop)
 def test_sequence(self):
  seen=[]
  with patch.object(m.time,'sleep',side_effect=lambda delay:seen.append((delay,self.phy.read_text()))):m.main()
  self.assertEqual(seen,[(1,'0\n')]);self.assertEqual(self.phy.read_text(),'1\n');self.assertEqual(self.reports,[(m.MESSAGES[30004],False)])
 def test_interrupted_delay_restores_output(self):
  with patch.object(m.time,'sleep',side_effect=KeyboardInterrupt):
   with self.assertRaises(KeyboardInterrupt):m.main()
  self.assertEqual(self.phy.read_text(),'1\n');self.assertEqual(self.reports,[])
 def test_concurrent_reset_declined(self):
  with open(self.lock,'a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with patch.object(m.time,'sleep') as sleep:m.main();sleep.assert_not_called()
  self.assertEqual(self.phy.read_text(),'ready');self.assertEqual(self.reports,[(m.MESSAGES[30001],False)])
 def test_check_does_not_reset_or_lock(self):
  with patch.object(sys,'argv',['default.py','--check']),patch.object(m.time,'sleep') as sleep:m.main();sleep.assert_not_called()
  self.assertEqual(self.phy.read_text(),'ready');self.assertFalse(self.lock.exists());self.assertEqual(self.reports,[(m.MESSAGES[30003],False)])
 def test_unavailable_control(self):
  self.phy.unlink()
  with self.assertRaises(OSError):m.main()
  self.assertFalse(self.lock.exists())
 def test_nonwritable_control(self):
  with patch.object(m.os,'access',return_value=False):
   with self.assertRaises(OSError):m.main()
  self.assertFalse(self.lock.exists());self.assertEqual(self.phy.read_text(),'ready')
 def test_restore_failure_is_not_reported_as_success(self):
  normal_open=open
  def opened(path,mode='r',*a,**kw):
   if str(path)==str(self.phy) and mode=='w' and self.phy.read_text()=='0\n':raise OSError('simulated enable failure')
   return normal_open(path,mode,*a,**kw)
  with patch.object(m.time,'sleep'),patch('builtins.open',side_effect=opened):
   with self.assertRaises(OSError):m.main()
  self.assertEqual(self.reports,[])
class LockPaths(unittest.TestCase):
 def test_kodi_and_installed_cli_match(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp)/'kodi';kodi=types.SimpleNamespace(translatePath=lambda p:str(root/'temp'))
   with patch.dict(sys.modules,{'xbmcvfs':kodi}):from_kodi=m.lock_path()
   with patch.dict(sys.modules,{'xbmcvfs':None}),patch.object(m,'__file__',str(root/'addons/script.hdmi.reset/default.py')):from_cli=m.lock_path()
   self.assertEqual(from_cli,from_kodi);self.assertTrue((root/'temp').is_dir())
unittest.main()
