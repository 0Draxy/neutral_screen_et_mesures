from pathlib import Path
import csv, json, math, hashlib, zipfile, subprocess, traceback
from datetime import datetime
from collections import defaultdict

B=Path(r"C:\dev_EA_MT5")
DATA=B/"data"/"v0.21.1"
REP=B/"reports"; LOG=B/"logs"; A=B/"autolab"/"continuous_stage_0005"
PKG=Path(__file__).resolve().parent
for d in (REP,LOG,A): d.mkdir(parents=True,exist_ok=True)

STATUS=LOG/"AUTOLAB_STATUS_STAGE0005.txt"
MASTER=LOG/"AUTOLAB_STAGE0005.log"
ERROR=LOG/"AUTOLAB_STAGE0005_ERROR.txt"
RESULTS=REP/"AUTOLAB_PAIR_RESULTS_STAGE0005.csv"
TOP=REP/"AUTOLAB_PAIR_TOP20_STAGE0005.csv"
SUMMARY=REP/"AUTOLAB_SUMMARY_STAGE0005.txt"
FINAL=REP/"AUTOLAB_FINAL_STAGE0005.md"
HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0005_PAIR_RELATIVE_VALUE.zip"
MARKER=A/"UPLOAD_CONFIRMED.txt"

PROTOCOL=PKG/"RESEARCH_PROTOCOL_STAGE0005.json"
MANIFEST=PKG/"SOURCE_MANIFEST_V0211.csv"
PROTOCOL_SHA="0192db34a4ddfcbb8f6cece66b950312632a6c50ba9e8838f513deb896fb0b31"
MANIFEST_SHA="fce21ee4eab1b14c673287c39e3a1b9598be4b48a001999e003d8775418fdf8c"

PAIRS=[
("EURUSD__GBPUSD","EURUSD","GBPUSD","FX"),
("AUDUSD__NZDUSD","AUDUSD","NZDUSD","FX"),
("EURJPY__GBPJPY","EURJPY","GBPJPY","FX"),
("EURCHF__GBPCHF","EURCHF","GBPCHF","FX"),
("AUDJPY__CADJPY","AUDJPY","CADJPY","FX"),
("US500__NAS100","US500","NAS100","INDEX"),
("US500__US30","US500","US30","INDEX"),
("XAUUSD__XAGUSD","XAUUSD","XAGUSD","METAL"),
]
LOOKBACKS=(120,240,480)
ZLEVELS=(1.0,1.5,2.0)
HOLDS=(8,24,72)
STYLES=("pair_mean_reversion","pair_momentum")
SCOPES=("ALL","FX","NON_FX_DIAGNOSTIC")

def stamp():return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def log(s):
    line=f"[{stamp()}] {s}"; print(line,flush=True)
    with MASTER.open("a",encoding="utf-8") as f:f.write(line+"\n")
