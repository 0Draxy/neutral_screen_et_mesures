from pathlib import Path
import csv, json, math, statistics, hashlib, zipfile, subprocess, traceback
from datetime import datetime
from collections import defaultdict, deque

B=Path(r"C:\dev_EA_MT5")
DATA=B/"data"/"v0.21.1"
REP=B/"reports"; LOG=B/"logs"; A=B/"autolab"/"continuous_stage_0003"
PKG=Path(__file__).resolve().parent
for d in (REP,LOG,A): d.mkdir(parents=True,exist_ok=True)
STATUS=LOG/"AUTOLAB_STATUS_STAGE0003.txt"
MASTER=LOG/"AUTOLAB_STAGE0003.log"
ERROR=LOG/"AUTOLAB_STAGE0003_ERROR.txt"
RESULTS=REP/"AUTOLAB_STRUCTURAL_RESULTS_STAGE0003.csv"
TOP=REP/"AUTOLAB_STRUCTURAL_TOP20_STAGE0003.csv"
YEARLY=REP/"AUTOLAB_STRUCTURAL_YEARLY_STAGE0003.csv"
SUMMARY=REP/"AUTOLAB_SUMMARY_STAGE0003.txt"
FINAL=REP/"AUTOLAB_FINAL_STAGE0003.md"
HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0003_STRUCTURAL.zip"
MARKER=A/"UPLOAD_CONFIRMED.txt"
PROTOCOL=PKG/"RESEARCH_PROTOCOL_STAGE0003.json"
MANIFEST=PKG/"SOURCE_MANIFEST_V0211.csv"
PROTOCOL_SHA="457e61c76387d0abcef75c171834dc90a534efe87aae0074322b6673d748d558"
MANIFEST_SHA="463795c818acd2150dbfcb9406b7ce965a649cae0d9c3acc360a9984ac3818cf"

def stamp():return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def log(s):
    line=f"[{stamp()}] {s}";print(line,flush=True)
    with MASTER.open("a",encoding="utf-8") as f:f.write(line+"\n")
def status(phase,msg=""):
    STATUS.write_text(f"AutoLab Continuous V1 STAGE 0003\nDate: {stamp()}\nPhase: {phase}\nMessage: {msg}\n2019-2026=RESEARCH EXPOSEE\nLIVE=INTERDIT\n",encoding="utf-8")
def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1048576),b""):h.update(c)
    return h.hexdigest()
def rows(path):
    raw=Path(path).read_bytes()
    for enc in ("utf-8-sig","cp1252","latin-1"):
        try:return list(csv.DictReader(raw.decode(enc).splitlines(),delimiter=';'))
        except UnicodeDecodeError:pass
    raise RuntimeError("decode impossible "+str(path))
def verify():
    if sha(PROTOCOL)!=PROTOCOL_SHA:raise RuntimeError("protocol SHA mismatch")
    if sha(MANIFEST)!=MANIFEST_SHA:raise RuntimeError("manifest SHA mismatch")
    m=rows(MANIFEST)
    if len(m)!=23:raise RuntimeError(f"manifest attendu 23, obtenu {len(m)}")
    for r in m:
        p=DATA/(r["symbol"]+".csv")
        if not p.exists():raise RuntimeError("source absente "+str(p))
        if sha(p).lower()!=r["sha256"].lower():raise RuntimeError("source SHA mismatch "+r["symbol"])
    return m

def load(r):
    out=[]
    for x in rows(DATA/(r["symbol"]+".csv")):
        try:
            out.append({
              "dt":datetime.strptime(x["time"],"%Y.%m.%d %H:%M"),
              "o":float(x["open"].replace(",",".")),
              "h":float(x["high"].replace(",",".")),
              "l":float(x["low"].replace(",",".")),
              "c":float(x["close"].replace(",",".")),
              "sp":float(x["spread_points"].replace(",",".")),
              "pt":float(x["point"].replace(",","."))
            })
        except Exception:pass
    out.sort(key=lambda x:x["dt"])
    return out

def atr14(data):
    tr=[]
    for i,x in enumerate(data):
        pc=data[i-1]["c"] if i else x["c"]
        tr.append(max(x["h"]-x["l"],abs(x["h"]-pc),abs(x["l"]-pc)))
    out=[None]*len(data);s=0.0;q=deque()
    for i,v in enumerate(tr):
        q.append(v);s+=v
        if len(q)>14:s-=q.popleft()
        if len(q)==14:out[i]=s/14
    return out

