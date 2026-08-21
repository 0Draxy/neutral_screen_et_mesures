from pathlib import Path
import csv,json,math,hashlib,zipfile,subprocess,traceback,urllib.request

B=Path(r"C:\dev_EA_MT5")
REP=B/"reports"; LOG=B/"logs"; A=B/"autolab"/"continuous_stage_0010"
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
STAGE7LOCK=PKG/"STAGE0007_RESULT_LOCK.json"
PROTOCOL=PKG/"RESEARCH_PROTOCOL_STAGE0010.json"
UPLOADER=PKG/"UPLOAD_STAGE0010_RESULT.ps1"

MANIFEST_SHA="f12a6b89ac3e06276c10cf1821f0a1868aed9b5cca1c2c9b412ef991875a370c"
LOCK_SHA="c208bea3a979b5e5f860b40317dd434dc3e6778e864db6934a375ffaed64722e"
STAGE7LOCK_SHA="f460f47ce91710a2e482b3d4fdc823417ab3d34fe388951b7c0416999d54cd0e"
PROTOCOL_SHA="9836c055017fbe5bcfdd860d091672c4b740d041457d15fece501d67ea439795"
STAGE7_HANDOFF_SHA="d06e5c0931280e1c5fbfad3b6a6f2cca6ebd399fb0ca93f2407a19d1d53c757e"

MASTER=LOG/"AUTOLAB_STAGE0010.log"
STATUS=LOG/"AUTOLAB_STATUS_STAGE0010.txt"
ERROR=LOG/"AUTOLAB_STAGE0010_ERROR.txt"
RESULTS=REP/"AUTOLAB_DISCOVERY_RESULTS_STAGE0010.csv"
TOP=REP/"AUTOLAB_DISCOVERY_TOP20_STAGE0010.csv"
SUMMARY=REP/"AUTOLAB_SUMMARY_STAGE0010.txt"
FINAL=REP/"AUTOLAB_FINAL_STAGE0010.md"
FROZEN=REP/"FROZEN_DISCOVERY_CANDIDATE_STAGE0010.json"
DONE=REP/"STAGE0010_RESULT_DONE.json"
HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0010_DISCOVERY.zip"
MARKER=A/"UPLOAD_CONFIRMED.txt"
SHA_SIDE=A/"HANDOFF_STAGE0010_SHA256.txt"
STAGE7_HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0007_DISCOVERY.zip"

for k,v in {
    "MANIFEST":MANIFEST,"LOCK":LOCK,"PROTOCOL":PROTOCOL,
    "MANIFEST_SHA":MANIFEST_SHA,"LOCK_SHA":LOCK_SHA,"PROTOCOL_SHA":PROTOCOL_SHA,
    "MASTER":MASTER,"STATUS":STATUS,"ERROR":ERROR,"RESULTS":RESULTS,"TOP":TOP,
    "SUMMARY":SUMMARY,"FINAL":FINAL,"FROZEN":FROZEN,"HANDOFF":HANDOFF,"MARKER":MARKER
}.items(): ns[k]=v

sha=ns["sha"]; rows=ns["rows"]; mean=ns["mean"]; log=ns["log"]; status=ns["status"]
load=ns["load"]; atr14=ns["atr14"]; atr_ratio72=ns["atr_ratio72"]
evaluate=ns["evaluate"]; finalize_base=ns["finalize"]; write_csv=ns["write_csv"]

