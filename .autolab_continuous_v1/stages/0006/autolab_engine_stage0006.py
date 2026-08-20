from pathlib import Path
import subprocess, shutil, time, os, re

B=Path(r"C:\dev_EA_MT5")
R=Path(r"C:\MT5_AutoLab_Runner")
TERM=R/"terminal64.exe"
RMQL=R/"MQL5"
REA=RMQL/"Experts"/"AutoLab"
RR=R/"reports"

LIVE_MQL5=Path(r"C:\Users\Daffy\AppData\Roaming\MetaQuotes\Terminal\9B101088254A9C260A9790D5079A7B11\MQL5")
LIVE_EA_DIR=LIVE_MQL5/"Experts"/"AutoLab"
LIVE_METAEDITOR=Path(r"C:\Program Files\Ava Trade MT5 Terminal\metaeditor64.exe")

A=B/"autolab"/"v0.21.1.1"
E=B/"experiments"/"v0.21.1.1"
REP=B/"reports"
LOG=B/"logs"
CFG=B/"config"
CAND=A/"autolab_candidate.mq5"
MASTER=LOG/"AUTOLAB_V02111.log"

for d in (REA,RR,A,E,REP,LOG,CFG,LIVE_EA_DIR):
    d.mkdir(parents=True,exist_ok=True)

def stamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log(s=""):
    x=f"[{stamp()}] {s}" if s else ""
    print(x,flush=True)
    with MASTER.open("a",encoding="utf-8") as f: f.write(x+"\n")

def run(args,cwd=None,timeout=None):
    log("EXEC: "+" ".join(map(str,args)))
    return subprocess.run(list(map(str,args)),cwd=str(cwd) if cwd else None,
        capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)

def killrunner():
    ps=("$p=Get-CimInstance Win32_Process|?{$_.Name -eq 'terminal64.exe' -and "
        "$_.ExecutablePath -eq 'C:\\MT5_AutoLab_Runner\\terminal64.exe'};"
        "$p|%{Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}")
    subprocess.run(["powershell.exe","-NoProfile","-Command",ps],capture_output=True)

def read_compile_log(path):
    raw=path.read_bytes()
    for enc in ("utf-16","utf-16-le","utf-8-sig","utf-8","cp1252","latin-1"):
        try: return raw.decode(enc)
        except Exception: pass
    return raw.decode("utf-8",errors="replace")

def compile_ea(ed):
    ed.mkdir(parents=True,exist_ok=True)
    live_mq5=LIVE_EA_DIR/"autolab_candidate.mq5"
    live_ex5=LIVE_EA_DIR/"autolab_candidate.ex5"
    live_log=LIVE_EA_DIR/"autolab_candidate.log"
    for p in (live_ex5,live_log):
        try:p.unlink()
        except FileNotFoundError:pass
    shutil.copy2(CAND,live_mq5)
    p=run([LIVE_METAEDITOR,f"/compile:{live_mq5}",f"/include:{LIVE_MQL5}","/log"],LIVE_METAEDITOR.parent,180)
    end=time.time()+30
    while time.time()<end and not live_log.exists(): time.sleep(.25)
    txt=read_compile_log(live_log) if live_log.exists() else ""
    (ed/"compile.log").write_text(
        f"MetaEditor={LIVE_METAEDITOR}\nEX5_exists={live_ex5.exists()}\nProcess_returncode={p.returncode}\n\n{txt or '[AUCUN LOG]'}",
        encoding="utf-8")
    if live_log.exists(): shutil.copy2(live_log,ed/"compile_raw.log")
    if not (live_ex5.exists() and re.search(r"Result:\s*0 errors?",txt,re.I)):
        raise RuntimeError("Compilation MQL5 impossible: "+str(ed/"compile.log"))
    shutil.copy2(CAND,ed/"candidate.mq5")
    shutil.copy2(live_ex5,ed/"candidate.ex5")
    shutil.copy2(CAND,REA/"autolab_candidate.mq5")
    shutil.copy2(live_ex5,REA/"autolab_candidate.ex5")
    log(f"Compilation {ed.name}: OK")

def safe_name(x):
    return re.sub(r"[^A-Za-z0-9_-]+","_",x)

def run_tester(c,phase,ed,date_from,date_to,symbol=None,model=None,timeout=None):
    killrunner(); time.sleep(.5)
    phase=safe_name(phase)
    sym=symbol or c["catalog_probe_symbol"]
    mod=c["extraction_model"] if model is None else model
    stem=f"AUTOLAB_V02111_{phase.upper()}"
    rr=RR/(stem+".htm")
    ini=CFG/f"autolab_v02111_{phase}.ini"
    try: rr.unlink()
    except FileNotFoundError: pass
    ini.write_text(f"""[Common]
NewsEnable=0
KeepPrivate=1

[Experts]
Enabled=0
AllowLiveTrading=0
AllowDllImport=0
Account=0
Profile=0

[Tester]
Expert=AutoLab\\autolab_candidate
Symbol={sym}
Period=H1
Model={mod}
ExecutionMode=0
Optimization=0
FromDate={date_from}
ToDate={date_to}
Report=reports\\{stem}
ReplaceReport=1
ShutdownTerminal=1
Deposit=1000
Currency=EUR
Leverage=1:400
UseLocal=1
UseRemote=0
UseCloud=0
Visual=0
""",encoding="ascii",errors="ignore")
    p=subprocess.Popen([str(TERM),"/portable",f"/config:{ini}"],cwd=str(R))
    try: p.wait(timeout=int(timeout or c["tester_timeout_seconds"]))
    except subprocess.TimeoutExpired:
        p.kill(); killrunner(); raise RuntimeError("Timeout Strategy Tester: "+phase)
    time.sleep(1)
    if not rr.exists(): raise RuntimeError("Rapport Strategy Tester absent: "+phase)
    ed.mkdir(parents=True,exist_ok=True)
    shutil.copy2(rr,ed/"tester_report.htm")
    shutil.copy2(ini,ed/ini.name)
    log(f"Tester {phase}: OK ({rr.stat().st_size} octets) | {sym} | Model={mod}")
