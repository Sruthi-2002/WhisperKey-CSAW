#!/usr/bin/env python3
"""
WhisperKey attacker console  -  interactive exploit demo.

An interactive front-end that plays the role of the SPI controller (RP2040)
talking to the trojaned FPGA.  You type 32-bit words; the console shows the
chip's response.  Ordinary words come back as ciphertext; the one secret
trigger word makes the chip leak its embedded key over MISO.

The cipher model here is the SAME one implemented in rtl/les_crypto_golden.v
(verified bit-for-bit against the hardware simulation and the challenge test
vector 0x59C359C3 -> 0x9CD84392), so what you see matches the real chip.

Run:  python3 attack_console.py
"""
import sys

# ---- recovered LES cipher (mirrors the RTL) --------------------------------
_T = ("637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0"
      "b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
      "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf"
      "d0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2"
      "cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb"
      "e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08"
      "ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e"
      "e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16")
SB  = [int(_T[i*2:i*2+2], 16) for i in range(256)]
INV = [0]*256
for _i, _v in enumerate(SB): INV[_v] = _i
M = 0xFFFFFFFF

KEY     = 0x8E043CB1     # embedded key (the attacker is trying to steal this)
TRIGGER = 0x1337C0DE     # WhisperKey secret trigger

def _sub(x, b): return (b[(x>>24)&255]<<24)|(b[(x>>16)&255]<<16)|(b[(x>>8)&255]<<8)|b[x&255]
def _rotl8(x):  return ((x<<8)|(x>>24)) & M
def _rotr8(x):  return ((x>>8)|(x<<24)) & M

def encrypt(word):
    """One encrypt operation: 4 rounds of SBox(ROTL8(x ^ K))."""
    x = word
    for _ in range(4):
        x = _sub(_rotl8(x ^ KEY), SB)
    return x & M

def decrypt(word, key):
    """Inverse of encrypt using a (stolen) key: 4 rounds of ROTR8(InvSBox(y)) ^ K."""
    y = word
    for _ in range(4):
        y = _rotr8(_sub(y, INV)) ^ key
    return y & M

def chip_response(word):
    """Model of the TROJANED chip: leak the key on the trigger, else encrypt."""
    if word == TRIGGER:
        return KEY, True
    return encrypt(word), False

BANNER = r"""
  _ _ _ _     _                _   __
 | | | | |_ _| |_ ___ ___ ___ | |_|  |_ ___ _ _
 | | | |   | |_|_ -| . | -_|  _| '_|  _| -_| | |
 |_____|_|_|_|_|___|  _|___|_| |_,_|___|___|_  |
                   |_|                     |___|   attacker console
   target: 32-bit LES SPI crypto accelerator (trojaned)
"""

def show(word, resp, leaked):
    print(f"   SPI  MOSI (in)  : 0x{word:08X}")
    if leaked:
        print(f"   SPI  MISO (out) : 0x{resp:08X}")
        print(f"   >>> TRIGGER MATCHED - chip leaked its KEY: 0x{resp:08X} <<<")
        print(f"       the encryption key is now compromised; all traffic can be decrypted.")
    else:
        print(f"   SPI  MISO (out) : 0x{resp:08X}   (ciphertext - normal operation)")

def main():
    print(BANNER)
    print("Type a 32-bit hex word to send to the chip (e.g. 59C359C3), or:")
    print("  t = send the secret trigger   d <hex> = decrypt a value with the leaked key")
    print("  v = run the known test vector   q = quit\n")
    leaked_key = None
    while True:
        try:
            cmd = input("MOSI> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not cmd: continue
        c = cmd.lower()
        if c in ("q", "quit", "exit"): break
        if c == "t":
            word = TRIGGER
        elif c == "v":
            word = 0x59C359C3
        elif c.startswith("d "):
            if leaked_key is None:
                print("   (leak the key first with 't')\n"); continue
            try: val = int(c.split()[1], 16)
            except Exception: print("   bad hex\n"); continue
            y = decrypt(val, leaked_key)
            print(f"   decrypt 0x{val:08X} with stolen key 0x{leaked_key:08X} -> 0x{y:08X}\n")
            continue
        else:
            try: word = int(c, 16) & M
            except Exception: print("   enter 8 hex digits, or t / v / d <hex> / q\n"); continue
        resp, leaked = chip_response(word)
        show(word, resp, leaked)
        if leaked: leaked_key = resp
        print()
    print("bye.")

if __name__ == "__main__":
    main()