def status(phase,msg=""):
    STATUS.write_text(
      f"AutoLab Continuous V1 STAGE 0005\nDate: {stamp()}\nPhase: {phase}\nMessage: {msg}\n"
      "2019-2026=RESEARCH EXPOSEE\nHOLDOUT HISTORIQUE=AUCUN\nLIVE=INTERDIT\n",
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
    if sha(PROTOCOL)!=PROTOCOL_SHA:raise RuntimeError("protocol SHA mismatch")
    if sha(MANIFEST)!=MANIFEST_SHA:raise RuntimeError("manifest SHA mismatch")
    m=rows(MANIFEST)
    if len(m)!=23:raise RuntimeError(f"manifest attendu 23 obtenu {len(m)}")
    byslot={r["slot"]:r for r in m}
    for pair,a,b,cls in PAIRS:
        for slot in (a,b):
            if slot not in byslot:raise RuntimeError("slot absent "+slot)
            r=byslot[slot]; p=DATA/(r["symbol"]+".csv")
            if not p.exists():raise RuntimeError("source absente "+str(p))
            if sha(p).lower()!=r["sha256"].lower():raise RuntimeError("source SHA mismatch "+slot)
    return byslot

def load_slot(meta):
    out={}
    p=DATA/(meta["symbol"]+".csv")
    for r in rows(p):
        try:
            dt=datetime.strptime(r["time"],"%Y.%m.%d %H:%M")
            if dt.year<2018 or dt.year>2026:continue
            out[dt]=(
              float(r["open"].replace(",",".")),
              float(r["close"].replace(",",".")),
              float(r["spread_points"].replace(",",".")),
              float(r["point"].replace(",","."))
            )
        except Exception:pass
    return out

def aligned_pair(a,b):
    ts=sorted(set(a).intersection(b))
    out=[]
    for t in ts:
        ao,ac,asp,apt=a[t]; bo,bc,bsp,bpt=b[t]
        if ao<=0 or ac<=0 or bo<=0 or bc<=0:continue
        out.append((t,ao,ac,asp,apt,bo,bc,bsp,bpt))
    return out

def rolling_z(spreads,look):
    # z at i uses ONLY prior look values [i-look, i); current spread is excluded.
    z=[None]*len(spreads)
    s=0.0; ss=0.0
    for i,v in enumerate(spreads):
        if i>=look:
            if i==look:
                win=spreads[:look]; s=sum(win); ss=sum(x*x for x in win)
            mu=s/look
            var=max(0.0,ss/look-mu*mu)
            sd=math.sqrt(var)
            if sd>1e-12:z[i]=(v-mu)/sd
            old=spreads[i-look]
            s += v-old
            ss += v*v-old*old
    return z

def make_events(pair_name,cls,data,style,look,zlevel,hold):
    spreads=[math.log(x[2])-math.log(x[6]) for x in data]  # closeA / closeB
    zz=rolling_z(spreads,look)
    ev=[]; next_allowed=0
    for i in range(max(look+1,2),len(data)-hold-2):
        if i<next_allowed:continue
        t=data[i][0]
        if t.year<2019 or t.year>2026:continue
        z=zz[i]; zp=zz[i-1]
        if z is None or zp is None:continue
        if abs(z)<zlevel or abs(zp)>=zlevel:continue
        en=i+1; ex=i+1+hold
        if ex>=len(data):continue
        # Require same research horizon years only.
        if data[en][0].year<2019 or data[ex][0].year>2026:continue
        a_en=data[en][1]; b_en=data[en][5]
        a_ex=data[ex][1]; b_ex=data[ex][5]
        if min(a_en,b_en,a_ex,b_ex)<=0:continue
        ra=a_ex/a_en-1.0; rb=b_ex/b_en-1.0
        # residual positive => A rich vs B.
        side=1.0 if z>0 else -1.0
        mult=(-side) if style=="pair_mean_reversion" else side
        gross=0.5*mult*ra - 0.5*mult*rb
        cost=0.5*(data[en][3]*data[en][4]/a_en) + 0.5*(data[en][7]*data[en][8]/b_en)
        ev.append({
          "pair":pair_name,"class":cls,"year":t.year,"z_side":"POS" if z>0 else "NEG",
          "gross_bps":gross*10000.0,"cost_bps":cost*10000.0,
          "net_bps":(gross-cost)*10000.0
        })
        next_allowed=i+hold+1
    return ev

def trim_top(ev,pct,key):
    if not ev:return 0.0
    vals=sorted((x[key] for x in ev),reverse=True)
    n=max(1,int(math.ceil(len(vals)*pct)))
    vals=vals[n:]
    return mean(vals) if vals else 0.0

def eval_config(style,look,zlevel,hold,scope,events):
    if scope=="FX":e=[x for x in events if x["class"]=="FX"]
    elif scope=="NON_FX_DIAGNOSTIC":e=[x for x in events if x["class"]!="FX"]
    else:e=list(events)
    if not e:return None

    py=defaultdict(list); yy=defaultdict(list); zs=defaultdict(list)
    for x in e:
        py[x["pair"]].append(x["net_bps"])
        yy[x["year"]].append(x["net_bps"])
        zs[x["z_side"]].append(x["net_bps"])

    net=mean([x["net_bps"] for x in e])
    s2=mean([x["gross_bps"]-2*x["cost_bps"] for x in e])
    s3=mean([x["gross_bps"]-3*x["cost_bps"] for x in e])
    t1=trim_top(e,.01,"net_bps")
    t5=trim_top(e,.05,"net_bps")

    pos_pairs=sum(1 for v in py.values() if mean(v)>0)
    pair_ratio=pos_pairs/len(py)
    full=[y for y in range(2019,2026) if y in yy]
    pos_years=sum(1 for y in full if mean(yy[y])>0)
    h1=[x["net_bps"] for x in e if 2019<=x["year"]<=2022]
    h2=[x["net_bps"] for x in e if 2023<=x["year"]<=2025]
    zpos=mean(zs["POS"]); zneg=mean(zs["NEG"])

    contrib={k:max(0.0,sum(v)) for k,v in py.items()}
    total=sum(contrib.values())
    maxshare=(max(contrib.values())/total) if total>0 else 1.0

    pair_gate=(pair_ratio>=0.625 if scope=="ALL" else pair_ratio>=0.60)
    lead_eligible=scope in ("ALL","FX")
    base_gates=[
      len(e)>=300,
      net>0.50,
      s2>0,
      s3>0,
      t1>0,
      t5>0,
      pair_gate,
      len(full)>=6 and pos_years>=5,
      mean(h1)>0 and mean(h2)>0,
      zpos>0 and zneg>0,
      maxshare<=0.35,
    ]
    return {
      "id":f"{style}__{scope}__LB{look}__Z{zlevel:.1f}__H{hold}",
      "style":style,"scope":scope,"lookback":look,"z_entry":zlevel,"hold":hold,
      "events":len(e),"mean_bps":net,"stress2_bps":s2,"stress3_bps":s3,
      "trim1_bps":t1,"trim5_bps":t5,
      "positive_pairs":pos_pairs,"eligible_pairs":len(py),"positive_pair_ratio":pair_ratio,
      "positive_years":pos_years,"eligible_years":len(full),
      "half1_bps":mean(h1),"half2_bps":mean(h2),
      "zpos_bps":zpos,"zneg_bps":zneg,
      "max_positive_pair_share":maxshare,
      "lead_eligible":lead_eligible,
      "_base_gates":base_gates
    }

def is_neighbor(a,b):
    if a["style"]!=b["style"] or a["scope"]!=b["scope"]:return False
    diffs=0
    for key,grid in (("lookback",LOOKBACKS),("z_entry",ZLEVELS),("hold",HOLDS)):
        if a[key]!=b[key]:
            ia=grid.index(a[key]); ib=grid.index(b[key])
            if abs(ia-ib)!=1:return False
            diffs+=1
    return diffs==1

def finalize(rows):
    for r in rows:
        neigh=[x for x in rows if is_neighbor(r,x)]
        good=sum(1 for x in neigh if x["mean_bps"]>0 and x["stress2_bps"]>0 and x["trim1_bps"]>0)
        ratio=(good/len(neigh)) if neigh else 0.0
        r["neighbor_good_ratio"]=ratio
        gates=list(r.pop("_base_gates"))+[ratio>=0.50]
        r["gates_passed"]=sum(gates)
        r["gate_bits"]="".join("1" if g else "0" for g in gates)
        r["lead"]="YES" if r["lead_eligible"] and all(gates) else "NO"
    rows.sort(key=lambda x:(x["lead"]=="YES",x["gates_passed"],x["mean_bps"]),reverse=True)
    return rows

def write_csv(path,data):
    if not data:return
    with path.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]),delimiter=';');w.writeheader();w.writerows(data)

