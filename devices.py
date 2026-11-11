"""USB controllers supported by the local bluetoothd patch generator."""
DEVICES = {
    'rtl8852ce': {'vendor': 0x0bda, 'product': 0x0852, 'kernels': (24, 25)},
    'rtl8852b': {'vendor': 0x0cb8, 'product': 0xc559, 'kernels': (25,)},
}
