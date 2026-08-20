from pathlib import Path
import csv,json,math,hashlib,zipfile,subprocess,traceback
from datetime import datetime
from collections import defaultdict,deque

B=Path(r"C:\dev_EA_MT5")
DATA=B/"data"/"continuous_stage0006_discovery"
REP=B/"reports"; LOG=B/"logs"; A=B/"autolab"/"continuous_stage_0007"
PKG=Path(__file__).resolve().parent
for d in (REP,LOG,A):d.mkdir(parents=True,exist_ok=True)

MANIFEST=PKG/"DISCOVERY_MANIFEST_STAGE0006.csv"
LOCK=PKG/"VALIDATION_POOL_STAGE0006_LOCKED.json"
PROTOCOL=PKG/"RESEARCH_PROTOCOL_STAGE0007.json"
MANIFEST_SHA="f12a6b89ac3e06276c10cf1821f0a1868aed9b5cca1c2c9b412ef991875a370c"
LOCK_SHA="c208bea3a979b5e5f860b40317dd434dc3e6778e864db6934a375ffaed64722e"
PROTOCOL_SHA="c55180064d93dc0520262e59abdb9643ff98cbe2382322f8e5de35a1080a04d1"

MASTER=LOG/"AUTOLAB_STAGE0007.log"
STATUS=LOG/"AUTOLAB_STATUS_STAGE0007.txt"
ERROR=LOG/"AUTOLAB_STAGE0007_ERROR.txt"
RESULTS=REP/"AUTOLAB_DISCOVERY_RESULTS_STAGE0007.csv"
TOP=REP/"AUTOLAB_DISCOVERY_TOP20_STAGE0007.csv"
SUMMARY=REP/"AUTOLAB_SUMMARY_STAGE0007.txt"
FINAL=REP/"AUTOLAB_FINAL_STAGE0007.md"
FROZEN=REP/"FROZEN_DISCOVERY_CANDIDATE_STAGE0007.json"
HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0007_DISCOVERY.zip"
MARKER=A/"UPLOAD_CONFIRMED.txt"

def stamp():return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def log(s):
    line=f"[{stamp()}] {s}";print(line,flush=True)
    with MASTER.open("a",encoding="utf-8") as f:f.write(line+"\n")
def status(phase,msg=""):
    STATUS.write_text(
      f"AutoLab Continuous V1 STAGE 0007\nDate: {stamp()}\nPhase: {phase}\nMessage: {msg}\n"
      "DISCOVERY=ACTIVE\nVALIDATION=LOCKED / NON EXTRAITE / NON ANALYSEE\nLIVE=INTERDIT\n",
      encoding="utf-8")
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
def mean(xs):return sum(xs)/len(xs) if xs else 0.0

def verify():
    if sha(MANIFEST)!=MANIFEST_SHA:raise RuntimeError("discovery manifest SHA mismatch")
    if sha(LOCK)!=LOCK_SHA:raise RuntimeError("validation lock SHA mismatch")
    if sha(PROTOCOL)!=PROTOCOL_SHA:raise RuntimeError("protocol SHA mismatch")
    lock=json.loads(LOCK.read_text(encoding="utf-8"))
    if lock.get("price_data_extracted") is not False or lock.get("price_data_analyzed") is not False:
        raise RuntimeError("validation lock violated before stage0007")
    m=rows(MANIFEST)
    if len(m)<24:raise RuntimeError(f"discovery instruments insufficient {len(m)}")
    cats={r["category"] for r in m}
    if len(cats)<6:raise RuntimeError(f"discovery categories insufficient {len(cats)}")
    for r in m:
        p=Path(r["path"])
        if not p.exists():raise RuntimeError("discovery data missing "+str(p))
        if sha(p).lower()!=r["sha256"].lower():raise RuntimeError("discovery data SHA mismatch "+r["symbol"])
    return m

