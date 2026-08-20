from pathlib import Path
import csv, json, math, hashlib, zipfile, subprocess, traceback
from datetime import datetime
from collections import defaultdict, deque

B=Path(r"C:\dev_EA_MT5")
DATA=B/"data"/"v0.21.1"
REP=B/"reports"; LOG=B/"logs"; A=B/"autolab"/"continuous_stage_0004"
PKG=Path(__file__).resolve().parent
for d in (REP,LOG,A): d.mkdir(parents=True,exist_ok=True)

STATUS=LOG/"AUTOLAB_STATUS_STAGE0004.txt"
MASTER=LOG/"AUTOLAB_STAGE0004.log"
ERROR=LOG/"AUTOLAB_STAGE0004_ERROR.txt"
RESULTS=REP/"AUTOLAB_CROSS_SECTIONAL_RESULTS_STAGE0004.csv"
TOP=REP/"AUTOLAB_CROSS_SECTIONAL_TOP20_STAGE0004.csv"
SUMMARY=REP/"AUTOLAB_SUMMARY_STAGE0004.txt"
FINAL=REP/"AUTOLAB_FINAL_STAGE0004.md"
HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0004_CROSS_SECTIONAL.zip"
MARKER=A/"UPLOAD_CONFIRMED.txt"

PROTOCOL=PKG/"RESEARCH_PROTOCOL_STAGE0004.json"
MANIFEST=PKG/"SOURCE_MANIFEST_V0211.csv"
PROTOCOL_SHA="2d78f0ceca02b487dfc5334c31c984248942924b7208c2ed8c7c89c26719fc8e"
MANIFEST_SHA="fce21ee4eab1b14c673287c39e3a1b9598be4b48a001999e003d8775418fdf8c"

LOOKBACKS=(24,72,120,240)
HOLDS=(8,24,72)
TAILS=(0.20,0.30)
STYLES=("cross_sectional_momentum","cross_sectional_reversal")
UNIVERSES=("FX","NON_FX_CORE","ALL_CORE")

