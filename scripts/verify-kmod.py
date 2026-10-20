import pathlib as P,plistlib,subprocess,struct
root=P.Path(__file__).resolve().parent.parent;bundle=root/'build/RealtekBluetoothCompat.kext';p=(bundle/'Contents/MacOS/RealtekBluetoothCompat').read_bytes()
sections=[];pos=32
for i in range(struct.unpack_from('<I',p,16)[0]):
 cmd,size=struct.unpack_from('<II',p,pos)
 if cmd==0x19:
  vm,vs,fo,fs=struct.unpack_from('<QQQQ',p,pos+24);sections.append((vm,vs,fo,fs))
 pos+=size
symbols={}
for line in subprocess.check_output(['xcrun','nm',str(bundle/'Contents/MacOS/RealtekBluetoothCompat')],text=True).splitlines():
 words=line.split()
 if len(words)==3:symbols[words[2]]=int(words[0],16)
def read(va,n):
 for vm,vs,fo,fs in sections:
  if vm<=va and va+n<=vm+fs:return p[fo+va-vm:fo+va-vm+n]
 raise ValueError(hex(va))
ki=symbols['_kmod_info']
assert struct.unpack('<Q',read(ki+180,8))[0]==symbols['__start']
assert struct.unpack('<Q',read(ki+188,8))[0]==symbols['__stop']
assert struct.unpack('<Q',read(symbols['__realmain'],8))[0]==symbols['_RealtekBluetoothCompat_kern_start']
assert struct.unpack('<Q',read(symbols['__antimain'],8))[0]==symbols['_RealtekBluetoothCompat_kern_stop']
print('PASS: kmod wrapper and real start/stop pointer audit.')
