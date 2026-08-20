from pathlib import Path
import csv,json,hashlib,shutil,zipfile,subprocess,traceback,time,re
from datetime import datetime
from collections import defaultdict
import autolab_engine_stage0006 as b

B=Path(r"C:\dev_EA_MT5")
PKG=Path(__file__).resolve().parent
A=B/"autolab"/"continuous_stage_0006"
E=B/"experiments"/"continuous_stage_0006"
REP=B/"reports";LOG=B/"logs";CFG=B/"config"
DATA=B/"data"/"continuous_stage0006_discovery"
COMMON=Path(r"C:\Users\Daffy\AppData\Roaming\MetaQuotes\Terminal\Common\Files")
for d in (A,E,REP,LOG,CFG,DATA):d.mkdir(parents=True,exist_ok=True)

MASTER=LOG/"AUTOLAB_STAGE0006.log"
STATUS=LOG/"AUTOLAB_STATUS_STAGE0006.txt"
ERROR=LOG/"AUTOLAB_STAGE0006_ERROR.txt"
MANIFEST=REP/"AUTOLAB_DISCOVERY_MANIFEST_STAGE0006.csv"
FAILURES=REP/"AUTOLAB_DISCOVERY_FAILURES_STAGE0006.json"
SUMMARY=REP/"AUTOLAB_SUMMARY_STAGE0006.txt"
LOCK=B/"VALIDATION_POOL_STAGE0006_LOCKED.json"
HANDOFF=REP/"AUTOLAB_A_ENVOYER_CHATGPT_STAGE0006_NEW_POOL.zip"
UPLOAD_MARK=A/"UPLOAD_CONFIRMED.txt"

SELECTION=PKG/"POOL_SELECTION_STAGE0006.csv"
PROTOCOL=PKG/"POOL_PROTOCOL_STAGE0006.json"
SELECTION_SHA="21d8c85138242cd17a01095d90a3da474f4fb95794d441e6ac09c0e424ede077"
PROTOCOL_SHA="1d88b13b614bcfbcf1db45bf29573d0a5a3668155ade689177d45446ad937ff5"

b.A=A;b.E=E;b.REP=REP;b.LOG=LOG;b.CFG=CFG
b.CAND=A/"autolab_candidate.mq5";b.MASTER=MASTER

TARGETS={'SHARE_US': 8, 'SHARE_EU': 4, 'ETF': 4, 'CRYPTO': 3, 'COMMODITY': 4, 'INDEX_NEW': 3, 'FX_NEW': 3, 'BOND': 1}
MIN_ROWS=10000
MIN_TOTAL=24
MIN_CATEGORIES=6
ATTEMPTS=2

def stamp():return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def log(s):
    line=f"[{stamp()}] {s}";print(line,flush=True)
    with MASTER.open("a",encoding="utf-8") as f:f.write(line+"\n")
def status(phase,msg=""):
    STATUS.write_text(
      f"AutoLab Continuous V1 STAGE 0006\nDate: {stamp()}\nPhase: {phase}\nMessage: {msg}\n"
      "VALIDATION=LOCKED / NON EXTRAITE\nLIVE=INTERDIT\n",encoding="utf-8")
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
def safe(s):return re.sub(r"[^A-Za-z0-9]","_",s)

