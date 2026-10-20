#!/usr/bin/env python3
"""Check local cache normalization and rejection of unknown code/signature data."""
import pathlib,struct,subprocess,sys,tempfile
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
 for address,original in ((0x2440,bytes(246)),(0x14493d,b'\x0c'),(0x146814,bytes.fromhex('554889e5415741564154534881ec20010000')),(0x1e4f39,b'\x74')):
  clean[off+address:off+address+len(original)]=original
 run(clean,True)
 assert (root/'generated/Patches.hpp').read_bytes()==before
 # Tampering outside the known replacement range must fail a signed-page check.
 changed=bytearray(clean);changed[off+0x146900]^=1;run(changed,False)
 # Unknown code at a replacement site must not be normalized.
 changed=bytearray(clean);changed[off+0x2440]=0xcc;run(changed,False)
 assert (root/'generated/Patches.hpp').read_bytes()==before
print('PASS: known cache/original pages generate identical data; unknown patch/page changes rejected.')
