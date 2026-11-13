#!/usr/bin/env python3
"""
Render a clear digital-timing waveform of the WhisperKey key-leak readback.

Compiles and runs tb/tb_wave.v (which sends the trigger then clocks the key out
over MISO), parses the resulting wave.vcd, and plots SCK / NORM_CS_N / BUSY / MISO
to reports/waveform_exploit.png, annotating the 32 MISO bits that carry the key.

Run:  python3 tools/render_waveform.py
"""
import os, re, subprocess
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE=os.path.dirname(os.path.abspath(__file__)); RTL=os.path.join(HERE,"..","rtl")
TB=os.path.join(HERE,"..","tb"); REP=os.path.join(HERE,"..","reports")
os.makedirs(REP, exist_ok=True)

def build_run():
    exe=os.path.join(RTL,"sim_wave")
    subprocess.run(["iverilog","-g2012","-o",exe,os.path.join(RTL,"les_crypto_trojan.v"),
                    os.path.join(TB,"tb_wave.v")],cwd=RTL,check=True)
    subprocess.run(["vvp",exe],cwd=RTL,check=True)
    return os.path.join(RTL,"wave.vcd")

def parse_vcd(path, names):
    """Return {signal: [(time,value)]} for the requested 1-bit signals."""
    sym={}; want=set(names); series={n:[] for n in names}; t=0
    for line in open(path):
        line=line.strip()
        m=re.match(r"\$var\s+\w+\s+\d+\s+(\S+)\s+(\S+)",line)
        if m:
            code,nm=m.group(1),re.sub(r"\[.*","",m.group(2))
            if nm in want: sym[code]=nm
            continue
        if line.startswith("#"): t=int(line[1:]); continue
        if line and line[0] in "01":
            v,code=line[0],line[1:]
            if code in sym: series[sym[code]].append((t,int(v)))
    return series

def step(ax, data, tmax, label, y):
    if not data:
        ax.text(0,y+0.25,label,va="center",ha="right",fontsize=9); return
    xs=[0]; ys=[data[0][1]]
    for (tt,vv) in data:
        xs.append(tt); ys.append(ys[-1]); xs.append(tt); ys.append(vv)
    xs.append(tmax); ys.append(ys[-1])
    ax.plot(xs,[v*0.7+y for v in ys],drawstyle="steps-post",lw=1.4,color="#1f6feb")
    ax.text(-tmax*0.01,y+0.35,label,va="center",ha="right",fontsize=9,family="monospace")

def main():
    vcd=build_run()
    names=["SCK","NORM_CS_N","BUSY","MISO"]
    s=parse_vcd(vcd,names)
    tmax=max((d[-1][0] for d in s.values() if d), default=1000)+200
    fig,ax=plt.subplots(figsize=(11,3.4))
    for i,n in enumerate(names):
        step(ax,s[n],tmax,n,(len(names)-1-i)*1.2)
    # shade only the final readback window: from the last NORM_CS_N falling edge to end
    ncs=s["NORM_CS_N"]
    falls=[t for (t,v) in ncs if v==0]
    rises=[t for (t,v) in ncs if v==1]
    if falls:
        rb_start=falls[-1]
        rb_end=min([t for t in rises if t>rb_start], default=tmax-180)
        ax.axvspan(rb_start, rb_end, color="#ffd33d", alpha=0.22)
        ax.text((rb_start+rb_end)/2, len(names)*1.2-0.05,
                "key shifts out over MISO = 0x8E043CB1", ha="center",
                fontsize=9, color="#9a6700")
    ax.set_title("WhisperKey exploit - trigger sent, embedded key leaked over MISO",fontsize=11)
    ax.set_xlabel("time (ps)"); ax.set_yticks([]); ax.set_xlim(-tmax*0.06,tmax)
    ax.set_ylim(-0.4,len(names)*1.2+0.3)
    for sp in ("top","right","left"): ax.spines[sp].set_visible(False)
    plt.tight_layout()
    out=os.path.join(REP,"waveform_exploit.png")
    plt.savefig(out,dpi=130)
    for f in ("sim_wave","wave.vcd"):
        p=os.path.join(RTL,f);  os.path.exists(p) and os.remove(p)
    print("waveform written:",os.path.relpath(out))

if __name__=="__main__":
    main()
