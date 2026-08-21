from pathlib import Path
import json,hashlib,zipfile,subprocess,traceback,urllib.request

B=Path(r"C:\dev_EA_MT5")
REP=B/"reports"; LOG=B/"logs"; A=B/"autolab"/"continuous_stage_0012"
PKG=Path(__file__).resolve().parent
for d in (REP,LOG,A): d.mkdir(parents=True,exist_ok=True)

BASE_URL="https://raw.githubusercontent.com/0Draxy/neutral_screen_et_mesures/main/.autolab_continuous_v1/stages/0007/RESEARCH_STAGE0007.py"
BASE_SHA="0b0a78be04ebd54c68faf0f7a2ae9ee80cc26f0adb1b33c383978b10b9b7130b"

raw=urllib.request.urlopen(BASE_URL,timeout=45).read()
if hashlib.sha256(raw).hexdigest()!=BASE_SHA:
    raise RuntimeError("STAGE0007 research base SHA mismatch")
ns={"__name__":"autolab_stage0007_base","__file__":str(PKG/"BASE_STAGE0007_REFERENCE.py")}
exec(compile(raw.decode("utf-8"),"BASE_STAGE0007_REFERENCE.py","exec"),ns)

MANIFEST=PKG/"DISCOVERY_MANIFEST_STAGE0006.csv"
LOCK=PKG/"VALIDATION_POOL_STAGE0006_LOCKED.json"
STAGE11LOCK=PKG/"STAGE0011_RESULT_LOCK.json"
PROTOCOL=PKG/"RESEARCH_PROTOCOL_STAGE0012.json"
UPLOADER=PKG/"UPLOAD_STAGE0012_RESULT.ps1"

MANIFEST_SHA="f12a6b89ac3e06276c10cf1821f0a1868aed9b5cca1c2c9b412ef991875a370c"
LOCK_SHA="c208bea3a979b5e5f860b40317dd434dc3e6778e864db6934a375ffaed64722e"
STAGE11LOCK_SHA="c258ea72d5f0c0629eed958932164b9c0836281e076e7dd7cd59de78ffe8401d"
PROTOCOL_CANON_SHA="63e10b5f6dead4bb081c540c01bfccb5b11731a397435da512440200b4f4b99d"
STAGE11_HANDOFF_SHA="cae1d6e42178a5a8c6c8ac31479b0628fd8bbb28315960dc9dc254c0af3f1cdd"

MASTER=LOG/"AUTOLAB_STAGE0012.log"
STATUS=LOG/"AUTOLAB_STATUS_STAGE0012.txt"
ERROR=LOG/"AUTOLAB_STAGE0012_ERROR.txt"
RESULTS=REP/"AUTOLAB_DISCOVERY_RESULTS_STAGE0012.csv"
TOP=REP/"AUTOLAB_DISCOVERY_TOP20_STAGE0012.csv"
SUMMARY=REP/"AUTOLAB_SUMMARY_STAGE0012.txt"
FINAL=REP/"AUTOLAB_FINAL_STAGE0012.md"
FROZEN=REP/"FROZEN_DISCOVERY_CANDIDATE_STAGE0012.json"
DONE=REP/"STAGE0012_RESULT_DONE.json"
HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0012_DISCOVERY.zip"
MARKER=A/"UPLOAD_CONFIRMED.txt"
SHA_SIDE=A/"HANDOFF_STAGE0012_SHA256.txt"
STAGE11_HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0011_DISCOVERY.zip"

for k,v in {
    "MANIFEST":MANIFEST,"LOCK":LOCK,"PROTOCOL":PROTOCOL,
    "MANIFEST_SHA":MANIFEST_SHA,"LOCK_SHA":LOCK_SHA,
    "MASTER":MASTER,"STATUS":STATUS,"ERROR":ERROR,"RESULTS":RESULTS,"TOP":TOP,
    "SUMMARY":SUMMARY,"FINAL":FINAL,"FROZEN":FROZEN,"HANDOFF":HANDOFF,"MARKER":MARKER
}.items(): ns[k]=v

sha=ns["sha"]; rows=ns["rows"]; load=ns["load"]; atr14=ns["atr14"]; write_csv=ns["write_csv"]
base_evaluate=ns["evaluate"]; finalize_base=ns["finalize"]; stamp=ns["stamp"]

def log(s):
    line=f"{stamp()} | {s}"
    print(line,flush=True)
    with MASTER.open("a",encoding="utf-8") as f: f.write(line+"\n")

def status(phase,message):
    STATUS.write_text(
        "AutoLab Continuous V1 STAGE 0012\n"
        f"Date: {stamp()}\n"
        f"Phase: {phase}\n"
        f"Message: {message}\n"
        "DISCOVERY=ACTIVE\n"
        "VALIDATION=LOCKED / NON EXTRAITE / NON ANALYSEE\n"
        "LIVE=INTERDIT\n",
        encoding="utf-8"
    )