def load(meta):
    out=[]
    p=Path(meta["path"])
    for r in rows(p):
        try:
            dt=datetime.strptime(r["time"],"%Y.%m.%d %H:%M")
            if dt.year<2018 or dt.year>2026:continue
            out.append({
              "dt":dt,"o":float(r["open"].replace(",",".")),
              "h":float(r["high"].replace(",",".")),
              "l":float(r["low"].replace(",",".")),
              "c":float(r["close"].replace(",",".")),
              "sp":float(r["spread_points"].replace(",",".")),
              "pt":float(r["point"].replace(",",".")),
            })
        except Exception:pass
    out.sort(key=lambda x:x["dt"])
    return out

def atr14(d):
    tr=[]
    for i,x in enumerate(d):
        pc=d[i-1]["c"] if i else x["c"]
        tr.append(max(x["h"]-x["l"],abs(x["h"]-pc),abs(x["l"]-pc)))
    out=[None]*len(d);q=deque();s=0.0
    for i,v in enumerate(tr):
        q.append(v);s+=v
        if len(q)>14:s-=q.popleft()
        if len(q)==14:out[i]=s/14
    return out

def atr_ratio72(a):
    out=[None]*len(a);q=deque();s=0.0
    for i,v in enumerate(a):
        if v is None:continue
        if len(q)>=72 and s>0:out[i]=v/(s/72)
        q.append(v);s+=v
        if len(q)>72:s-=q.popleft()
    return out

def hypotheses():
    H=[]
    for fam in ("ts_momentum","ts_reversal","range_breakout","range_reversal"):
      for lb in (24,72,120):
       for hold in (8,24,72):
        H.append({"family":fam,"lookback":lb,"hold":hold})
    for fam in ("impulse_momentum","impulse_reversal"):
      for lb in (6,12):
       for th in (1.0,1.5):
        for hold in (4,8,24):
         H.append({"family":fam,"lookback":lb,"threshold":th,"hold":hold})
    for cr in (0.65,0.80):
      for lb in (24,72):
       for hold in (8,24):
        H.append({"family":"compression_breakout","compression":cr,"lookback":lb,"hold":hold})
    if len(H)!=68:raise RuntimeError(f"hypothesis count {len(H)} != 68")
    for h in H:
        parts=[h["family"],f"LB{h['lookback']}",f"H{h['hold']}"]
        if "threshold" in h:parts.append(f"T{h['threshold']}")
        if "compression" in h:parts.append(f"C{h['compression']}")
        h["id"]="__".join(parts)
    return H

def make_events(meta,d,a,vr,h):
    fam=h["family"];lb=h["lookback"];hold=h["hold"]
    ev=[];next_allowed=0
    start=max(250,lb+80)
    for i in range(start,len(d)-hold-2):
        if i<next_allowed:continue
        y=d[i]["dt"].year
        if y<2019 or y>2026 or a[i] is None or a[i]<=0:continue
        direction=None
        if fam.startswith("ts_"):
            move=d[i]["c"]-d[i-lb]["c"]
            if move>0:direction="LONG"
            elif move<0:direction="SHORT"
            if fam=="ts_reversal" and direction:direction="SHORT" if direction=="LONG" else "LONG"
        elif fam.startswith("range_"):
            hh=max(x["h"] for x in d[i-lb:i]);ll=min(x["l"] for x in d[i-lb:i])
            if d[i]["c"]>hh:direction="LONG"
            elif d[i]["c"]<ll:direction="SHORT"
            if fam=="range_reversal" and direction:direction="SHORT" if direction=="LONG" else "LONG"
        elif fam.startswith("impulse_"):
            move=d[i]["c"]-d[i-lb]["c"]
            if abs(move)<h["threshold"]*a[i]:continue
            direction="LONG" if move>0 else "SHORT"
            if fam=="impulse_reversal":direction="SHORT" if direction=="LONG" else "LONG"
        elif fam=="compression_breakout":
            if vr[i] is None or vr[i]>h["compression"]:continue
            hh=max(x["h"] for x in d[i-lb:i]);ll=min(x["l"] for x in d[i-lb:i])
            if d[i]["c"]>hh:direction="LONG"
            elif d[i]["c"]<ll:direction="SHORT"
        if not direction:continue
        en=i+1;ex=i+1+hold
        gross=(d[ex]["o"]-d[en]["o"]) if direction=="LONG" else (d[en]["o"]-d[ex]["o"])
        cost=d[en]["sp"]*d[en]["pt"]
        ev.append({
          "symbol":meta["symbol"],"category":meta["category"],"year":y,"direction":direction,
          "gross":gross/a[i],"cost":cost/a[i],"net":(gross-cost)/a[i]
        })
        next_allowed=i+hold+1
    return ev