def upload():
    uploaders=[
      B/"AUTOLAB_CONTINUOUS_GUARD_v2_1"/"AUTOLOOP_UPLOAD_ROBUST.ps1",
      B/"AUTOLAB_CONTINUOUS_GUARD_v2"/"AUTOLOOP_UPLOAD_ROBUST.ps1",
      B/"MT5_AutoLab_v0.23.1_METAL_EXECUTION"/"AUTOLOOP_UPLOAD_ROBUST_V0231.ps1",
      B/"AUTOLAB_CONTINUOUS_LOOP_v1"/"MT5_AutoLab_v0.23.1_LOOPTEST"/"AUTOLOOP_UPLOAD_ROBUST_V0231.ps1"
    ]
    up=next((p for p in uploaders if p.exists()),None)
    if not up:raise RuntimeError("uploader robuste introuvable")
    msg=("AUTOLAB CONTINUOUS V1 STAGE 0005 : recherche pair-relative-value terminee. Analyse le ZIP; "
         "si aucune vraie decision utilisateur n est necessaire, publie automatiquement STAGE 0006 dans "
         ".autolab_continuous_v1/stages/0006 avec MANIFEST.json puis READY.txt en dernier. "
         "2019-2026 reste recherche exposee; aucun holdout historique intact; aucun live.")
    p=subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(up),
                      "-FilePath",str(HANDOFF),"-Message",msg,"-MarkerPath",str(MARKER)],timeout=420)
    log(f"UPLOAD exit={p.returncode}")