def stamp(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def log(s):
    line=f"[{stamp()}] {s}"; print(line,flush=True)
    with MASTER.open("a",encoding="utf-8") as f:f.write(line+"\n")
def status(phase,msg=""):
    STATUS.write_text(
      f"AutoLab Continuous V1 STAGE 0004\nDate: {stamp()}\nPhase: {phase}\nMessage: {msg}\n"
      "2019-2026=RESEARCH EXPOSEE\nHOLDOUT HISTORIQUE=AUCUN\nLIVE=INTERDIT\n",encoding="utf-8")
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

def load(meta):
    out=[]
    for x in rows(DATA/(meta["symbol"]+".csv")):
        try:
            out.append({
              "dt":datetime.strptime(x["time"],"%Y.%m.%d %H:%M"),
              "o":float(x["open"].replace(",",".")),
              "h":float(x["high"].replace(",",".")),
              "l":float(x["low"].replace(",",".")),
              "c":float(x["close"].replace(",",".")),
              "sp":float(x["spread_points"].replace(",",".")),
              "pt":float(x["point"].replace(",",".")),
            })
        except Exception:pass
    out.sort(key=lambda x:x["dt"])
    return out

def atr14(data):
    tr=[]
    for i,x in enumerate(data):
        pc=data[i-1]["c"] if i else x["c"]
        tr.append(max(x["h"]-x["l"],abs(x["h"]-pc),abs(x["l"]-pc)))
    out=[None]*len(data);q=deque();s=0.0
    for i,v in enumerate(tr):
        q.append(v);s+=v
        if len(q)>14:s-=q.popleft()
        if len(q)==14:out[i]=s/14
    return out

def mean(xs): return sum(xs)/len(xs) if xs else 0.0

def coverage_ok(meta):
    try:
        first=datetime.strptime(meta["first"],"%Y-%m-%d %H:%M:%S")
        last=datetime.strptime(meta["last"],"%Y-%m-%d %H:%M:%S")
        return first<=datetime(2019,1,15) and last>=datetime(2026,8,1)
    except Exception:return False

def make_universes(manifest):
    eligible=[m for m in manifest if coverage_ok(m)]
    fx=[m for m in eligible if m["category"]=="FX"]
    nonfx=[m for m in eligible if m["category"]!="FX"]
    return {"FX":fx,"NON_FX_CORE":nonfx,"ALL_CORE":fx+nonfx}

def prepare_series(metas):
    S={}
    for meta in metas:
        d=load(meta); a=atr14(d); idx={x["dt"]:i for i,x in enumerate(d)}
        S[meta["slot"]]={"meta":meta,"d":d,"a":a,"idx":idx}
        log(f"LOAD {meta['slot']} broker={meta['symbol']} bars={len(d)}")
    common=None
    for v in S.values():
        times=set(v["idx"])
        common=times if common is None else common & times
    common=sorted(t for t in common if datetime(2019,1,1)<=t<=datetime(2026,8,6,23,59))
    return S,common

def hypothesis_list():
    return [(style,lb,hold,tail) for style in STYLES for lb in LOOKBACKS for hold in HOLDS for tail in TAILS]

def run_hypothesis(S,common,h):
    style,lb,hold,tail=h
    events=[]
    symbol_contrib=defaultdict(float)
    next_allowed=None
    nsel=max(1,int(math.floor(len(S)*tail)))
    for dt in common:
        if next_allowed is not None and dt<next_allowed:continue
        ranks=[]
        valid=True
        for slot,v in S.items():
            i=v["idx"].get(dt)
            if i is None or i<max(lb,20) or i+1+hold>=len(v["d"]) or v["a"][i] is None or v["a"][i]<=0:
                valid=False;break
            c0=v["d"][i-lb]["c"]; c1=v["d"][i]["c"]
            if c0<=0:valid=False;break
            ranks.append(((c1/c0)-1.0,slot,i))
        if not valid or len(ranks)<4:continue
        ranks.sort()
        bottom=ranks[:nsel];top=ranks[-nsel:]
        if style=="cross_sectional_momentum":
            longs=top;shorts=bottom
        else:
            longs=bottom;shorts=top
        legs=[]
        exits=[]
        for direction,bucket in (("LONG",longs),("SHORT",shorts)):
            for _,slot,i in bucket:
                v=S[slot];d=v["d"];a=v["a"][i]
                en=i+1;ex=i+1+hold
                gross=(d[ex]["o"]-d[en]["o"]) if direction=="LONG" else (d[en]["o"]-d[ex]["o"])
                cost=d[en]["sp"]*d[en]["pt"]
                ga=gross/a; ca=cost/a
                legs.append((slot,direction,ga,ca))
                exits.append(d[ex]["dt"])
        if not legs:continue
        net=[ga-ca for _,_,ga,ca in legs]
        net2=[ga-2*ca for _,_,ga,ca in legs]
        net3=[ga-3*ca for _,_,ga,ca in legs]
        longvals=[ga-ca for _,di,ga,ca in legs if di=="LONG"]
        shortvals=[ga-ca for _,di,ga,ca in legs if di=="SHORT"]
        for slot,_,ga,ca in legs:symbol_contrib[slot]+=ga-ca
        events.append({
          "dt":dt,"year":dt.year,"net":mean(net),"net2":mean(net2),"net3":mean(net3),
          "long":mean(longvals),"short":mean(shortvals)
        })
        next_allowed=max(exits)
    return events,symbol_contrib

def trim_top(vals,pct):
    if not vals:return 0.0
    n=max(1,int(math.ceil(len(vals)*pct)))
    z=sorted(vals,reverse=True)[n:]
    return mean(z) if z else 0.0

def base_metrics(universe,h,events,contrib):
    style,lb,hold,tail=h
    nets=[e["net"] for e in events]
    years=defaultdict(list)
    for e in events:
        if 2019<=e["year"]<=2025:years[e["year"]].append(e["net"])
    eligible=[y for y in range(2019,2026) if y in years]
    pos_years=sum(1 for y in eligible if mean(years[y])>0)
    half1=[e["net"] for e in events if 2019<=e["year"]<=2022]
    half2=[e["net"] for e in events if 2023<=e["year"]<=2025]
    pos={k:max(0.0,v) for k,v in contrib.items()}
    tot=sum(pos.values())
    max_share=max(pos.values())/tot if tot>0 and pos else 1.0
    r={
      "id":f"{style}__{universe}__LB{lb}__H{hold}__T{tail:.2f}",
      "style":style,"universe":universe,"lookback":lb,"hold":hold,"tail":tail,
      "events":len(events),
      "mean_atr":mean(nets),"stress2_atr":mean([e["net2"] for e in events]),
      "stress3_atr":mean([e["net3"] for e in events]),
      "trim1_atr":trim_top(nets,0.01),"trim5_atr":trim_top(nets,0.05),
      "positive_years":pos_years,"eligible_years":len(eligible),
      "half1_atr":mean(half1),"half2_atr":mean(half2),
      "long_atr":mean([e["long"] for e in events]),
      "short_atr":mean([e["short"] for e in events]),
      "max_positive_symbol_share":max_share,
    }
    return r

def is_neighbor(a,b):
    if a["universe"]!=b["universe"] or a["style"]!=b["style"]:return False
    diffs=0
    for key,grid in (("lookback",LOOKBACKS),("hold",HOLDS),("tail",TAILS)):
        ia=grid.index(a[key]);ib=grid.index(b[key])
        if ia!=ib:
            if abs(ia-ib)!=1:return False
            diffs+=1
    return diffs==1

def finalize(rows_):
    for r in rows_:
        neigh=[x for x in rows_ if is_neighbor(r,x)]
        good=[x for x in neigh if x["mean_atr"]>0 and x["stress2_atr"]>0 and x["trim1_atr"]>0]
        nr=len(good)/len(neigh) if neigh else 0.0
        r["neighbor_good_ratio"]=nr
        gates=[
          r["events"]>=300,
          r["mean_atr"]>0.05,
          r["stress2_atr"]>0,
          r["stress3_atr"]>0,
          r["trim1_atr"]>0,
          r["trim5_atr"]>0,
          r["eligible_years"]>=6 and r["positive_years"]>=5,
          r["half1_atr"]>0 and r["half2_atr"]>0,
          r["long_atr"]>0,
          r["short_atr"]>0,
          r["max_positive_symbol_share"]<=0.30,
          nr>=0.50,
        ]
        r["gates_passed"]=sum(gates)
        r["gate_bits"]="".join("1" if x else "0" for x in gates)
        r["lead"]="YES" if all(gates) else "NO"
    rows_.sort(key=lambda r:(r["lead"]=="YES",r["gates_passed"],r["mean_atr"],r["stress3_atr"]),reverse=True)

def write_csv(path,data):
    if not data:return
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]),delimiter=';');w.writeheader();w.writerows(data)