def verify():
    if sha(MANIFEST)!=MANIFEST_SHA: raise RuntimeError("discovery manifest SHA mismatch")
    if sha(LOCK)!=LOCK_SHA: raise RuntimeError("validation lock SHA mismatch")
    if sha(STAGE7LOCK)!=STAGE7LOCK_SHA: raise RuntimeError("stage0007 result lock SHA mismatch")
    if sha(PROTOCOL)!=PROTOCOL_SHA: raise RuntimeError("protocol SHA mismatch")
    s7=json.loads(STAGE7LOCK.read_text(encoding="utf-8"))
    if s7.get("phase")!="NO_ROBUST_DISCOVERY_LEAD" or int(s7.get("robust_leads",-1))!=0:
        raise RuntimeError("stage0007 outcome incompatible")
    if s7.get("frozen_candidate_present_in_handoff") is not False:
        raise RuntimeError("stage0007 candidate exists: validation path required, not stage0010")
    if not STAGE7_HANDOFF.exists() or sha(STAGE7_HANDOFF).lower()!=STAGE7_HANDOFF_SHA:
        raise RuntimeError("exact stage0007 handoff missing/mismatch; NEVER recalculate stage0007")
    lock=json.loads(LOCK.read_text(encoding="utf-8"))
    if lock.get("price_data_extracted") is not False or lock.get("price_data_analyzed") is not False:
        raise RuntimeError("validation lock violated")
    m=rows(MANIFEST)
    if len(m)!=29 or len({r["category"] for r in m})!=8: raise RuntimeError("discovery pool mismatch")
    for r in m:
        p=Path(r["path"])
        if not p.exists() or sha(p).lower()!=r["sha256"].lower():
            raise RuntimeError("discovery data missing/SHA mismatch "+r["symbol"])
    return m

def hypotheses():
    H=[]
    for fam in ("wide_bar_momentum","wide_bar_reversal"):
        for ra in (1.25,1.75):
            for cl in (0.65,0.80):
                for hold in (2,4,8):
                    H.append({"family":fam,"range_atr":ra,"close_location":cl,"hold":hold})
    for ws in (0.45,0.60):
        for hold in (2,4,8): H.append({"family":"wick_rejection","wick_share":ws,"hold":hold})
    for fam in ("outside_bar_momentum","outside_bar_reversal"):
        for hold in (2,4,8): H.append({"family":fam,"hold":hold})
    for hold in (2,4,8): H.append({"family":"inside_breakout","hold":hold})
    for fam in ("close_extreme_momentum","close_extreme_reversal"):
        for cl in (0.75,0.85):
            for hold in (2,4,8): H.append({"family":fam,"close_location":cl,"hold":hold})
    if len(H)!=51: raise RuntimeError("hypothesis count != 51")
    for h in H:
        parts=[h["family"],f"H{h['hold']}"]
        if "range_atr" in h: parts.append(f"RA{h['range_atr']}")
        if "close_location" in h: parts.append(f"CL{h['close_location']}")
        if "wick_share" in h: parts.append(f"W{h['wick_share']}")
        h["id"]="__".join(parts)
    return H

def signal(h,d,a,i):
    x=d[i]; rng=x["h"]-x["l"]
    if rng<=0 or a[i] is None or a[i]<=0: return None
    clv=(x["c"]-x["l"])/rng
    b=1 if x["c"]>x["o"] else (-1 if x["c"]<x["o"] else 0)
    fam=h["family"]
    if fam.startswith("wide_bar_"):
        if rng/a[i]<h["range_atr"]: return None
        cl=h["close_location"]; q="LONG" if b>0 and clv>=cl else ("SHORT" if b<0 and clv<=1-cl else None)
        if q and fam.endswith("reversal"): q="SHORT" if q=="LONG" else "LONG"
        return q
    if fam=="wick_rejection":
        hi=max(x["o"],x["c"]); lo=min(x["o"],x["c"])
        up=(x["h"]-hi)/rng; dn=(lo-x["l"])/rng; w=h["wick_share"]
        if dn>=w and dn>up and clv>=.5: return "LONG"
        if up>=w and up>dn and clv<=.5: return "SHORT"
        return None
    if fam.startswith("outside_bar_"):
        p=d[i-1]
        if not(x["h"]>p["h"] and x["l"]<p["l"]) or b==0: return None
        q="LONG" if b>0 else "SHORT"
        if fam.endswith("reversal"): q="SHORT" if q=="LONG" else "LONG"
        return q
    if fam=="inside_breakout":
        ins=d[i-1]; mom=d[i-2]
        if not(ins["h"]<=mom["h"] and ins["l"]>=mom["l"]): return None
        return "LONG" if x["c"]>mom["h"] else ("SHORT" if x["c"]<mom["l"] else None)
    if fam.startswith("close_extreme_"):
        cl=h["close_location"]; q="LONG" if b>0 and clv>=cl else ("SHORT" if b<0 and clv<=1-cl else None)
        if q and fam.endswith("reversal"): q="SHORT" if q=="LONG" else "LONG"
        return q
    return None