def verify():
    if sha(MANIFEST)!=MANIFEST_SHA: raise RuntimeError("discovery manifest SHA mismatch")
    if sha(LOCK)!=LOCK_SHA: raise RuntimeError("validation lock SHA mismatch")
    if sha(STAGE11LOCK)!=STAGE11LOCK_SHA: raise RuntimeError("stage0011 result lock SHA mismatch")
    pobj=json.loads(PROTOCOL.read_text(encoding="utf-8"))
    pcanon=hashlib.sha256(json.dumps(pobj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()
    if pcanon!=PROTOCOL_CANON_SHA: raise RuntimeError("protocol semantic fingerprint mismatch")
    s11=json.loads(STAGE11LOCK.read_text(encoding="utf-8"))
    if s11.get("phase")!="NO_ROBUST_DISCOVERY_LEAD" or int(s11.get("robust_leads",-1))!=0:
        raise RuntimeError("stage0011 outcome incompatible")
    if s11.get("frozen_candidate_present_in_handoff") is not False:
        raise RuntimeError("stage0011 candidate exists: validation path required, not stage0012")
    if not STAGE11_HANDOFF.exists() or sha(STAGE11_HANDOFF).lower()!=STAGE11_HANDOFF_SHA:
        raise RuntimeError("exact stage0011 handoff missing/mismatch; NEVER recalculate stage0011")
    lock=json.loads(LOCK.read_text(encoding="utf-8"))
    if lock.get("price_data_extracted") is not False or lock.get("price_data_analyzed") is not False:
        raise RuntimeError("validation lock violated")
    m=rows(MANIFEST)
    if len(m)!=29 or len({r["category"] for r in m})!=8:
        raise RuntimeError("discovery pool mismatch")
    for r in m:
        p=Path(r["path"])
        if not p.exists() or sha(p).lower()!=r["sha256"].lower():
            raise RuntimeError("discovery data missing/SHA mismatch "+r["symbol"])
    return m

def hypotheses():
    H=[]
    for fam in ("weekday_long","weekday_short"):
        for wd in range(7):
            for hold in (8,24,72):
                H.append({"family":fam,"weekday":wd,"hold":hold})
    if len(H)!=42:
        raise RuntimeError(f"hypothesis count {len(H)} != 42")
    for h in H:
        h["id"]=f'{h["family"]}__WD{h["weekday"]}__H{h["hold"]}'
    return H

def first_bar_of_day(d,i):
    if i<=0: return False
    return d[i]["dt"].date()!=d[i-1]["dt"].date()

def make_events(meta,d,a,h):
    ev=[]; nxt=0; hold=h["hold"]; wd=h["weekday"]
    q="LONG" if h["family"]=="weekday_long" else "SHORT"
    for i in range(250,len(d)-hold-2):
        if i<nxt or a[i] is None or a[i]<=0:
            continue
        y=d[i]["dt"].year
        if y<2019 or y>2026:
            continue
        if d[i]["dt"].weekday()!=wd or not first_bar_of_day(d,i):
            continue
        en=i+1; ex=en+hold
        gross=(d[ex]["o"]-d[en]["o"]) if q=="LONG" else (d[en]["o"]-d[ex]["o"])
        cost=d[en]["sp"]*d[en]["pt"]
        ev.append({"symbol":meta["symbol"],"category":meta["category"],"year":y,
                   "direction":q,"gross":gross/a[i],"cost":cost/a[i],"net":(gross-cost)/a[i]})
        nxt=i+hold+1
    return ev

def evaluate(h,e):
    hb=dict(h)
    hb.setdefault("lookback",0)
    r=base_evaluate(hb,e)
    r["weekday"]=h["weekday"]
    return r

def grids(f):
    return {"weekday":[0,1,2,3,4,5,6],"hold":[8,24,72]}

def is_neighbor(a,b):
    if a["family"]!=b["family"]:
        return False
    dif=0
    for k,g in grids(a["family"]).items():
        if a.get(k,"")!=b.get(k,""):
            try:
                if abs(g.index(a[k])-g.index(b[k]))!=1:
                    return False
            except Exception:
                return False
            dif+=1
    return dif==1

ns["is_neighbor"]=is_neighbor
finalize=finalize_base

def freeze_if_lead(rr):
    leads=[r for r in rr if r["lead"]=="YES"]
    if not leads:
        FROZEN.unlink(missing_ok=True)
        return None
    best=leads[0]
    keys=("id","family","hold","weekday")
    p={"chain_id":"AUTOLAB_CONTINUOUS_V1","stage":"0012","status":"FROZEN_DISCOVERY_CANDIDATE",
       "candidate":{k:best.get(k,"") for k in keys},
       "discovery_metrics":{k:best[k] for k in best if k not in keys},
       "stage0011_handoff_sha256":STAGE11_HANDOFF_SHA,
       "discovery_manifest_sha256":MANIFEST_SHA,
       "protocol_sha256":sha(PROTOCOL),
       "validation_lock_sha256":LOCK_SHA,
       "validation_status":"LOCKED_NOT_EXTRACTED_NOT_ANALYZED",
       "rule":"exact family/parameters only; no alternatives in validation",
       "frozen_at":stamp()}
    FROZEN.write_text(json.dumps(p,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return p

def upload():
    if MARKER.exists():
        return 0
    msg=("AUTOLAB CONTINUOUS V1 - RESULTAT STAGE 0012 EXISTANT. Analyse le ZIP discovery. "
         "Ne recalcule jamais STAGE 0012. Si aucune vraie decision scientifique utilisateur n'est necessaire, "
         "publie automatiquement STAGE 0013 avec MANIFEST.json puis READY.txt en dernier. "
         "Validation Stage0006 verrouillee sauf si FROZEN_DISCOVERY_CANDIDATE_STAGE0012.json existe. Aucun live.")
    p=subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(UPLOADER),
        "-FilePath",str(HANDOFF),"-Message",msg,"-MarkerPath",str(MARKER)],timeout=600)
    log(f"UPLOAD exit={p.returncode}")
    return p.returncode

def frozen_result():
    return DONE.exists() and HANDOFF.exists() and SHA_SIDE.exists() and SHA_SIDE.read_text().strip().lower()==sha(HANDOFF).lower()

def run():
    if MARKER.exists():
        return 0
    if frozen_result():
        log("RESULTAT STAGE0012 FIGE -> aucun recalcul, upload seulement")
        return upload()
    MASTER.write_text("",encoding="utf-8")
    m=verify()
    status("RESEARCH","structurally distinct weekday seasonality tournament")
    hs=hypotheses()
    all_ev={h["id"]:[] for h in hs}
    byid={h["id"]:h for h in hs}
    for i,meta in enumerate(m,1):
        status("RESEARCH",f"{i}/{len(m)} {meta['symbol']}")
        d=load(meta); a=atr14(d)
        log(f"{meta['symbol']} bars={len(d)}")
        for h in hs:
            all_ev[h["id"]].extend(make_events(meta,d,a,h))
    rr=finalize([evaluate(byid[k],e) for k,e in all_ev.items()])
    write_csv(RESULTS,rr)
    write_csv(TOP,rr[:20])
    frozen=freeze_if_lead(rr)
    phase="DISCOVERY_CANDIDATE_FROZEN" if frozen else "NO_ROBUST_DISCOVERY_LEAD"
    lines=[
      f"AutoLab Continuous STAGE 0012 - {phase}",
      f"Discovery instruments: {len(m)} | categories: {len(set(x['category'] for x in m))}",
      f"Hypotheses: {len(hs)} | robust leads: {sum(x['lead']=='YES' for x in rr)}",
      "Structural family: deterministic weekday seasonality / fixed long-short direction",
      "Validation: LOCKED / NOT EXTRACTED / NOT ANALYZED",""
    ]
    for x in rr[:10]:
        lines.append(f"{x['id']} gates={x['gates_passed']}/15 events={x['events']} "
                     f"eq={x['equal_symbol_mean_atr']:+.4f} s3={x['stress3_equal_atr']:+.4f} "
                     f"trim5={x['trim5_pooled_atr']:+.4f} sym+={x['positive_symbol_ratio']:.1%} "
                     f"cat+={x['positive_category_ratio']:.1%} years+={x['positive_years']}/{x['eligible_years']} "
                     f"neigh={x['neighbor_good_ratio']:.2f}")
    SUMMARY.write_text("\n".join(lines)+"\n",encoding="utf-8")
    FINAL.write_text("# "+lines[0]+"\n\n"+"\n".join("- "+x for x in lines[1:] if x)+"\n",encoding="utf-8")
    status(phase,f"leads={sum(x['lead']=='YES' for x in rr)}")
    DONE.write_text(json.dumps({"chain_id":"AUTOLAB_CONTINUOUS_V1","stage":"0012","phase":phase,
       "protocol_sha256":sha(PROTOCOL),"stage0011_handoff_sha256":STAGE11_HANDOFF_SHA,
       "validation_status":"LOCKED_NOT_EXTRACTED_NOT_ANALYZED","completed_at":stamp()},indent=2)+"\n")
    files=[RESULTS,TOP,SUMMARY,FINAL,STATUS,MASTER,DONE,MANIFEST,LOCK,STAGE11LOCK,PROTOCOL,PKG/"RESEARCH_STAGE0012.py"]
    if FROZEN.exists(): files.append(FROZEN)
    with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:
            if p.exists(): z.write(p,p.name)
    SHA_SIDE.write_text(sha(HANDOFF)+"\n")
    log(f"RESULT FROZEN SHA={sha(HANDOFF)}")
    return upload()

if __name__=="__main__":
    try:
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception:
        ERROR.write_text(traceback.format_exc(),encoding="utf-8")
        status("ERROR",str(traceback.format_exc().splitlines()[-1]))
        raise SystemExit(20)
