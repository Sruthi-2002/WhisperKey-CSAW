# WhisperKey — an AI-generated key-exfiltration hardware Trojan

**CSAW AI Hardware Attack Challenge 2026 — Preliminary (qualifier) submission**
Sruthi Raghavan (sr7892) · GenAI-Based Chip Design (ECE-GY 9941)

WhisperKey is a stealthy hardware Trojan inserted into the challenge's 32-bit "LES"
SPI cryptographic accelerator. The accelerator works perfectly under normal use, but
when a secret 32-bit *trigger* word is sent over SPI, the Trojan loads the embedded
secret key onto the output path, exfiltrating it over the **MISO** line. The entire
Trojan and exploit were produced with an LLM; a one-command pipeline regenerates and
verifies the whole attack.

---

## 1. Threat model

The attacker is an **insider in the FPGA design/supply chain** — a malicious IP
vendor, an engineer, or an untrusted synthesis/bitstream step — who can modify the
accelerator's RTL before deployment. The modification must (a) survive normal
functional testing, and (b) let anyone who knows the secret trigger recover the key
later, over the device's ordinary interface. The defender runs standard functional
vectors but does not know the trigger. This matches real supply-chain Trojan concerns
for cryptographic IP (bank cards, secure elements, embedded crypto).

---

## 2. Reverse engineering the bitstream

The source RTL was not provided — only the bitstream, the interface doc
(`ice40_cryptographic_IP.md`), the MicroPython driver, and the block diagrams
(`docs/les_block_diagrams`). My method:

1. **Structure from the interface + diagrams.** The diagrams show a 32-bit SPI shift
   register, two crypto cores (encrypt/decrypt) and a 2-bit round-controller FSM
   (`IDLE→R1→R2→R3`), with `BUSY` falling when the result is parallel-loaded for
   readback. I reconstructed this datapath in `rtl/les_crypto_golden.v`.

2. **Cipher recovery by matching the known test vector.** The driver gives one known
   pair: plaintext `0x59C359C3` → ciphertext `0x9CD84392` (encrypt mode). The diagrams
   indicate a 4-round structure using byte-wise AES S-box substitution, an 8-bit byte
   rotation, and a per-round XOR with a fixed key `K`. I searched the small space of
   round structures (S-box vs inverse S-box, rotate direction, operation order, key-XOR
   position, byte endianness) and, for each, brute-forced all 2³² keys to find which
   `(structure, key)` reproduces the vector (`tools/key_recovery.c`).

3. **Result.** The recovered encrypt round is
   `x ← SBox( ROTL8( x ⊕ K ) )`, applied 4 times, ciphertext = x₄, with the
   recovered key below. Decrypt is the exact inverse,
   `y ← ROTR8( InvSBox(y) ) ⊕ K`. The reconstructed RTL reproduces the test vector in
   simulation and round-trips encrypt/decrypt (`tb/tb_golden_vector.v`).

### How the encryption works (recovered)

- 32-bit block, **4 identical rounds**, one fixed 32-bit key `K` (no key schedule).
- Each round: XOR the state with `K`, rotate the 32-bit word left by one byte (ROTL8),
  then substitute each of the 4 bytes through the AES S-box.
- The SPI shift register is clocked directly by `SCK` (unified clock domain, ≤1 MHz),
  MSB-first; the FSM runs the 4 rounds while `BUSY` is high and parallel-loads the
  result on the falling edge of `BUSY`.

### Recovered key (bonus)

**`K = 0x8E043CB1`.** The brute-force search over the round structure finds this key
**uniquely** for the recovered structure: it reproduces the published test vector exactly
(`encrypt(0x59C359C3) = 0x9CD84392`, and `decrypt(0x9CD84392) = 0x59C359C3`). It also
**matches the key value annotated in the provided block diagrams** (`docs/les_block_diagrams`),
confirming the recovery independently.

---

## 3. How the AI was used

- **Model / access:** Claude (Sonnet-class) via the NYU Portkey gateway (OpenAI-compatible
  chat API), the same gateway used elsewhere in the course. Interaction was through a
  conversational UI plus a scripted insertion/test wrapper.
- **Pipeline, not copy-paste.** The attack is produced by a staged flow:
  1. *Analyze* — the model is given the recovered RTL and the interface and asked to
     locate the output parallel-load path and the key register.
  2. *Generate* — the model emits the WhisperKey Trojan logic (trigger comparator +
     output mux) as Verilog.
  3. *Insert* — `tools/pipeline.py` splices the generated Trojan into the golden RTL at
     named structural anchors (module header, the shift-register load statement, and the
     `round()` function boundary) — automated insertion, no hand-editing of the trojaned
     file.
  4. *Test* — the pipeline compiles golden + trojaned RTL with the exploit testbench and
     feeds the pass/fail (and any simulator errors) back to the model to refine.
- **One command** reproduces generate→insert→simulate→verify:
  `python3 tools/pipeline.py`.
- Full prompt/response transcripts are in [`ai/`](ai/).

---

## 4. The WhisperKey Trojan

### Trigger
A single, exact 32-bit input word, `TRIGGER = 0x1337C0DE`, compared against the latched
SPI input word. False-trigger probability under random traffic is 2⁻³² (~1 in 4.3 billion),
so it never fires during normal operation.

### Payload
On a trigger match, a flag `armed` is set; it steers a 32-bit 2:1 mux on the shift
register's parallel-load input to load the **key register `K`** instead of the ciphertext.
The key then shifts out over **MISO** on the next readback. It is a one-shot (auto-disarms
after the leak) to minimise its footprint in traces.

### Stealth
- **Functionally transparent:** when not triggered, `load_value == result`, so the output
  is **bit-for-bit identical** to the clean design. `tb/tb_exploit.v` proves this against a
  batch of ordinary inputs by running the golden and trojaned chips in parallel.