def make_events(meta,d,a,vr,h):
    ev=[]; nxt=0; hold=h["hold"]
    for i in range(40,len(d)-hold-2):
        if i<nxt or a[i] is None or a[i]<=0: continue
        y=d[i]["dt"].year
        if y<2019 or y>2026: continue
        q=signal(h,d,a,i)
        if not q: continue
        en=i+1; ex=en+hold
        gross=(d[ex]["o"]-d[en]["o"]) if q=="LONG" else (d[en]["o"]-d[ex]["o"])
        cost=d[en]["sp"]*d[en]["pt"]
        ev.append({"symbol":meta["symbol"],"category":meta["category"],"year":y,
                   "direction":q,"gross":gross/a[i],"cost":cost/a[i],"net":(gross-cost)/a[i]})
        nxt=i+hold+1
    return ev

def grids(f):
    if f.startswith("wide_bar_"): return {"hold":[2,4,8],"range_atr":[1.25,1.75],"close_location":[0.65,0.80]}
    if f=="wick_rejection": return {"hold":[2,4,8],"wick_share":[0.45,0.60]}
    if f in ("outside_bar_momentum","outside_bar_reversal","inside_breakout"): return {"hold":[2,4,8]}
    return {"hold":[2,4,8],"close_location":[0.75,0.85]}

def is_neighbor(a,b):
    if a["family"]!=b["family"]: return False
    dif=0
    for k,g in grids(a["family"]).items():
        if a.get(k,"")!=b.get(k,""):
            try:
                if abs(g.index(a[k])-g.index(b[k]))!=1: return False
            except: return False
            dif+=1
    return dif==1

ns["is_neighbor"]=is_neighbor
finalize=finalize_base

def freeze_if_lead(rr):
    leads=[r for r in rr if r["lead"]=="YES"]
    if not leads: FROZEN.unlink(missing_ok=True); return None
    best=leads[0]
    keys=("id","family","hold","range_atr","close_location","wick_share")
    p={"chain_id":"AUTOLAB_CONTINUOUS_V1","stage":"0010","status":"FROZEN_DISCOVERY_CANDIDATE",
       "candidate":{k:best.get(k,"") for k in keys},
       "discovery_metrics":{k:best[k] for k in best if k not in keys},
       "stage0007_handoff_sha256":STAGE7_HANDOFF_SHA,"discovery_manifest_sha256":MANIFEST_SHA,
       "protocol_sha256":PROTOCOL_SHA,"validation_lock_sha256":LOCK_SHA,
       "validation_status":"LOCKED_NOT_EXTRACTED_NOT_ANALYZED",
       "rule":"exact family/parameters only; no alternatives in validation","frozen_at":ns["stamp"]()}
    FROZEN.write_text(json.dumps(p,indent=2,ensure_ascii=False)+"\n",encoding="utf-8"); return p

def upload():
    if MARKER.exists(): return 0
    msg=("AUTOLAB CONTINUOUS V1 - RESULTAT STAGE 0010 EXISTANT. Analyse le ZIP discovery. "
         "Ne recalcule jamais STAGE 0010. Si aucune vraie decision scientifique utilisateur n'est necessaire, "
         "publie automatiquement STAGE 0011 avec MANIFEST.json puis READY.txt en dernier. "
         "Validation Stage0006 verrouillee sauf si FROZEN_DISCOVERY_CANDIDATE_STAGE0010.json existe. Aucun live.")
    p=subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(UPLOADER),
        "-FilePath",str(HANDOFF),"-Message",msg,"-MarkerPath",str(MARKER)],timeout=600)
    log(f"UPLOAD exit={p.returncode}"); return p.returncode

