#!/usr/bin/env python3
"""Verify the checked-in project-owned assembly template."""
import pathlib,struct,subprocess,tempfile
root=pathlib.Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as directory:
 obj=pathlib.Path(directory)/'hook.o'
 subprocess.run(['xcrun','clang','-arch','x86_64','-c',str(root/'dispatcher-hook-template.s'),'-o',str(obj)],check=True)
 p=obj.read_bytes();pos=32;found=None
 for _ in range(struct.unpack_from('<I',p,16)[0]):
  cmd,size=struct.unpack_from('<II',p,pos)
  if cmd==0x19:
   for j in range(struct.unpack_from('<I',p,pos+64)[0]):
    sec=pos+72+80*j
    if p[sec:sec+16].rstrip(b'\0')==b'__text':
     length,offset=struct.unpack_from('<QI',p,sec+40);found=p[offset:offset+length]
  pos+=size
 assert found== (root/'dispatcher-hook-template.bin').read_bytes(), 'Assembly template differs'
 print('PASS: assembly template reproduces the 200-byte checked-in payload.')
