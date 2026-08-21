from pathlib import Path
import csv,json,math,hashlib,zipfile,subprocess,traceback,urllib.request

B=Path(r"C:\dev_EA_MT5")
REP=B/"reports"; LOG=B/"logs"; A=B/"autolab"/"continuous_stage_0011"
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
STAGE10LOCK=PKG/"STAGE0010_RESULT_LOCK.json"
PROTOCOL=PKG/"RESEARCH_PROTOCOL_STAGE0011.json"
UPLOADER=PKG/"UPLOAD_STAGE0011_RESULT.ps1"

MANIFEST_SHA="f12a6b89ac3e06276c10cf1821f0a1868aed9b5cca1c2c9b412ef991875a370c"
LOCK_SHA="c208bea3a979b5e5f860b40317dd434dc3e6778e864db6934a375ffaed64722e"
STAGE10LOCK_SHA="10fe039148bf3a6f405247454d1de5e86ed2f602f45faaf6902ce26b19c2d849"
PROTOCOL_SHA="e93a62843e295823b4f7c6e0ff116fd85a460e3750a6be57b023c95616a7bd35"
STAGE10_HANDOFF_SHA="6daec3091671147be71c8cedf0d984d0e7d26a635ff219094c312d93f3c2f296"

MASTER=LOG/"AUTOLAB_STAGE0011.log"
STATUS=LOG/"AUTOLAB_STATUS_STAGE0011.txt"
ERROR=LOG/"AUTOLAB_STAGE0011_ERROR.txt"
RESULTS=REP/"AUTOLAB_DISCOVERY_RESULTS_STAGE0011.csv"
TOP=REP/"AUTOLAB_DISCOVERY_TOP20_STAGE0011.csv"
SUMMARY=REP/"AUTOLAB_SUMMARY_STAGE0011.txt"
FINAL=REP/"AUTOLAB_FINAL_STAGE0011.md"
FROZEN=REP/"FROZEN_DISCOVERY_CANDIDATE_STAGE0011.json"
DONE=REP/"STAGE0011_RESULT_DONE.json"
HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0011_DISCOVERY.zip"
MARKER=A/"UPLOAD_CONFIRMED.txt"
SHA_SIDE=A/"HANDOFF_STAGE0011_SHA256.txt"
STAGE10_HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0010_DISCOVERY.zip"

for k,v in {
    "MANIFEST":MANIFEST,"LOCK":LOCK,"PROTOCOL":PROTOCOL,
    "MANIFEST_SHA":MANIFEST_SHA,"LOCK_SHA":LOCK_SHA,"PROTOCOL_SHA":PROTOCOL_SHA,
    "MASTER":MASTER,"STATUS":STATUS,"ERROR":ERROR,"RESULTS":RESULTS,"TOP":TOP,
    "SUMMARY":SUMMARY,"FINAL":FINAL,"FROZEN":FROZEN,"HANDOFF":HANDOFF,"MARKER":MARKER
}.items(): ns[k]=v

sha=ns["sha"]; rows=ns["rows"]; log=ns["log"]; status=ns["status"]
load=ns["load"]; atr14=ns["atr14"]; write_csv=ns["write_csv"]
base_evaluate=ns["evaluate"]; finalize_base=ns["finalize"]

def verify():
    if sha(MANIFEST)!=MANIFEST_SHA: raise RuntimeError("discovery manifest SHA mismatch")
    if sha(LOCK)!=LOCK_SHA: raise RuntimeError("validation lock SHA mismatch")
    if sha(STAGE10LOCK)!=STAGE10LOCK_SHA: raise RuntimeError("stage0010 result lock SHA mismatch")
    if sha(PROTOCOL)!=PROTOCOL_SHA: raise RuntimeError("protocol SHA mismatch")
    s10=json.loads(STAGE10LOCK.read_text(encoding="utf-8"))
    if s10.get("phase")!="NO_ROBUST_DISCOVERY_LEAD" or int(s10.get("robust_leads",-1))!=0:
        raise RuntimeError("stage0010 outcome incompatible")
    if s10.get("frozen_candidate_present_in_handoff") is not False:
        raise RuntimeError("stage0010 candidate exists: validation path required, not stage0011")
    if not STAGE10_HANDOFF.exists() or sha(STAGE10_HANDOFF).lower()!=STAGE10_HANDOFF_SHA:
        raise RuntimeError("exact stage0010 handoff missing/mismatch; NEVER recalculate stage0010")
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
    for fam in ("streak_continuation","streak_reversal"):
        for n in (3,5,7):
            for hold in (8,24,72):
                H.append({"family":fam,"run_len":n,"hold":hold})
    for fam in ("alternation_continuation","alternation_reversal"):
        for n in (4,6):
            for hold in (8,24,72):
                H.append({"family":fam,"alt_len":n,"hold":hold})
    if len(H)!=48:
        raise RuntimeError("hypothesis count != 48")
    for h in H:
        span=h.get("run_len",h.get("alt_len"))
        key="RUN" if "run_len" in h else "ALT"
        h["id"]=f'{h["family"]}__{key}{span}__H{h["hold"]}'
    return H

