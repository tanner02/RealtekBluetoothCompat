.text
.globl _compat_hook
_compat_hook:
 cmpl $0xab, %edi
 je Lsetup
 cmpl $0xd7, %edi
 jne Loriginal
Lsetup:
 pushq %rax
 pushq %rdi
 pushq %rsi
 pushq %rdx
 pushq %rcx
 pushq %r8
 pushq %r9
 pushq %r10
 pushq %r11
 subq $128, %rsp
 movdqu %xmm0, 0(%rsp)
 movdqu %xmm1, 16(%rsp)
 movdqu %xmm2, 32(%rsp)
 movdqu %xmm3, 48(%rsp)
 movdqu %xmm4, 64(%rsp)
 movdqu %xmm5, 80(%rsp)
 movdqu %xmm6, 96(%rsp)
 movdqu %xmm7, 112(%rsp)
 movl $0xa5, %edi
 xorl %esi, %esi
 movabsq $0x8877665544332211, %rdx
 movabsq $0x1122334455667788, %r11
 xorl %eax, %eax
 callq *%r11
 movdqu 0(%rsp), %xmm0
 movdqu 16(%rsp), %xmm1
 movdqu 32(%rsp), %xmm2
 movdqu 48(%rsp), %xmm3
 movdqu 64(%rsp), %xmm4
 movdqu 80(%rsp), %xmm5
 movdqu 96(%rsp), %xmm6
 movdqu 112(%rsp), %xmm7
 addq $128, %rsp
 popq %r11
 popq %r10
 popq %r9
 popq %r8
 popq %rcx
 popq %rdx
 popq %rsi
 popq %rdi
 popq %rax
Loriginal:
 .byte 0xff,0x25,0,0,0,0
 .quad 0x1122334455667788