def hypotheses():
    H=[]
    for lb in (2,5,10,20):
      for hold in (24,72):
        H.append(("daily_tsmom",lb,hold,None))
        H.append(("daily_tsreversal",lb,hold,None))
    for lb in (3,6,12):
      for th in (0.75,1.25):
       for hold in (4,8,24):
        H.append(("impulse_momentum",lb,hold,th))
        H.append(("impulse_reversal",lb,hold,th))
    for lb in (48,120):
      for edge in (0.15,0.25):
       for hold in (8,24):
        H.append(("range_position_momentum",lb,hold,edge))
        H.append(("range_position_reversal",lb,hold,edge))
    assert len(H)==68
    return H

def make_events(meta,data,atr,h):
    fam,lb,hold,p=h
    ev=[];next_allowed=0
    if fam.startswith("daily_"):
        look=lb*24
    else:look=lb
    for i in range(max(250,look+5),len(data)-hold-2):
        if i<next_allowed:continue
        y=data[i]["dt"].year
        if y<2019 or y>2026 or atr[i] is None or atr[i]<=0:continue
        d=None
        if fam.startswith("daily_"):
            past=data[i]["c"]-data[i-look]["c"]
            if past>0:d="LONG"
            elif past<0:d="SHORT"
            if fam=="daily_tsreversal" and d:d="SHORT" if d=="LONG" else "LONG"
        elif fam.startswith("impulse_"):
            move=data[i]["c"]-data[i-lb]["c"]
            if abs(move) < p*atr[i]:continue
            d="LONG" if move>0 else "SHORT"
            if fam=="impulse_reversal":d="SHORT" if d=="LONG" else "LONG"
        elif fam.startswith("range_position_"):
            hs=max(x["h"] for x in data[i-lb:i])
            ls=min(x["l"] for x in data[i-lb:i])
            rng=hs-ls
            if rng<=0:continue
            pos=(data[i]["c"]-ls)/rng
            if pos>=1-p:d="LONG"
            elif pos<=p:d="SHORT"
            else:continue
            if fam=="range_position_reversal":d="SHORT" if d=="LONG" else "LONG"
        if not d:continue
        en=i+1;ex=i+1+hold
        gross=(data[ex]["o"]-data[en]["o"]) if d=="LONG" else (data[en]["o"]-data[ex]["o"])
        cost=data[en]["sp"]*data[en]["pt"]
        ev.append({"slot":meta["slot"],"symbol":meta["symbol"],"category":meta["category"],"year":y,"direction":d,
                   "gross":gross/atr[i],"cost":cost/atr[i],"net":(gross-cost)/atr[i]})
        next_allowed=i+hold+1
    return ev

def mean(xs):return sum(xs)/len(xs) if xs else 0.0
def equal_symbol_mean(ev,key):
    d=defaultdict(list)
    for x in ev:d[x["slot"]].append(x[key])
    return mean([mean(v) for v in d.values()]) if d else 0.0
def trim_top(ev,pct,key="net"):
    if not ev:return 0.0
    n=max(1,int(math.ceil(len(ev)*pct)))
    vals=sorted([x[key] for x in ev],reverse=True)[n:]
    return mean(vals) if vals else 0.0

def evaluate(h,ev,scope):
    if scope=="FX":e=[x for x in ev if x["category"]=="FX"]
    elif scope=="NON_FX":e=[x for x in ev if x["category"]!="FX"]
    else:e=list(ev)
    if not e:return None
    sy=defaultdict(list);yr=defaultdict(list);cl=defaultdict(list)
    for x in e:
        sy[x["slot"]].append(x["net"]);yr[x["year"]].append(x["net"]);cl[x["category"]].append(x["net"])
    eq=mean([mean(v) for v in sy.values()])
    stress=equal_symbol_mean([{**x,"net2":x["gross"]-2*x["cost"]} for x in e],"net2")
    trimmed=trim_top(e,0.01)
    pos_sy=sum(1 for v in sy.values() if mean(v)>0); psy=pos_sy/len(sy)
    full=[y for y in range(2019,2026) if y in yr]
    pos_year=sum(1 for y in full if mean(yr[y])>0)
    pos_classes=sum(1 for v in cl.values() if mean(v)>0)
    pos_contrib={k:max(0.0,sum(v)) for k,v in sy.items()}
    tot=sum(pos_contrib.values());mx=max(pos_contrib.values())/tot if tot>0 else 1.0
    gates=[
      len(e)>=300,
      eq>0.05,
      stress>0,
      trimmed>0,
      psy>=0.60,
      len(full)>=6 and pos_year>=5,
      (pos_classes>=2 if scope=="ALL" else pos_classes>=1),
      mx<=0.35
    ]
    fam,lb,hold,p=h
    return {"id":f"{fam}__LB{lb}__H{hold}__P{p}","family":fam,"lookback":lb,"hold":hold,"param":p if p is not None else "",
      "scope":scope,"events":len(e),"equal_mean_atr":eq,"stress2_mean_atr":stress,"trim1_mean_atr":trimmed,
      "positive_symbols":pos_sy,"eligible_symbols":len(sy),"positive_symbol_ratio":psy,
      "positive_years_2019_2025":pos_year,"eligible_full_years":len(full),"positive_classes":pos_classes,
      "eligible_classes":len(cl),"max_positive_symbol_share":mx,"gates_passed":sum(gates),
      "lead":"YES" if all(gates) else "NO","gate_bits":"".join("1" if g else "0" for g in gates)}

