#!/usr/bin/env python3
"""Generate build-pinned, ASLR-independent bluetoothd memory patches."""
import hashlib,json,pathlib,struct,subprocess,re,argparse
root=pathlib.Path(__file__).resolve().parent
(root/'generated').mkdir(exist_ok=True)
parser=argparse.ArgumentParser()
parser.add_argument('--binary',default='/usr/sbin/bluetoothd',help='Matching local Apple binary (never uploaded)')
args=parser.parse_args()
binary=bytearray(pathlib.Path(args.binary).read_bytes())
expected_cdhash='be939612ec41703dbe1c6f8d004599ebf0e335c0'
observed_sha256=hashlib.sha256(binary).hexdigest()
assert binary[:4]==bytes.fromhex('cafebabe')
for i in range(struct.unpack_from('>I',binary,4)[0]):
 cpu,sub,off,size,align=struct.unpack_from('>IIIII',binary,8+20*i)
 if cpu==0x1000007:break
else:raise AssertionError('No x86_64 slice')
p=binary[off:off+size]
header_end=32+struct.unpack_from('<I',p,20)[0]
assert header_end==0x2440
# This verified zero-filled gap is after every Mach load command and before __text.
cave=0x2440;trampoline=0x2510;random_address=0x2530;entry=0x146814
original=bytes.fromhex('554889e5415741564154534881ec20010000')
hook=(root/'dispatcher-hook-template.bin').read_bytes()
assert len(hook)==200
ptr=struct.pack('<Q',0x1122334455667788);adr=struct.pack('<Q',0x8877665544332211)
def relative(op,at,target):return op+struct.pack('<i',target-(at+len(op)+4))
# Keep instruction lengths: replace absolute movabs by RIP-relative LEA + three NOPs.
for token,prefix,lea,target in [(adr,b'\x48\xba',b'\x48\x8d\x15',random_address),(ptr,b'\x49\xbb',b'\x4c\x8d\x1d',trampoline)]:
 at=hook.index(prefix+token)
 hook=hook[:at]+relative(lea,cave+at,target)+b'\x90'*3+hook[at+10:]
assert hook[-14:-8]==bytes.fromhex('ff2500000000') and hook[-8:]==ptr
hook=hook[:-14]+relative(b'\xe9',cave+len(hook)-14,trampoline)+b'\x90'*9
payload=bytearray(random_address+6-cave)
payload[:len(hook)]=hook
tramp=original+relative(b'\xe9',trampoline+len(original),entry+len(original))
payload[trampoline-cave:trampoline-cave+len(tramp)]=tramp
assert cave+len(payload)<0x2550
patches=[('payload',cave,bytes(payload)),('optional-page2',0x14493d,b'\xff'),('dispatcher',entry,relative(b'\xe9',entry,cave)+b'\x90'*13),('baseline-phy',0x1e4f39,b'\xeb')]
# An active code-validation plugin can leave its exact patches in the UBC cache.
# Normalize only our four known ranges in this temporary buffer, then require the
# original signed-page hashes bound to the exact CodeDirectory. Never write
# to the executable or accept unknown code/signature data.
original_ranges=[bytes(len(payload)),b'\x0c',original,b'\x74']
normalized=0
for (name,addr,replacement),before in zip(patches,original_ranges):
 start=off+addr;current=bytes(binary[start:start+len(before)])
 if current==before:continue
 matches=current==replacement
 if name=='payload':
  matches=(current[:-6]==replacement[:-6] and len(current)==len(replacement)
           and current[-1]&0xc0==0xc0)
 assert matches,'Unexpected bytes at %s; use a clean matching local binary'%name
 binary[start:start+len(before)]=before;normalized+=1
# Identify the native CodeDirectory directly; the active UBC cache can also
# contain unrelated BlueToolFixup patches, making whole-file read hashes unstable.
# Its exact hash plus original signed-page hashes are authoritative for this patch.
pos=32;signature=None
for _ in range(struct.unpack_from('<I',p,16)[0]):
 cmd,length=struct.unpack_from('<II',p,pos)
 assert length>=8 and pos+length<=header_end
 if cmd==0x1d:
  dataoff,datasize=struct.unpack_from('<II',p,pos+8)
  signature=bytes(p[dataoff:dataoff+datasize])
 pos+=length
assert signature is not None and len(signature)>=12,'No native code signature'
magic,total,count=struct.unpack_from('>III',signature)
assert magic==0xfade0cc0 and total<=len(signature)
code_directory=None
for index in range(count):
 kind,location=struct.unpack_from('>II',signature,12+index*8)
 magic,length=struct.unpack_from('>II',signature,location)
 if magic!=0xfade0c02:continue
 candidate=signature[location:location+length]
 if hashlib.sha256(candidate).hexdigest()[:40]==expected_cdhash:
  code_directory=candidate;break
assert code_directory is not None,'Unsupported native CodeDirectory hash'
hash_offset=struct.unpack_from('>I',code_directory,16)[0]
slots=struct.unpack_from('>I',code_directory,28)[0]
assert code_directory[36]==32 and code_directory[37]==2 and code_directory[39]==12
p=bytes(binary[off:off+size])
required_pages={0,0x1000,0x2000}|{address&~4095 for _,address,_ in patches}
for page in required_pages:
 slot=page//4096;assert slot<slots
 signed_hash=code_directory[hash_offset+slot*32:hash_offset+(slot+1)*32]
 assert len(signed_hash)==32 and hashlib.sha256(p[page:page+4096]).digest()==signed_hash, 'Unexpected signed page 0x%x'%page
p=bytes(binary[off:off+size])
assert p[cave:0x2550]==bytes(0x2550-cave)
assert p[entry:entry+18]==original
if normalized:print('Normalized %d known cache patches in a temporary buffer; exact CodeDirectory and signed pages verified.'%normalized)
cdhash=bytes.fromhex(expected_cdhash)
lines=['// Generated only from the exact supported local binary. Do not edit.','#pragma once']
def arr(name,value,mutable=False):
 lines.append(('static unsigned char ' if mutable else 'static const unsigned char ')+name+'[] = {')
 lines.extend('    '+','.join('0x%02x'%b for b in value[i:i+24])+',' for i in range(0,len(value),24))
 lines.append('};')
arr('supportedCDHash',cdhash)
for i,(name,addr,replacement) in enumerate(patches):
 page=addr&~4095
 arr('originalPage%d'%i,p[page:page+4096])
 arr('replacement%d'%i,replacement,i==0)
lines.append('static PatchSpec patchSpecs[] = {')
for i,(name,addr,replacement) in enumerate(patches):
 lines.append('    {0x%x, 0x%x, %d, originalPage%d, replacement%d, "%s"},'%(off+(addr&~4095),addr&4095,len(replacement),i,i,name))
lines.append('};')
(root/'generated/Patches.hpp').write_text('\n'.join(lines)+'\n')
(root/'generated/payload.bin').write_bytes(payload)
manifest={'observed_file_sha256':observed_sha256,'cdhash':cdhash.hex(),'slice_offset':off,'load_commands_end':header_end,'text_start':0x2550,'cave':cave,'trampoline':trampoline,'random_address':random_address,'entry':entry,'patches':[{'name':n,'offset':a,'original':p[a:a+len(r)].hex(),'replacement':r.hex()} for n,a,r in patches]}
(root/'generated/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Generated four build-pinned page patches locally; generated/ must not be committed.')