def upload():
    candidates=[
      B/"AUTOLAB_CONTINUOUS_GUARD_v2_1"/"AUTOLOOP_UPLOAD_ROBUST.ps1",
      B/"AUTOLAB_CONTINUOUS_GUARD_v2"/"AUTOLOOP_UPLOAD_ROBUST.ps1",
      B/"MT5_AutoLab_v0.23.1_METAL_EXECUTION"/"AUTOLOOP_UPLOAD_ROBUST_V0231.ps1",
      B/"AUTOLAB_CONTINUOUS_LOOP_v1"/"MT5_AutoLab_v0.23.1_LOOPTEST"/"AUTOLOOP_UPLOAD_ROBUST_V0231.ps1",
    ]
    up=next((p for p in candidates if p.exists()),None)
    if not up:raise RuntimeError("uploader robuste introuvable")
    msg=("AUTOLAB CONTINUOUS V1 STAGE 0004 : recherche cross-sectionnelle terminee. Analyse le ZIP; "
         "si aucune vraie decision utilisateur n est necessaire, publie automatiquement STAGE 0005 dans "
         ".autolab_continuous_v1/stages/0005 avec MANIFEST.json puis READY.txt en dernier. "
         "2019-2026 reste recherche exposee; aucun holdout historique intact; aucun live.")
    p=subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(up),
                      "-FilePath",str(HANDOFF),"-Message",msg,"-MarkerPath",str(MARKER)],timeout=420)
    log(f"UPLOAD exit={p.returncode}")

