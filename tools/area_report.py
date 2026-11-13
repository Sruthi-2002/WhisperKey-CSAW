#!/usr/bin/env python3
"""Synthesize golden vs trojaned RTL with Yosys and report the Trojan's area overhead.
Run: python3 tools/area_report.py   (writes reports/area_overhead.txt)"""
import os, re, subprocess
HERE=os.path.dirname(os.path.abspath(__file__)); RTL=os.path.join(HERE,"..","rtl")
REP=os.path.join(HERE,"..","reports","area_overhead.txt")
def synth(mod):
    ys=f"read_verilog -sv les_crypto_{mod}.v\nhierarchy -top les_crypto_{mod}\nsynth -flatten\nstat\n"
    open(f"/tmp/_s_{mod}.ys","w").write(ys)
    out=subprocess.run(["yosys","-s",f"/tmp/_s_{mod}.ys"],cwd=RTL,capture_output=True,text=True).stdout
    cells=int(re.search(r"Number of cells:\s+(\d+)",out).group(1))
    wb=int(re.search(r"Number of wire bits:\s+(\d+)",out).group(1))
    ff=sum(int(n) for n in re.findall(r"\$_[S]?DFF\w*\s+(\d+)",out))
    return cells,wb,ff,out
g=synth("golden"); t=synth("trojan")
lines=[]
lines.append("WhisperKey - synthesized area overhead (Yosys 0.33, generic cells)\n")
lines.append(f"{'metric':<14}{'golden':>10}{'trojan':>10}{'overhead':>14}")
for name,i in [("cells",0),("wire bits",1),("flip-flops",2)]:
    d=t[i]-g[i]; pct=100.0*d/g[i] if g[i] else 0
    lines.append(f"{name:<14}{g[i]:>10}{t[i]:>10}{('+%d (+%.2f%%)'%(d,pct)):>14}")
lines.append("\nThe Trojan adds a 32-bit trigger comparator, a 32-bit 2:1 output mux, and the")
lines.append("'armed' flag register with its one-shot control. The overhead is a small fraction")
lines.append("of the design (which is dominated by the AES S-box lookup logic), consistent with")
lines.append("a stealthy Trojan.")
open(REP,"w").write("\n".join(lines)+"\n")
print("\n".join(lines))
print("\nwritten:",os.path.relpath(REP))
