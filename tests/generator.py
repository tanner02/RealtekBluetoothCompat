#!/usr/bin/env python3
"""Check local cache normalization and rejection of unknown code/signature data."""
import pathlib,struct,subprocess,sys,tempfile,json
root=pathlib.Path(__file__).resolve().parent.parent
binary=bytearray(pathlib.Path('/usr/sbin/bluetoothd').read_bytes())
for i in range(struct.unpack_from('>I',binary,4)[0]):
 cpu,sub,off,size,alignment=struct.unpack_from('>IIIII',binary,8+20*i)
 if cpu==0x1000007:break
else:raise AssertionError('No native x86_64 slice')
with tempfile.TemporaryDirectory() as directory:
 fixture=pathlib.Path(directory)/'bluetoothd'
 def run(data,success):
  fixture.write_bytes(data)
  p=subprocess.run([sys.executable,str(root/'generate.py'),'--binary',str(fixture)],capture_output=True,text=True)
  assert (p.returncode==0)==success,p.stdout+p.stderr
 # Valid original or known cache-patched pages must produce the same local fixtures.
 run(binary,True)
 before=(root/'generated/Patches.hpp').read_bytes()
 clean=bytearray(binary)
 manifest=json.loads((root/'generated/manifest.json').read_text())
 for spec in manifest['patches']:
  address=spec['offset'];original=bytes.fromhex(spec['original'])
  clean[off+address:off+address+len(original)]=original
 run(clean,True)
 assert (root/'generated/Patches.hpp').read_bytes()==before
 # The new cache layout must also regenerate identical original signed pages.
 manifest=json.loads((root/'generated/manifest.json').read_text())
 patched=bytearray(clean)
 for spec in manifest['patches']:
  replacement=bytearray.fromhex(spec['replacement'])
  if spec['name']=='payload':replacement[-6:]=bytes([1,2,3,4,5,0xc6])
  at=off+spec['offset'];patched[at:at+len(replacement)]=replacement
 run(patched,True)
 assert (root/'generated/Patches.hpp').read_bytes()==before
 # Tampering outside the known replacement range must fail a signed-page check.
 changed=bytearray(clean);changed[off+(manifest['entry']&~4095)+0x300]^=1;run(changed,False)
 # Unknown code at a replacement site must not be normalized.
 changed=bytearray(clean);changed[off+manifest['cave']]=0xcc;run(changed,False)
 assert (root/'generated/Patches.hpp').read_bytes()==before
print('PASS: known cache/original pages generate identical data; unknown patch/page changes rejected.')