def main():
    MASTER.write_text("",encoding="utf-8")
    try:
        status("VERIFY");manifest=verify();log("23 sources SHA PASS")
        universes=make_universes(manifest)
        log("UNIVERSES "+", ".join(f"{k}={len(v)}" for k,v in universes.items()))
        hlist=hypothesis_list()
        if len(hlist)!=48:raise RuntimeError("hypothesis grid !=48")
        allrows=[]
        for uname,metas in universes.items():
            if len(metas)<4:raise RuntimeError(f"univers {uname} trop petit: {len(metas)}")
            status("PREPARE_UNIVERSE",f"{uname} n={len(metas)}")
            S,common=prepare_series(metas)
            if len(common)<5000:raise RuntimeError(f"timestamps communs insuffisants {uname}: {len(common)}")
            log(f"COMMON {uname} timestamps={len(common)}")
            for j,h in enumerate(hlist,1):
                status("RESEARCH",f"{uname} {j}/48 {h}")
                ev,contrib=run_hypothesis(S,common,h)
                allrows.append(base_metrics(uname,h,ev,contrib))
            del S
        if len(allrows)!=144:raise RuntimeError(f"evaluations attendues 144, obtenu {len(allrows)}")
        finalize(allrows)
        write_csv(RESULTS,allrows);write_csv(TOP,allrows[:20])
        leads=[r for r in allrows if r["lead"]=="YES"]
        phase="ROBUST_CROSS_SECTIONAL_LEAD" if leads else "NO_ROBUST_CROSS_SECTIONAL_LEAD"
        lines=[f"AutoLab Continuous STAGE 0004 - {phase}",
               f"Evaluations: {len(allrows)} | leads: {len(leads)}",""]
        for r in allrows[:12]:
            lines.append(
              f"{r['id']} gates={r['gates_passed']}/12 events={r['events']} mean={r['mean_atr']:+.4f} "
              f"x2={r['stress2_atr']:+.4f} x3={r['stress3_atr']:+.4f} trim1={r['trim1_atr']:+.4f} "
              f"trim5={r['trim5_atr']:+.4f} years={r['positive_years']}/{r['eligible_years']} "
              f"halves=({r['half1_atr']:+.4f},{r['half2_atr']:+.4f}) "
              f"sides=({r['long_atr']:+.4f},{r['short_atr']:+.4f}) neigh={r['neighbor_good_ratio']:.0%}"
            )
        SUMMARY.write_text("\n".join(lines)+"\n",encoding="utf-8")
        FINAL.write_text("# "+lines[0]+"\n\n"+"\n".join("- "+x for x in lines[1:] if x)+"\n",encoding="utf-8")
        status(phase,f"leads={len(leads)}")
        files=[RESULTS,TOP,SUMMARY,FINAL,STATUS,MASTER,PROTOCOL,MANIFEST,PKG/"RESEARCH_STAGE0004.py"]
        with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in files:
                if p.exists():z.write(p,p.name)
        log(f"ZIP={HANDOFF} SHA={sha(HANDOFF)}")
        upload();return 0
    except Exception as e:
        ERROR.write_text(traceback.format_exc(),encoding="utf-8")
        status("TECHNICAL_ERROR",str(e));log("ERROR "+str(e))
        with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED) as z:
            for p in (ERROR,STATUS,MASTER,PROTOCOL,MANIFEST,PKG/"RESEARCH_STAGE0004.py"):
                if p.exists():z.write(p,p.name)
        try:upload()
        except Exception as u:log("UPLOAD ERROR "+str(u))
        return 20

if __name__=="__main__":raise SystemExit(main())