def trim_top(e,pct,key="net"):
    if not e:return 0.0
    vals=sorted((x[key] for x in e),reverse=True)
    n=max(1,int(math.ceil(len(vals)*pct)))
    vals=vals[n:]
    return mean(vals) if vals else 0.0

def equal_group_mean(e,group,key):
    g=defaultdict(list)
    for x in e:g[x[group]].append(x[key])
    return mean([mean(v) for v in g.values()]) if g else 0.0

def evaluate(h,e):
    sy=defaultdict(list);cat=defaultdict(list);yr=defaultdict(list)
    for x in e:
        sy[x["symbol"]].append(x["net"])
        cat[x["category"]].append(x["net"])
        yr[x["year"]].append(x["net"])

    elig_sy={k:v for k,v in sy.items() if len(v)>=20}
    elig_cat={k:v for k,v in cat.items() if len(v)>=40}
    eq=mean([mean(v) for v in elig_sy.values()])
    s2=mean([mean([x["gross"]-2*x["cost"] for x in e if x["symbol"]==k]) for k in elig_sy]) if elig_sy else 0.0
    s3=mean([mean([x["gross"]-3*x["cost"] for x in e if x["symbol"]==k]) for k in elig_sy]) if elig_sy else 0.0
    t1=trim_top(e,.01);t5=trim_top(e,.05)

    pos_sy=sum(1 for v in elig_sy.values() if mean(v)>0)
    psr=pos_sy/len(elig_sy) if elig_sy else 0.0
    pos_cat=sum(1 for v in elig_cat.values() if mean(v)>0)
    pcr=pos_cat/len(elig_cat) if elig_cat else 0.0

    full=[y for y in range(2019,2026) if len(yr.get(y,[]))>=50]
    py=sum(1 for y in full if mean(yr[y])>0)
    h1=[x["net"] for x in e if 2019<=x["year"]<=2022]
    h2=[x["net"] for x in e if 2023<=x["year"]<=2025]
    half1=mean(h1);half2=mean(h2)

    contrib_sy={k:max(0.0,sum(v)) for k,v in elig_sy.items()}
    total_sy=sum(contrib_sy.values())
    max_sy=max(contrib_sy.values())/total_sy if total_sy>0 and contrib_sy else 1.0
    contrib_cat={k:max(0.0,sum(v)) for k,v in elig_cat.items()}
    total_cat=sum(contrib_cat.values())
    max_cat=max(contrib_cat.values())/total_cat if total_cat>0 and contrib_cat else 1.0

    base=[
      len(e)>=600,len(elig_sy)>=18,len(elig_cat)>=6,
      eq>0.04,s2>0,s3>0,t1>0,t5>0,
      psr>=0.60,pcr>=0.625,
      len(full)>=6 and py>=5,
      half1>0 and half2>0,
      max_sy<=0.20,max_cat<=0.40,
    ]
    return {
      "id":h["id"],"family":h["family"],"lookback":h["lookback"],"hold":h["hold"],
      "threshold":h.get("threshold",""),"compression":h.get("compression",""),
      "events":len(e),"eligible_symbols":len(elig_sy),"eligible_categories":len(elig_cat),
      "equal_symbol_mean_atr":eq,"stress2_equal_atr":s2,"stress3_equal_atr":s3,
      "trim1_pooled_atr":t1,"trim5_pooled_atr":t5,
      "positive_symbols":pos_sy,"positive_symbol_ratio":psr,
      "positive_categories":pos_cat,"positive_category_ratio":pcr,
      "positive_years":py,"eligible_years":len(full),
      "half1_atr":half1,"half2_atr":half2,
      "max_positive_symbol_share":max_sy,"max_positive_category_share":max_cat,
      "_base":base
    }