def verify_freeze():
    if sha(SELECTION)!=SELECTION_SHA:raise RuntimeError("selection SHA mismatch")
    if sha(PROTOCOL)!=PROTOCOL_SHA:raise RuntimeError("protocol SHA mismatch")
    sel=rows(SELECTION)
    vals=[x for x in sel if x["role"].startswith("VALIDATION")]
    if not vals:raise RuntimeError("validation list empty")
    lock={
      "chain_id":"AUTOLAB_CONTINUOUS_V1","stage":"0006",
      "selection_sha256":SELECTION_SHA,
      "validation_symbols":[x["symbol"] for x in vals],
      "validation_roles":[{"role":x["role"],"category":x["category"],"symbol":x["symbol"]} for x in vals],
      "price_data_extracted":False,"price_data_analyzed":False,
      "unlock_condition":"candidate frozen on discovery before validation extraction",
      "created":stamp()
    }
    LOCK.write_text(json.dumps(lock,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return sel

def exporter_mql():
    return r"""#property strict
#property version "0.06"
int fh=INVALID_HANDLE;datetime lastBar=0;int digits=0;double point=0.0;
string SafeName(string s){
 string out="";
 for(int i=0;i<StringLen(s);i++){
   ushort c=(ushort)StringGetCharacter(s,i);
   bool ok=((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9'));
   out+=ok?StringSubstr(s,i,1):"_";
 }
 return out;
}
int OnInit(){
 if(!MQLInfoInteger(MQL_TESTER))return INIT_FAILED;
 digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);point=SymbolInfoDouble(_Symbol,SYMBOL_POINT);
 string fn="AUTOLAB_STAGE0006_BARS_"+SafeName(_Symbol)+".csv";
 fh=FileOpen(fn,FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI,';');
 if(fh==INVALID_HANDLE)return INIT_FAILED;
 FileWrite(fh,"symbol","time","open","high","low","close","spread_points","tick_volume","real_volume","point","digits");
 return INIT_SUCCEEDED;
}
void OnDeinit(const int reason){if(fh!=INVALID_HANDLE)FileClose(fh);}
void OnTick(){
 datetime t=iTime(_Symbol,PERIOD_H1,0);if(t<=0||t==lastBar)return;lastBar=t;
 MqlRates r[];ArraySetAsSeries(r,true);if(CopyRates(_Symbol,PERIOD_H1,0,3,r)<3)return;
 FileWrite(fh,_Symbol,TimeToString(r[1].time,TIME_DATE|TIME_MINUTES),
   DoubleToString(r[1].open,digits),DoubleToString(r[1].high,digits),DoubleToString(r[1].low,digits),DoubleToString(r[1].close,digits),
   (int)r[1].spread,(long)r[1].tick_volume,(long)r[1].real_volume,DoubleToString(point,10),digits);
 FileFlush(fh);
}
"""

def parse_bar_file(path):
    rr=rows(path);out=[]
    for r in rr:
        try:out.append((datetime.strptime(r["time"],"%Y.%m.%d %H:%M"),r))
        except Exception:pass
    out.sort(key=lambda x:x[0])
    ded=[];last=None
    for t,r in out:
        if t==last:continue
        ded.append((t,r));last=t
    return ded

def cfg():
    return {"catalog_probe_symbol":"EURUSD","extraction_model":1,"tester_timeout_seconds":1800}

def try_extract(x,idx):
    sym=x["symbol"];sf=safe(sym);common=COMMON/f"AUTOLAB_STAGE0006_BARS_{sf}.csv";dest=DATA/f"{sf}.csv"
    last=None
    for attempt in range(1,ATTEMPTS+1):
        try:
            try:common.unlink()
            except FileNotFoundError:pass
            ed=E/f"extract_{idx:03d}_{sf}_a{attempt}"
            b.run_tester(cfg(),f"stage0006_{idx:03d}_{sf}_a{attempt}",ed,
                "2018.01.01","2026.08.06",symbol=sym,model=1,timeout=1800)
            if not common.exists():raise RuntimeError("CSV FILE_COMMON absent")
            shutil.copy2(common,dest)
            br=parse_bar_file(dest)
            if len(br)<MIN_ROWS:raise RuntimeError(f"rows={len(br)} < {MIN_ROWS}")
            return {"category":x["category"],"symbol":sym,"role_used":x["role"],
              "rows":len(br),"first":br[0][0].isoformat(sep=" "),"last":br[-1][0].isoformat(sep=" "),
              "sha256":sha(dest),"path":str(dest)}
        except Exception as exc:
            last=exc;log(f"EXTRACT FAIL {sym} attempt={attempt}: {exc}");time.sleep(3)
    return {"category":x["category"],"symbol":sym,"role":x["role"],"error":str(last)}

def build_pool(sel):
    status("COMPILE_EXPORTER")
    b.CAND.write_text(exporter_mql(),encoding="utf-8")
    b.compile_ea(E/"exporter_compile")
    bycat=defaultdict(list)
    for x in sel:
        if x["role"] in ("DISCOVERY_PRIMARY","DISCOVERY_RESERVE"):
            bycat[x["category"]].append(x)
    for c in bycat:
        bycat[c].sort(key=lambda x:(0 if x["role"]=="DISCOVERY_PRIMARY" else 1,int(x["rank_in_role"])))
    successes=[];fails=[];idx=0
    for cat,target in TARGETS.items():
        got=0
        for x in bycat.get(cat,[]):
            if got>=target:break
            idx+=1;status("EXTRACTION",f"{len(successes)} success | {cat} {got}/{target} | {x['symbol']}")
            r=try_extract(x,idx)
            if "error" in r:fails.append(r)
            else:successes.append(r);got+=1
        log(f"CATEGORY {cat} success={got} target={target}")
    cats=len(set(x["category"] for x in successes))
    if len(successes)<MIN_TOTAL or cats<MIN_CATEGORIES:
        raise RuntimeError(f"discovery pool insuffisant: success={len(successes)} categories={cats}")
    with MANIFEST.open("w",encoding="utf-8",newline="") as f:
        fields=["category","symbol","role_used","rows","first","last","sha256","path"]
        w=csv.DictWriter(f,fieldnames=fields,delimiter=';');w.writeheader();w.writerows(successes)
    FAILURES.write_text(json.dumps(fails,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return successes,fails

def make_handoff(reason):
    files=[MANIFEST,FAILURES,SUMMARY,STATUS,MASTER,LOCK,SELECTION,PROTOCOL,PKG/"RESEARCH_STAGE0006.py"]
    with zipfile.ZipFile(HANDOFF,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:
            if p.exists():z.write(p,p.name)
    log(f"HANDOFF {HANDOFF} SHA={sha(HANDOFF)} reason={reason}")

def upload():
    uploaders=[
      B/"AUTOLAB_CONTINUOUS_GUARD_v2_1"/"AUTOLOOP_UPLOAD_ROBUST.ps1",
      B/"AUTOLAB_CONTINUOUS_GUARD_v2"/"AUTOLOOP_UPLOAD_ROBUST.ps1",
      B/"AUTOLAB_CONTINUOUS_LOOP_v1"/"MT5_AutoLab_v0.23.1_LOOPTEST"/"AUTOLOOP_UPLOAD_ROBUST_V0231.ps1"
    ]
    up=next((p for p in uploaders if p.exists()),None)
    if not up:raise RuntimeError("uploader robuste introuvable")
    msg=("AUTOLAB CONTINUOUS V1 STAGE 0006 : nouveau pool cross-instrument construit. Analyse le ZIP; "
         "si aucune vraie decision utilisateur n est necessaire, publie automatiquement STAGE 0007 dans "
         ".autolab_continuous_v1/stages/0007 avec MANIFEST.json puis READY.txt en dernier. "
         "VALIDATION STAGE0006 reste verrouillee/non extraite; aucun live.")
    p=subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(up),
        "-FilePath",str(HANDOFF),"-Message",msg,"-MarkerPath",str(UPLOAD_MARK)],timeout=420)
    log(f"UPLOAD exit={p.returncode}")

def main():
    MASTER.write_text("",encoding="utf-8")
    try:
        status("VERIFY");sel=verify_freeze();log(f"FREEZE PASS selection_rows={len(sel)}")
        success,fails=build_pool(sel)
        cats=defaultdict(int)
        for x in success:cats[x["category"]]+=1
        lines=[
          "AutoLab Continuous STAGE 0006 - DISCOVERY_POOL_BUILT",
          f"Discovery successes: {len(success)} | failures: {len(fails)} | categories: {len(cats)}",
          "Validation: LOCKED / NOT EXTRACTED / NOT ANALYZED",
          "Selection SHA: "+SELECTION_SHA,
          "Discovery by category: "+", ".join(f"{k}={v}" for k,v in sorted(cats.items()))
        ]
        SUMMARY.write_text("\n".join(lines)+"\n",encoding="utf-8")
        status("DISCOVERY_POOL_BUILT",f"success={len(success)} categories={len(cats)} validation=LOCKED")
        make_handoff("DISCOVERY_POOL_BUILT");upload();return 0
    except Exception as exc:
        ERROR.write_text(traceback.format_exc(),encoding="utf-8")
        status("TECHNICAL_ERROR",str(exc));log("ERROR "+str(exc))
        SUMMARY.write_text("AutoLab Continuous STAGE 0006 - TECHNICAL_ERROR\n"+str(exc)+"\n",encoding="utf-8")
        make_handoff("TECHNICAL_ERROR")
        try:upload()
        except Exception as u:log("UPLOAD ERROR "+str(u))
        return 20
if __name__=="__main__":raise SystemExit(main())