def write_csv(path,data):
    if not data:return
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]),delimiter=';');w.writeheader();w.writerows(data)

def upload():
    uploaders=[
      B/"MT5_AutoLab_v0.23.1_METAL_EXECUTION"/"AUTOLOOP_UPLOAD_ROBUST_V0231.ps1",
      B/"AUTOLAB_CONTINUOUS_LOOP_v1"/"MT5_AutoLab_v0.23.1_LOOPTEST"/"AUTOLOOP_UPLOAD_ROBUST_V0231.ps1"
    ]
    up=next((p for p in uploaders if p.exists()),None)
    if not up:raise RuntimeError("uploader robuste introuvable")
    msg=("AUTOLAB CONTINUOUS V1 STAGE 0003 : nouvelle recherche structurelle terminee. Analyse le ZIP; "
         "si aucune vraie decision utilisateur n est necessaire, publie automatiquement STAGE 0004 dans "
         ".autolab_continuous_v1/stages/0004 avec MANIFEST.json puis READY.txt en dernier. "
         "2019-2026 reste recherche exposee; aucun holdout historique intact; aucun live.")
    p=subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(up),"-FilePath",str(HANDOFF),"-Message",msg,"-MarkerPath",str(MARKER)],timeout=420)
    log(f"UPLOAD exit={p.returncode}")

def main():
    MASTER.write_text("",encoding="utf-8")
    try:
      status("VERIFY");m=verify();log("23 sources SHA PASS")
      hlist=hypotheses();log(f"hypotheses predefinies={len(hlist)}")
      all_by_h={h:[] for h in hlist}
      for idx,meta in enumerate(m,1):
        status("RESEARCH",f"{idx}/23 {meta['slot']}")
        d=load(meta);a=atr14(d);log(f"{meta['slot']} bars={len(d)}")
        for h in hlist:all_by_h[h].extend(make_events(meta,d,a,h))
      rr=[]
      for h,ev in all_by_h.items():
        for scope in ("ALL","FX","NON_FX"):
          x=evaluate(h,ev,scope)
          if x:rr.append(x)
      rr.sort(key=lambda x:(x["lead"]=="YES",x["gates_passed"],x["equal_mean_atr"]),reverse=True)
      write_csv(RESULTS,rr);write_csv(TOP,rr[:20])
      leads=[x for x in rr if x["lead"]=="YES"]
      phase="ROBUST_STRUCTURAL_LEAD" if leads else "NO_ROBUST_STRUCTURAL_LEAD"
      lines=[f"AutoLab Continuous STAGE 0003 - {phase}",f"Hypotheses: {len(hlist)} | evaluations: {len(rr)} | leads: {len(leads)}",""]
      for x in rr[:10]:
        lines.append(f"{x['id']} scope={x['scope']} gates={x['gates_passed']}/8 events={x['events']} mean={x['equal_mean_atr']:+.4f} stress2={x['stress2_mean_atr']:+.4f} trim1={x['trim1_mean_atr']:+.4f} sym+={x['positive_symbol_ratio']:.1%} years+={x['positive_years_2019_2025']}/{x['eligible_full_years']}")
      SUMMARY.write_text("\n".join(lines)+"\n",encoding="utf-8")
      FINAL.write_text("# "+lines[0]+"\n\n"+"\n".join("- "+x for x in lines[1:] if x)+"\n",encoding="utf-8")
      status(phase,f"leads={len(leads)}")
      files=[RESULTS,TOP,SUMMARY,FINAL,STATUS,MASTER,PROTOCOL,MANIFEST,PKG/"RESEARCH_STAGE0003.py"]
      with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:
          if p.exists():z.write(p,p.name)
      log(f"ZIP={HANDOFF} SHA={sha(HANDOFF)}")
      upload();return 0
    except Exception as e:
      ERROR.write_text(traceback.format_exc(),encoding="utf-8");status("TECHNICAL_ERROR",str(e));log("ERROR "+str(e))
      with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED) as z:
        for p in (ERROR,STATUS,MASTER,PROTOCOL,MANIFEST,PKG/"RESEARCH_STAGE0003.py"):
          if p.exists():z.write(p,p.name)
      try:upload()
      except Exception as u:log("UPLOAD ERROR "+str(u))
      return 20
if __name__=="__main__":raise SystemExit(main())