def adjacent(grid,a,b):
    try:return abs(grid.index(a)-grid.index(b))==1
    except:return False

def is_neighbor(a,b):
    if a["family"]!=b["family"]:return False
    diffs=0
    for key,grid in (("lookback",[24,72,120]),("hold",[4,8,24,72]),("threshold",[1.0,1.5]),("compression",[0.65,0.80])):
        av=a.get(key,"");bv=b.get(key,"")
        if av=="" and bv=="":continue
        if av!=bv:
            if av=="" or bv=="":return False
            if key=="hold":
                fam=a["family"]
                g=[8,24,72] if fam in ("ts_momentum","ts_reversal","range_breakout","range_reversal") else ([4,8,24] if fam.startswith("impulse_") else [8,24])
                if not adjacent(g,av,bv):return False
            elif not adjacent(grid,av,bv):return False
            diffs+=1
    return diffs==1

def finalize(rr):
    for r in rr:
        ns=[x for x in rr if is_neighbor(r,x)]
        good=sum(1 for x in ns if x["equal_symbol_mean_atr"]>0 and x["stress2_equal_atr"]>0 and x["trim1_pooled_atr"]>0)
        nr=good/len(ns) if ns else 0.0
        r["neighbor_good_ratio"]=nr
        gates=list(r.pop("_base"))+[nr>=0.50]
        r["gates_passed"]=sum(gates);r["gate_bits"]="".join("1" if g else "0" for g in gates)
        r["lead"]="YES" if all(gates) else "NO"
        r["robustness_floor"]=min(r["stress3_equal_atr"],r["trim5_pooled_atr"],r["half1_atr"],r["half2_atr"])
    rr.sort(key=lambda r:(r["lead"]=="YES",r["robustness_floor"],r["positive_symbol_ratio"],r["neighbor_good_ratio"],r["equal_symbol_mean_atr"],r["id"]),reverse=True)
    return rr

def write_csv(p,data):
    if not data:return
    with p.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]),delimiter=';');w.writeheader();w.writerows(data)

def freeze_if_lead(rr):
    leads=[r for r in rr if r["lead"]=="YES"]
    if not leads:
        FROZEN.unlink(missing_ok=True)
        return None
    best=leads[0]
    payload={
      "chain_id":"AUTOLAB_CONTINUOUS_V1","stage":"0007","status":"FROZEN_DISCOVERY_CANDIDATE",
      "candidate":{k:best[k] for k in ("id","family","lookback","hold","threshold","compression")},
      "discovery_metrics":{k:best[k] for k in best if k not in ("id","family","lookback","hold","threshold","compression")},
      "discovery_manifest_sha256":MANIFEST_SHA,"protocol_sha256":PROTOCOL_SHA,
      "validation_lock_sha256":LOCK_SHA,
      "validation_status":"LOCKED_NOT_EXTRACTED_NOT_ANALYZED",
      "rule":"exact family/parameters only; no alternatives in validation",
      "frozen_at":stamp()
    }
    FROZEN.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return payload

def upload():
    uploaders=[
      B/"AUTOLAB_CONTINUOUS_GUARD_v2_1"/"AUTOLOOP_UPLOAD_ROBUST.ps1",
      B/"AUTOLAB_CONTINUOUS_GUARD_v2"/"AUTOLOOP_UPLOAD_ROBUST.ps1",
      B/"MT5_AutoLab_v0.23.1_METAL_EXECUTION"/"AUTOLOOP_UPLOAD_ROBUST_V0231.ps1",
    ]
    up=next((p for p in uploaders if p.exists()),None)
    if not up:raise RuntimeError("uploader robuste introuvable")
    msg=("AUTOLAB CONTINUOUS V1 STAGE 0007 : tournoi discovery termine. Analyse le ZIP; "
         "si aucune vraie decision utilisateur n est necessaire, publie automatiquement STAGE 0008 dans "
         ".autolab_continuous_v1/stages/0008 avec MANIFEST.json puis READY.txt en dernier. "
         "VALIDATION reste verrouillee sauf si FROZEN_DISCOVERY_CANDIDATE_STAGE0007.json existe; aucun live.")
    p=subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(up),
                      "-FilePath",str(HANDOFF),"-Message",msg,"-MarkerPath",str(MARKER)],timeout=420)
    log(f"UPLOAD exit={p.returncode}")