def close_sign(d,j):
    delta=d[j]["c"]-d[j-1]["c"]
    return 1 if delta>0 else (-1 if delta<0 else 0)

def signal(h,d,i):
    fam=h["family"]
    if "run_len" in h:
        n=h["run_len"]
        signs=[close_sign(d,j) for j in range(i-n+1,i+1)]
        if not signs or 0 in signs or any(s!=signs[0] for s in signs[1:]):
            return None
        q="LONG" if signs[-1]>0 else "SHORT"
    else:
        n=h["alt_len"]
        signs=[close_sign(d,j) for j in range(i-n+1,i+1)]
        if not signs or 0 in signs:
            return None
        if any(signs[k]==signs[k-1] for k in range(1,len(signs))):
            return None
        q="LONG" if signs[-1]>0 else "SHORT"
    if fam.endswith("reversal"):
        q="SHORT" if q=="LONG" else "LONG"
    return q

def make_events(meta,d,a,h):
    ev=[]; nxt=0; hold=h["hold"]
    span=h.get("run_len",h.get("alt_len"))
    start=max(250,span+2)
    for i in range(start,len(d)-hold-2):
        if i<nxt or a[i] is None or a[i]<=0:
            continue
        y=d[i]["dt"].year
        if y<2019 or y>2026:
            continue
        q=signal(h,d,i)
        if not q:
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
    r["run_len"]=h.get("run_len","")
    r["alt_len"]=h.get("alt_len","")
    return r

def grids(f):
    if f.startswith("streak_"):
        return {"run_len":[3,5,7],"hold":[8,24,72]}
    return {"alt_len":[4,6],"hold":[8,24,72]}

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
    keys=("id","family","hold","run_len","alt_len")
    p={"chain_id":"AUTOLAB_CONTINUOUS_V1","stage":"0011","status":"FROZEN_DISCOVERY_CANDIDATE",
       "candidate":{k:best.get(k,"") for k in keys},
       "discovery_metrics":{k:best[k] for k in best if k not in keys},
       "stage0010_handoff_sha256":STAGE10_HANDOFF_SHA,
       "discovery_manifest_sha256":MANIFEST_SHA,
       "protocol_sha256":PROTOCOL_SHA,
       "validation_lock_sha256":LOCK_SHA,
       "validation_status":"LOCKED_NOT_EXTRACTED_NOT_ANALYZED",
       "rule":"exact family/parameters only; no alternatives in validation",
       "frozen_at":ns["stamp"]()}
    FROZEN.write_text(json.dumps(p,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return p

def upload():
    if MARKER.exists():
        return 0
    msg=("AUTOLAB CONTINUOUS V1 - RESULTAT STAGE 0011 EXISTANT. Analyse le ZIP discovery. "
         "Ne recalcule jamais STAGE 0011. Si aucune vraie decision scientifique utilisateur n'est necessaire, "
         "publie automatiquement STAGE 0012 avec MANIFEST.json puis READY.txt en dernier. "
         "Validation Stage0006 verrouillee sauf si FROZEN_DISCOVERY_CANDIDATE_STAGE0011.json existe. Aucun live.")
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
        log("RESULTAT STAGE0011 FIGE -> aucun recalcul, upload seulement")
        return upload()
    MASTER.write_text("",encoding="utf-8")
    m=verify()
    status("RESEARCH","structurally distinct serial-dependence/sign-sequence tournament")
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
      f"AutoLab Continuous STAGE 0011 - {phase}",
      f"Discovery instruments: {len(m)} | categories: {len(set(x['category'] for x in m))}",
      f"Hypotheses: {len(hs)} | robust leads: {sum(x['lead']=='YES' for x in rr)}",
      "Structural family: close-to-close sign serial dependence / streak and alternation",
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
    DONE.write_text(json.dumps({"chain_id":"AUTOLAB_CONTINUOUS_V1","stage":"0011","phase":phase,
       "protocol_sha256":PROTOCOL_SHA,"stage0010_handoff_sha256":STAGE10_HANDOFF_SHA,
       "validation_status":"LOCKED_NOT_EXTRACTED_NOT_ANALYZED","completed_at":ns["stamp"]()},indent=2)+"\n")
    files=[RESULTS,TOP,SUMMARY,FINAL,STATUS,MASTER,DONE,MANIFEST,LOCK,STAGE10LOCK,PROTOCOL,PKG/"RESEARCH_STAGE0011.py"]
    if FROZEN.exists():
        files.append(FROZEN)
    with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:
            if p.exists():
                z.write(p,p.name)
    SHA_SIDE.write_text(sha(HANDOFF)+"\n")
    log(f"RESULT FROZEN SHA={sha(HANDOFF)}")
    return upload()

if __name__=="__main__":
    try:
        raise SystemExit(run())
    except Exception as e:
        ERROR.write_text(traceback.format_exc(),encoding="utf-8")
        try:
            status("TECHNICAL_ERROR",str(e))
        except Exception:
            pass
        print(traceback.format_exc(),flush=True)
        raise SystemExit(20)