def main():
    MASTER.write_text("",encoding="utf-8")
    try:
        status("VERIFY")
        byslot=verify()
        log("sources/pairs SHA PASS")

        slots=sorted({x for _,a,b,_ in PAIRS for x in (a,b)})
        loaded={s:load_slot(byslot[s]) for s in slots}
        pairdata={}
        for name,a,b,cls in PAIRS:
            d=aligned_pair(loaded[a],loaded[b])
            if len(d)<10000:raise RuntimeError(f"pair {name} historique insuffisant {len(d)}")
            pairdata[name]=(cls,d)
            log(f"{name} synchronized_bars={len(d)}")

        # Precompute event sets by pair+style+grid.
        cache={}
        for name,a,b,cls in PAIRS:
            _,d=pairdata[name]
            for style in STYLES:
              for lb in LOOKBACKS:
               for z in ZLEVELS:
                for hold in HOLDS:
                  cache[(name,style,lb,z,hold)]=make_events(name,cls,d,style,lb,z,hold)

        rr=[]
        for style in STYLES:
          for lb in LOOKBACKS:
           for z in ZLEVELS:
            for hold in HOLDS:
             all_ev=[]
             for name,_,_,_ in PAIRS:
                 all_ev.extend(cache[(name,style,lb,z,hold)])
             for scope in SCOPES:
                 x=eval_config(style,lb,z,hold,scope,all_ev)
                 if x:rr.append(x)

        if len(rr)!=162:raise RuntimeError(f"evaluations attendues 162 obtenu {len(rr)}")
        rr=finalize(rr)
        write_csv(RESULTS,rr);write_csv(TOP,rr[:20])
        leads=[x for x in rr if x["lead"]=="YES"]
        phase="ROBUST_PAIR_RELATIVE_VALUE_LEAD" if leads else "NO_ROBUST_PAIR_RELATIVE_VALUE_LEAD"

        lines=[f"AutoLab Continuous STAGE 0005 - {phase}",
               f"Evaluations: {len(rr)} | leads: {len(leads)}",""]
        for x in rr[:12]:
            lines.append(
              f"{x['id']} gates={x['gates_passed']}/12 events={x['events']} "
              f"mean={x['mean_bps']:+.3f}bps x2={x['stress2_bps']:+.3f} x3={x['stress3_bps']:+.3f} "
              f"trim1={x['trim1_bps']:+.3f} trim5={x['trim5_bps']:+.3f} "
              f"pairs={x['positive_pairs']}/{x['eligible_pairs']} years={x['positive_years']}/{x['eligible_years']} "
              f"halves=({x['half1_bps']:+.3f},{x['half2_bps']:+.3f}) "
              f"zsides=({x['zpos_bps']:+.3f},{x['zneg_bps']:+.3f}) neigh={x['neighbor_good_ratio']:.0%}"
            )
        SUMMARY.write_text("\n".join(lines)+"\n",encoding="utf-8")
        FINAL.write_text("# "+lines[0]+"\n\n"+"\n".join("- "+x for x in lines[1:] if x)+"\n",encoding="utf-8")
        status(phase,f"leads={len(leads)}")

        files=[RESULTS,TOP,SUMMARY,FINAL,STATUS,MASTER,PROTOCOL,MANIFEST,PKG/"RESEARCH_STAGE0005.py"]
        with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as zf:
            for p in files:
                if p.exists():zf.write(p,p.name)
        log(f"ZIP={HANDOFF} SHA={sha(HANDOFF)}")
        upload()
        return 0
    except Exception as e:
        ERROR.write_text(traceback.format_exc(),encoding="utf-8")
        status("TECHNICAL_ERROR",str(e)); log("ERROR "+str(e))
        with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED) as zf:
            for p in (ERROR,STATUS,MASTER,PROTOCOL,MANIFEST,PKG/"RESEARCH_STAGE0005.py"):
                if p.exists():zf.write(p,p.name)
        try:upload()
        except Exception as u:log("UPLOAD ERROR "+str(u))
        return 20

if __name__=="__main__":
    raise SystemExit(main())