def main():
    MASTER.write_text("",encoding="utf-8")
    try:
        status("VERIFY")
        m=verify();log(f"discovery integrity PASS instruments={len(m)} categories={len(set(x['category'] for x in m))}")
        hs=hypotheses();log(f"hypotheses frozen={len(hs)}")
        all_ev={h["id"]:[] for h in hs}
        byid={h["id"]:h for h in hs}
        for idx,meta in enumerate(m,1):
            status("RESEARCH",f"{idx}/{len(m)} {meta['symbol']}")
            d=load(meta);a=atr14(d);vr=atr_ratio72(a)
            log(f"{meta['symbol']} category={meta['category']} bars={len(d)}")
            for h in hs:all_ev[h["id"]].extend(make_events(meta,d,a,vr,h))
        rr=[evaluate(byid[k],e) for k,e in all_ev.items()]
        rr=finalize(rr)
        write_csv(RESULTS,rr);write_csv(TOP,rr[:20])
        frozen=freeze_if_lead(rr)
        phase="DISCOVERY_CANDIDATE_FROZEN" if frozen else "NO_ROBUST_DISCOVERY_LEAD"
        lines=[
          f"AutoLab Continuous STAGE 0007 - {phase}",
          f"Discovery instruments: {len(m)} | categories: {len(set(x['category'] for x in m))}",
          f"Hypotheses: {len(hs)} | robust leads: {sum(1 for x in rr if x['lead']=='YES')}",
          "Validation: LOCKED / NOT EXTRACTED / NOT ANALYZED",""
        ]
        for x in rr[:10]:
            lines.append(f"{x['id']} gates={x['gates_passed']}/15 events={x['events']} eq={x['equal_symbol_mean_atr']:+.4f} s3={x['stress3_equal_atr']:+.4f} trim5={x['trim5_pooled_atr']:+.4f} sym+={x['positive_symbol_ratio']:.1%} cat+={x['positive_category_ratio']:.1%} years+={x['positive_years']}/{x['eligible_years']} neigh={x['neighbor_good_ratio']:.2f}")
        SUMMARY.write_text("\n".join(lines)+"\n",encoding="utf-8")
        FINAL.write_text("# "+lines[0]+"\n\n"+"\n".join("- "+x for x in lines[1:] if x)+"\n",encoding="utf-8")
        status(phase,f"leads={sum(1 for x in rr if x['lead']=='YES')}")
        files=[RESULTS,TOP,SUMMARY,FINAL,STATUS,MASTER,MANIFEST,LOCK,PROTOCOL,PKG/"RESEARCH_STAGE0007.py"]
        if FROZEN.exists():files.append(FROZEN)
        with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in files:
                if p.exists():z.write(p,p.name)
        log(f"ZIP={HANDOFF} SHA={sha(HANDOFF)}")
        upload()
        return 0
    except Exception as exc:
        ERROR.write_text(traceback.format_exc(),encoding="utf-8")
        status("TECHNICAL_ERROR",str(exc));log("ERROR "+str(exc))
        with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED) as z:
            for p in (ERROR,STATUS,MASTER,MANIFEST,LOCK,PROTOCOL,PKG/"RESEARCH_STAGE0007.py"):
                if p.exists():z.write(p,p.name)
        try:upload()
        except Exception as u:log("UPLOAD ERROR "+str(u))
        return 20

if __name__=="__main__":raise SystemExit(main())