- **Negligible area:** one 1-bit flag + one 32-bit 2:1 mux + a 32-bit comparator.
- **No new interface:** the leak reuses the existing MISO output; no added ports or pins.

### Taxonomy (per the standard hardware-Trojan classification)
- **Insertion phase:** design (RTL).
- **Abstraction level:** register-transfer level.
- **Activation:** conditionally triggered, **digital**, **externally** activated by a
  specific input value (not always-on, not time-based).
- **Effect / payload:** **information leakage** (key exfiltration) via an existing output
  channel — it does not change the normal functional result.
- **Location:** the crypto core's output / SPI readback path.

---

## 5. Exploit (reproducible in hardware)

Once a bitstream is generated from `rtl/les_crypto_trojan.v`:

1. Follow the normal driver sequence (`spi_ice40_crypto_ip_test.py`): reset, then clock
   the **trigger word `0x1337C0DE`** in over MOSI (MSB-first, `ENC_DEC=0`), drive
   `NORM_CS_N` high to latch it.
2. Pulse `START`; wait for `BUSY` to fall (4 clocks).
3. Clock out 32 bits over MISO — the bits returned are the **key `0x8E043CB1`**, not a
   ciphertext.
4. With the key, decrypt any captured ciphertext offline (the recovered decrypt routine,
   demonstrated in `tools/attack_console.py`).

The interactive `tools/attack_console.py` plays the SPI controller: send ordinary words
(get ciphertext), send `t` (the trigger → the key leaks), then `d <ciphertext>` to decrypt
captured traffic with the stolen key.

---

## 6. Two insertion techniques

The Trojan is inserted two independent ways, both automated and both verified:

- **Text/anchor pipeline** (`tools/pipeline.py`) — splices the AI-generated Trojan into
  the golden RTL at named structural anchors, then compiles and runs the exploit test.
- **AST transformation** (`tools/ast_insert.py`) — parses the golden RTL into a Verilog
  abstract syntax tree (pyverilog), grafts the Trojan nodes, rewrites the output-load
  statement's RHS at the AST level (`result → load_value`), and regenerates Verilog.
  This is the "advanced technique (AST manipulation)" path; the generated
  `rtl/les_crypto_trojan_ast.v` passes the same exploit/stealth checks.

## 7. Evidence / reports

- **Stealth, formally shown in simulation** — `tb/tb_exploit.v` runs the clean and
  trojaned chips in parallel and asserts bit-identical outputs for a batch of inputs.
- **Synthesized area overhead** (`reports/area_overhead.txt`, via `tools/area_report.py`
  + Yosys): the Trojan adds **+159 cells (+3.9%)** — a small fraction of the design, which
  is dominated by the AES S-box lookup logic.
- **Waveform** (`reports/waveform_exploit.png`, via `tools/render_waveform.py`): a clear
  digital timing diagram of the trigger run, with the 32 MISO bits of the leaked key
  highlighted.

## 7b. Interactive attack lab

`demo/index.html` is a self-contained, in-browser model of the trojaned accelerator
(open it in any web browser, no build step). It implements the recovered cipher in
JavaScript and lets you run the full attack interactively: encrypt normally, send the
trigger `0x1337C0DE` to arm the Trojan and watch the key `0x8E043CB1` shift out over
MISO bit-by-bit, then decrypt captured traffic with the stolen key. The page self-checks
its cipher against the challenge test vector on load.

## 8. Repository layout

```
submission/
├── README.md                     this technical brief
├── Makefile                      one-command build/verify (make, make area, make wave ...)
├── rtl/
│   ├── les_crypto_golden.v       recovered clean accelerator (reference)
│   ├── les_crypto_trojan.v       trojaned RTL (WhisperKey inserted)   <-- the deliverable
│   ├── les_crypto_trojan_ast.v   same Trojan, produced via AST transform
│   └── sbox.hex, isbox.hex       AES S-box tables
├── tb/
│   ├── tb_golden_vector.v        validates recovery vs the known test vector
│   ├── tb_exploit.v              proves stealth (golden==trojan) + the key leak
│   └── tb_wave.v                 focused capture of the leak readback (for the waveform)
├── tools/
│   ├── pipeline.py               one-click generate -> insert -> simulate -> verify
│   ├── ast_insert.py             AST-level Trojan insertion (pyverilog)
│   ├── area_report.py            Yosys area-overhead report
│   ├── render_waveform.py        renders reports/waveform_exploit.png
│   ├── attack_console.py         interactive attacker console (SPI controller role)
│   └── key_recovery.c            brute-force cipher/key recovery from the test vector
├── reports/
│   ├── area_overhead.txt         synthesized overhead (golden vs trojan)
│   └── waveform_exploit.png      rendered key-leak waveform
├── demo/
│   └── index.html                interactive in-browser attack lab (open in a browser)
└── ai/                           LLM prompt/response transcripts
```

## 9. How to run

```
make            # regenerate the Trojan and verify stealth + exploit  (one command)
make vector     # validate the recovered cipher vs the known test vector
make exploit    # run only the exploit/stealth testbench
make ast        # AST-based insertion -> rtl/les_crypto_trojan_ast.v
make area       # synthesized area-overhead report (needs Yosys)
make wave       # render the key-leak waveform (needs matplotlib)
make console    # interactive attacker console
```

Expected: the known vector passes, trojaned output is identical to the clean chip for
ordinary inputs, and the trigger `0x1337C0DE` leaks the key `0x8E043CB1` over MISO.

Requires Icarus Verilog (`iverilog`/`vvp`) and Python 3; the AST, area, and waveform
steps additionally use `pyverilog`, `yosys`, and `matplotlib`. No API keys or credentials
are stored in this repository.