def frozen_result():
    return DONE.exists() and HANDOFF.exists() and SHA_SIDE.exists() and SHA_SIDE.read_text().strip().lower()==sha(HANDOFF).lower()

def run():
    if MARKER.exists(): return 0
    if frozen_result():
        log("RESULTAT STAGE0010 FIGE -> aucun recalcul, upload seulement"); return upload()
    MASTER.write_text("",encoding="utf-8")
    m=verify(); status("RESEARCH","structurally distinct local bar tournament")
    hs=hypotheses(); all_ev={h["id"]:[] for h in hs}; byid={h["id"]:h for h in hs}
    for i,meta in enumerate(m,1):
        status("RESEARCH",f"{i}/{len(m)} {meta['symbol']}")
        d=load(meta); a=atr14(d); vr=atr_ratio72(a); log(f"{meta['symbol']} bars={len(d)}")
        for h in hs: all_ev[h["id"]].extend(make_events(meta,d,a,vr,h))
    rr=finalize([evaluate(byid[k],e) for k,e in all_ev.items()])
    write_csv(RESULTS,rr); write_csv(TOP,rr[:20]); frozen=freeze_if_lead(rr)
    phase="DISCOVERY_CANDIDATE_FROZEN" if frozen else "NO_ROBUST_DISCOVERY_LEAD"
    lines=[f"AutoLab Continuous STAGE 0010 - {phase}",
      f"Discovery instruments: {len(m)} | categories: {len(set(x['category'] for x in m))}",
      f"Hypotheses: {len(hs)} | robust leads: {sum(x['lead']=='YES' for x in rr)}",
      "Structural family: local completed-bar morphology / short pattern state",
      "Validation: LOCKED / NOT EXTRACTED / NOT ANALYZED",""]
    for x in rr[:10]: lines.append(f"{x['id']} gates={x['gates_passed']}/15 events={x['events']} eq={x['equal_symbol_mean_atr']:+.4f} s3={x['stress3_equal_atr']:+.4f} trim5={x['trim5_pooled_atr']:+.4f} sym+={x['positive_symbol_ratio']:.1%} cat+={x['positive_category_ratio']:.1%} years+={x['positive_years']}/{x['eligible_years']} neigh={x['neighbor_good_ratio']:.2f}")
    SUMMARY.write_text("\n".join(lines)+"\n",encoding="utf-8")
    FINAL.write_text("# "+lines[0]+"\n\n"+"\n".join("- "+x for x in lines[1:] if x)+"\n",encoding="utf-8")
    status(phase,f"leads={sum(x['lead']=='YES' for x in rr)}")
    DONE.write_text(json.dumps({"chain_id":"AUTOLAB_CONTINUOUS_V1","stage":"0010","phase":phase,
       "protocol_sha256":PROTOCOL_SHA,"stage0007_handoff_sha256":STAGE7_HANDOFF_SHA,
       "validation_status":"LOCKED_NOT_EXTRACTED_NOT_ANALYZED","completed_at":ns["stamp"]()},indent=2)+"\n")
    files=[RESULTS,TOP,SUMMARY,FINAL,STATUS,MASTER,DONE,MANIFEST,LOCK,STAGE7LOCK,PROTOCOL,PKG/"RESEARCH_STAGE0010.py"]
    if FROZEN.exists(): files.append(FROZEN)
    with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:
            if p.exists(): z.write(p,p.name)
    SHA_SIDE.write_text(sha(HANDOFF)+"\n"); log(f"RESULT FROZEN SHA={sha(HANDOFF)}")
    return upload()

if __name__=="__main__":
    try: raise SystemExit(run())
    except Exception as e:
        ERROR.write_text(traceback.format_exc(),encoding="utf-8")
        try: status("TECHNICAL_ERROR",str(e))
        except: pass
        print(traceback.format_exc(),flush=True); raise SystemExit(20)
