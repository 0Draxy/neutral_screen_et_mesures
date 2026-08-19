from pathlib import Path
import importlib.util, subprocess, shutil, json, os, sys, time, hashlib, zipfile, traceback

# MT5 AutoLab v0.15 LOCAL — overlay on verified v0.14 infrastructure.
B = Path(r"C:\dev_EA_MT5")
PKG = Path(__file__).resolve().parent
PARENT_SOURCE = B / "MT5_AutoLab_v0.14_LOCAL" / "autolab_v014_local.py"
EXPECTED_PARENT_SHA256 = "dd2656fd7cb24fd8a708af2cd5a0ffed1d4e7023da31bf2e781a14d234c370c8"


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


if not PARENT_SOURCE.exists():
    raise RuntimeError("Source parent v0.14 absent: " + str(PARENT_SOURCE))
if file_sha256(PARENT_SOURCE).lower() != EXPECTED_PARENT_SHA256:
    raise RuntimeError("SHA256 source parent v0.14 incorrect")

spec = importlib.util.spec_from_file_location("autolab_v014_parent", PARENT_SOURCE)
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

# Rebind current-version paths before using parent infrastructure.
b.PKG = PKG
b.A = B / "autolab" / "v0.15"
b.E = B / "experiments" / "v0.15"
b.REP = B / "reports"
b.LOG = B / "logs"
b.CFG = B / "config"
b.CAND = b.A / "autolab_candidate.mq5"
b.FROZEN = b.A / "frozen_candidate.mq5"
b.CONF = b.CFG / "autolab_v015_local_config.json"
b.SUMMARY = b.REP / "AUTOLAB_SUMMARY_V015_LOCAL.txt"
b.FINAL_MD = b.REP / "AUTOLAB_FINAL_V015_LOCAL.md"
b.CANDIDATES_CSV = b.REP / "AUTOLAB_CANDIDATES_V015_LOCAL.csv"
b.MASTER = b.LOG / "AUTOLAB_V015_LOCAL.log"
b.ERR = b.LOG / "AUTOLAB_V015_LOCAL_ERROR.txt"
b.STATUS = b.LOG / "AUTOLAB_STATUS_V015_LOCAL.txt"
b.STATE = b.A / "campaign_state.json"
b.HANDOFF_ZIP = b.REP / "AUTOLAB_A_ENVOYER_CHATGPT_V015_LOCAL.zip"
b.HANDOFF_INDEX = b.REP / "AUTOLAB_A_ENVOYER_CHATGPT_V015_LOCAL.txt"
b.PARSE_DIAG = b.REP / "AUTOLAB_PARSE_DIAGNOSTIC_V015_LOCAL.txt"
b.LOOP_ID = B / "AUTOLOOP_V014_TO_V015_ID.txt"
b.AUTOLOOP_UPLOAD = B / "_AUTOLOOP_BRIDGE" / "AUTOLOOP_UPLOAD.ps1"
b.AUTOLOOP_UPLOAD_MARKER = b.A / "AUTOLOOP_V015_UPLOAD_DONE.txt"
for d in (b.REA, b.RR, b.A, b.E, b.REP, b.LOG, b.CFG):
    d.mkdir(parents=True, exist_ok=True)

b.FAMILIES = [
    {"id": "short_vol_core", "label": "SHORT MR + regime ATR raffine"},
    {"id": "short_vol_session", "label": "SHORT MR + ATR + session large"},
    {"id": "short_vol_slope", "label": "SHORT MR + ATR + pente EMA200"},
    {"id": "short_adaptive_or", "label": "SHORT MR + pente OU volatilite"},
]
b.FAMILY_ID = {f["id"]: i + 1 for i, f in enumerate(b.FAMILIES)}


def default_state():
    return {
        "version": "0.15", "status": "NEW", "started_at": "", "updated_at": "",
        "phase": "", "family": "", "variant": 0, "completed_discovery": 0,
        "selected": "", "frozen_hash": "",
    }


b.default_state = default_state


def show_progress(phase, current, total, detail=""):
    current = max(0, int(current)); total = max(1, int(total))
    pct = 100.0 * current / total
    suffix = (" | " + str(detail)) if detail else ""
    print(f"[{phase}] TEST {current}/{total} ({pct:5.1f}%){suffix}", flush=True)
    b.set_console_title(f"AutoLab v0.15 - {phase} - TEST {current}/{total}")


b.show_progress = show_progress


def write_runtime_status(c, message=""):
    s = b.load_state()
    lines = [
        "============================================================",
        " MT5 AUTOLAB V0.15 LOCAL - ETAT COURANT",
        "============================================================",
        f"Date                  : {b.stamp()}",
        f"Statut                : {s.get('status','')}",
        f"Phase                 : {s.get('phase','')}",
        f"Famille               : {s.get('family','')}",
        f"Variante              : {s.get('variant',0)}",
        f"Discovery terminees   : {s.get('completed_discovery',0)} / {b.discovery_total(c)}",
        f"Candidat selectionne  : {s.get('selected','') or 'AUCUN'}",
        f"SHA256 gele           : {s.get('frozen_hash','') or 'N/A'}",
        "Codex / IA externe    : AUCUN",
        f"Progression           : {s.get('progress_text','')}",
        f"Message               : {message}",
        "",
        "STOP : STOP_AUTOLAB_V015_LOCAL.bat",
        "Reprise : START_AUTOLAB_V015_LOCAL_INSTALL_AND_RUN.bat",
        f"ZIP resultat : {b.HANDOFF_ZIP}",
    ]
    b.STATUS.write_text("\n".join(lines) + "\n", encoding="utf-8")


b.write_runtime_status = write_runtime_status


def base_gene(family, variant, c):
    g = {
        "family": family, "risk": float(c.get("risk_percent", 0.5)),
        "atr_period": 14, "rsi_period": 14, "fast_ema": 30, "slow_ema": 200,
        "lookback": 48, "aux_lookback": 72, "level1": 39.0, "level2": 0.35,
        "flat_atr": 0.75, "filter_a": 0.40, "filter_b": 0.02,
        "slope_min": -5.0, "slope_max": 5.0, "vol_min": 0.70, "vol_max": 1.50,
        "session_start": -1, "session_end": -1, "stop_atr": 1.25,
        "rr": 1.10, "max_hold": 10, "max_spread_atr": 0.15,
    }
    v = int(variant)
    if family == "short_vol_core":
        rows = [
            (38,.40,.70,.50,.60,1.40,1.25,1.05,8), (38,.40,.72,.45,.65,1.45,1.25,1.10,8),
            (39,.35,.72,.40,.65,1.50,1.25,1.10,10), (39,.35,.75,.40,.70,1.50,1.25,1.10,10),
            (39,.35,.75,.35,.70,1.60,1.25,1.10,10), (40,.30,.78,.35,.70,1.50,1.25,1.05,10),
            (39,.35,.75,.40,.75,1.55,1.50,1.10,10), (39,.35,.80,.35,.65,1.55,1.25,1.15,12),
        ]
        rsi,dev,flat,rebound,vmin,vmax,sl,rr,hold = rows[v-1]
        g.update(level1=rsi, level2=dev, flat_atr=flat, filter_a=rebound,
                 vol_min=vmin, vol_max=vmax, stop_atr=sl, rr=rr, max_hold=hold)
    elif family == "short_vol_session":
        rows = [
            (38,.40,.70,.50,.60,1.50,0,22,1.05,8), (39,.35,.72,.40,.65,1.50,0,21,1.10,10),
            (39,.35,.75,.40,.65,1.55,2,22,1.10,10), (39,.35,.75,.40,.70,1.55,4,22,1.10,10),
            (39,.35,.75,.35,.70,1.60,6,22,1.10,10), (40,.30,.78,.35,.70,1.55,6,20,1.05,10),
            (39,.35,.80,.35,.65,1.50,8,21,1.10,12), (39,.35,.75,.40,.60,1.45,10,22,1.15,10),
        ]
        rsi,dev,flat,rebound,vmin,vmax,ss,se,rr,hold = rows[v-1]
        g.update(level1=rsi, level2=dev, flat_atr=flat, filter_a=rebound,
                 vol_min=vmin, vol_max=vmax, session_start=ss, session_end=se, rr=rr, max_hold=hold)
    elif family == "short_vol_slope":
        rows = [
            (38,.40,.70,.50,.60,1.50,.50,1.05,8), (39,.35,.72,.40,.65,1.50,.75,1.10,10),
            (39,.35,.75,.40,.65,1.55,1.00,1.10,10), (39,.35,.75,.40,.70,1.55,1.25,1.10,10),
            (39,.35,.75,.35,.70,1.60,1.50,1.10,10), (40,.30,.78,.35,.70,1.55,1.75,1.05,10),
            (39,.35,.80,.35,.65,1.50,2.00,1.10,12), (39,.35,.75,.40,.60,1.45,2.50,1.15,10),
        ]
        rsi,dev,flat,rebound,vmin,vmax,smax,rr,hold = rows[v-1]
        g.update(level1=rsi, level2=dev, flat_atr=flat, filter_a=rebound,
                 vol_min=vmin, vol_max=vmax, slope_max=smax, rr=rr, max_hold=hold)
    elif family == "short_adaptive_or":
        rows = [
            (38,.40,.70,.50,.75,1.35,.50,-1,-1,1.05,8), (39,.35,.72,.40,.75,1.40,.75,-1,-1,1.10,10),
            (39,.35,.75,.40,.80,1.45,1.00,-1,-1,1.10,10), (39,.35,.75,.40,.80,1.50,1.25,0,22,1.10,10),
            (39,.35,.75,.35,.85,1.55,1.50,2,22,1.10,10), (40,.30,.78,.35,.85,1.50,1.75,4,22,1.05,10),
            (39,.35,.80,.35,.80,1.45,2.00,6,22,1.10,12), (39,.35,.75,.40,.75,1.40,2.50,8,22,1.15,10),
        ]
        rsi,dev,flat,rebound,vmin,vmax,smax,ss,se,rr,hold = rows[v-1]
        g.update(level1=rsi, level2=dev, flat_atr=flat, filter_a=rebound,
                 vol_min=vmin, vol_max=vmax, slope_max=smax,
                 session_start=ss, session_end=se, rr=rr, max_hold=hold)
    else:
        raise RuntimeError("Famille inconnue: " + family)
    return g


b.base_gene = base_gene


def mutate_gene(parent, mut_index):
    g = dict(parent); fam = g["family"]
    if mut_index == 1:
        g["level1"] = round(b.clamp(float(g["level1"])+1.0,36.0,42.0),1)
        g["level2"] = round(b.clamp(float(g["level2"])-.05,.20,.50),2)
    elif mut_index == 2:
        g["level1"] = round(b.clamp(float(g["level1"])-1.0,36.0,42.0),1)
        g["level2"] = round(b.clamp(float(g["level2"])+.05,.20,.50),2)
    elif mut_index == 3:
        g["vol_min"] = round(b.clamp(float(g["vol_min"])-.05,.50,1.20),2)
        g["vol_max"] = round(b.clamp(float(g["vol_max"])+.05,1.10,1.80),2)
    else:
        g["max_hold"] = int(b.clamp(int(g["max_hold"])+2,6,14))
        g["rr"] = round(b.clamp(float(g["rr"])+.05,.95,1.25),2)
    if fam == "short_vol_session" and int(g.get("session_start",-1)) >= 0:
        if mut_index == 1: g["session_start"] = int(b.clamp(int(g["session_start"])-1,0,23))
        elif mut_index == 2: g["session_start"] = int(b.clamp(int(g["session_start"])+1,0,23))
    elif fam in ("short_vol_slope","short_adaptive_or"):
        if mut_index == 1: g["slope_max"] = round(b.clamp(float(g["slope_max"])+.20,0.0,3.0),2)
        elif mut_index == 2: g["slope_max"] = round(b.clamp(float(g["slope_max"])-.20,0.0,3.0),2)
    return g


b.mutate_gene = mutate_gene
_parent_mql = b.mql_source


def mql_source(g, magic):
    s = _parent_mql(g, magic)
    s = s.replace('#property version   "0.14"', '#property version   "0.15"')
    s = s.replace("MT5 AutoLab v0.14 LOCAL generated candidate", "MT5 AutoLab v0.15 LOCAL generated candidate")
    old = "\n".join([
        "   if(FAMILY_ID==1)", "      ok=(flat && bodyOk && shortConfirm && slopeOk);",
        "   else if(FAMILY_ID==2)", "      ok=(flat && bodyOk && shortConfirm && volOk);",
        "   else if(FAMILY_ID==3)", "      ok=(flat && bodyOk && shortConfirm && slopeOk);",
        "   else if(FAMILY_ID==4)", "      ok=(flat && bodyOk && shortConfirm && slopeOk && volOk);",
    ])
    new = "\n".join([
        "   if(FAMILY_ID==1)", "      ok=(flat && bodyOk && shortConfirm && volOk);",
        "   else if(FAMILY_ID==2)", "      ok=(flat && bodyOk && shortConfirm && volOk);",
        "   else if(FAMILY_ID==3)", "      ok=(flat && bodyOk && shortConfirm && volOk && slopeOk);",
        "   else if(FAMILY_ID==4)", "      ok=(flat && bodyOk && shortConfirm && (volOk || slopeOk));",
    ])
    if old not in s:
        raise RuntimeError("Template MQL parent inattendu")
    return s.replace(old, new, 1)


b.mql_source = mql_source


def cleanup_previous_autolab_versions():
    current = (0,15,0)
    archive = B / "archive" / "autolab_handoffs"; archive.mkdir(parents=True, exist_ok=True)
    prior = []
    for p in b.REP.glob("AUTOLAB_A_ENVOYER_CHATGPT_V*_LOCAL.zip"):
        v = b._version_tokens_from_name(p.name)
        if v and v < current: prior.append((v,p))
    if prior:
        prior.sort(key=lambda x:x[0], reverse=True)
        try: shutil.copy2(prior[0][1], archive/prior[0][1].name)
        except Exception as exc: b.log("Archive handoff impossible: "+str(exc))
    targets = []
    for p in B.glob("MT5_AutoLab_v*"):
        try:
            if p.resolve() == PKG.resolve(): continue
        except Exception: pass
        v = b._version_tokens_from_name(p.name)
        if v and v < current: targets.append(p)
    for parent in (B/"autolab", B/"experiments"):
        if parent.exists():
            for p in parent.glob("v*"):
                v = b._version_tokens_from_name(p.name)
                if v and v < current: targets.append(p)
    if targets:
        escaped = [str(p).replace("'","''") for p in targets]
        arr = ",".join("'"+x+"'" for x in escaped)
        ps = "$t=@("+arr+");try{$s=New-Object -ComObject Shell.Application;foreach($w in @($s.Windows())){try{$p=[string]$w.Document.Folder.Self.Path;foreach($x in $t){if($p -and $p.StartsWith($x,[System.StringComparison]::OrdinalIgnoreCase)){$w.Quit();break}}}catch{}}}catch{}"
        try: subprocess.run(["powershell.exe","-NoProfile","-Command",ps],timeout=20)
        except Exception: pass
        time.sleep(.7)
    for p in targets: b._safe_remove_path(p)
    for parent in (b.LOG,b.REP):
        if parent.exists():
            for p in parent.iterdir():
                if p.is_file():
                    v = b._version_tokens_from_name(p.name)
                    if v and v < current: b._safe_remove_path(p)
    if b.CFG.exists():
        for p in b.CFG.glob("autolab_v*_config.json"):
            v = b._version_tokens_from_name(p.name)
            if v and v < current: b._safe_remove_path(p)
    b.log("Nettoyage anciennes versions termine apres preflight v0.15.")


b.cleanup_previous_autolab_versions = cleanup_previous_autolab_versions


def prepare_handoff(reason=""):
    files = []
    for base, pattern in ((b.REP,"*V015_LOCAL*"),(b.LOG,"*V015_LOCAL*")):
        for p in base.glob(pattern):
            if p.is_file() and p != b.HANDOFF_ZIP: files.append((p, base.name+"/"+p.name))
    for p in (b.STATE,b.CONF,b.CAND,b.FROZEN,PKG/"autolab_v015_local.py",PKG/"README.txt",
              PKG/"PARENT_LOOP_V014.json",PKG/"ANALYSE_V014_ET_PLAN_V015.txt"):
        if p.exists() and p.is_file(): files.append((p,"core/"+p.name))
    latest = None
    if b.E.exists():
        for p in b.E.rglob("*"):
            if not p.is_file(): continue
            if p.suffix.lower() in (".txt",".json",".csv",".log",".mq5") and p.stat().st_size <= 5*1024*1024:
                files.append((p,"experiments/"+str(p.relative_to(b.E)).replace("\\","/")))
            elif p.name.lower() in ("tester_report.htm","tester_report.html"):
                if latest is None or p.stat().st_mtime > latest.stat().st_mtime: latest = p
    if latest is not None: files.append((latest,"experiments/"+str(latest.relative_to(b.E)).replace("\\","/")))
    used=set(); unique=[]
    for p,a in files:
        if a not in used: used.add(a); unique.append((p,a))
    b.HANDOFF_INDEX.write_text("MT5 AutoLab v0.15 LOCAL - RESULTAT\nAUTOLOOP: STOP APRES v0.15\n" +
                               "\n".join(" - "+a for _,a in unique) + "\n", encoding="utf-8")
    unique.insert(0,(b.HANDOFF_INDEX,"LISEZ_MOI_A_ENVOYER_CHATGPT.txt"))
    tmp = b.HANDOFF_ZIP.with_suffix(".tmp")
    try: tmp.unlink()
    except FileNotFoundError: pass
    with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p,a in unique: z.write(p,a)
    tmp.replace(b.HANDOFF_ZIP)
    b.log("PAQUET CHATGPT PRET: "+str(b.HANDOFF_ZIP))
    return b.HANDOFF_ZIP


b.prepare_handoff = prepare_handoff


def write_final(c,status,candidates,shortlist,stability_results,selected=None,val=None,hold=None):
    lines = ["# MT5 AutoLab v0.15 LOCAL — rapport final","",f"Statut final : **{status}**","",
             f"Research PASS : {sum(1 for x in candidates if b.discovery_pass(c,x['metrics']))}/{len(candidates)}",
             f"Shortlist stabilité : {len(shortlist)}",""]
    if stability_results:
        lines += ["## Stabilité annuelle","","| Candidat | PF19 | PF20 | PF21 | PF22 | PF23 | PF24 | Gate |",
                  "|---|---:|---:|---:|---:|---:|---:|:---:|"]
        for r in stability_results:
            f = r["folds"]
            lines.append(f"| {r['candidate']['candidate']} | {f['2019']['profit_factor']:.2f} | {f['2020']['profit_factor']:.2f} | {f['2021']['profit_factor']:.2f} | {f['2022']['profit_factor']:.2f} | {f['2023']['profit_factor']:.2f} | {f['2024']['profit_factor']:.2f} | {'PASS' if r['pass'] else 'FAIL'} |")
        lines.append("")
    if selected: lines += ["## Candidat gelé",f"- {selected['candidate']}",f"- SHA256 `{selected['sha256']}`",""]
    if hold is not None:
        lines += ["## Holdout 2025–2026",f"- Net {hold['net_profit']:.2f} EUR",f"- PF {hold['profit_factor']:.2f}",
                  f"- Trades {hold['trades']}",f"- DD {hold['equity_drawdown_pct']:.2f}%",f"- Sharpe {hold['sharpe_ratio']:.2f}",
                  f"- Gate **{'PASS' if b.holdout_pass(c,hold) else 'FAIL'}**",""]
    conclusions = {"NO_GO_DISCOVERY":"Aucun candidat research stable.","NO_GO_STABILITY":"Aucun candidat stable sur 6 ans.",
                   "NO_GO_HOLDOUT":"Le candidat gelé échoue au holdout.","PASS_HOLDOUT":"Research + stabilité + holdout PASS."}
    lines += ["## Conclusion",conclusions.get(status,"Campagne incomplète."),"","AutoLoop : **STOP après résultat v0.15**."]
    b.FINAL_MD.write_text("\n".join(lines)+"\n",encoding="utf-8")


b.write_final = write_final


def write_summary(c,status,candidates=None,selected=None,val_state="NON_EXECUTEE",hold_state="NON_EXECUTE",hold=None):
    candidates = candidates or []
    h = "NON OUVERT" if hold is None else f"net={hold['net_profit']:.2f} PF={hold['profit_factor']:.2f} trades={hold['trades']} DD={hold['equity_drawdown_pct']:.2f}% Sharpe={hold['sharpe_ratio']:.2f} gate={'PASS' if b.holdout_pass(c,hold) else 'FAIL'}"
    lines = ["============================================================"," MT5 AUTOLAB - SUMMARY V0.15 LOCAL","============================================================",
             f"Date                  : {b.stamp()}",f"Statut                : {status}","Research              : 2019-2024",
             "Stabilite             : 2019 / 2020 / 2021 / 2022 / 2023 / 2024",f"Holdout resultat      : {h}",
             f"Candidat gele         : {(selected or {}).get('candidate','AUCUN')}",f"SHA256                : {(selected or {}).get('sha256','N/A')}",
             f"Candidats evalues     : {len(candidates)}","AutoLoop              : RESULTAT v0.15 -> ChatGPT -> STOP",
             "Parser trades         : Nb trades = positions; Operations = deals",f"ZIP resultat          : {b.HANDOFF_ZIP}"]
    b.SUMMARY.write_text("\n".join(lines)+"\n",encoding="utf-8")


b.write_summary = write_summary


def autoloop_finish(c,reason=""):
    if not b.HANDOFF_ZIP.exists() or not b.AUTOLOOP_UPLOAD.exists():
        b.log("AUTOLOOP v0.15: ZIP ou pont uploader absent"); return
    if b.AUTOLOOP_UPLOAD_MARKER.exists():
        b.log("AUTOLOOP v0.15: upload deja effectue"); return
    msg = "AUTOLAB PRODUCTION LOOP : resultat v0.15 automatique. Analyse le ZIP v0.15. La boucle demandee est terminee : STOP, ne publie pas v0.16."
    p = subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(b.AUTOLOOP_UPLOAD),
                        "-FilePath",str(b.HANDOFF_ZIP),"-Message",msg],timeout=180)
    if p.returncode != 0:
        b.log("AUTOLOOP v0.15: uploader code="+str(p.returncode)); return
    b.AUTOLOOP_UPLOAD_MARKER.write_text(f"handoff_sha256={b.sha256(b.HANDOFF_ZIP)}\nuploaded_at={b.stamp()}\nnext_version=STOP\n",encoding="utf-8")
    b.log("AUTOLOOP v0.15: resultat envoye. STOP.")


b.autoloop_finish = autoloop_finish


def main():
    c = b.load_cfg(); terminal = {"PASS_HOLDOUT","NO_GO_DISCOVERY","NO_GO_STABILITY","NO_GO_HOLDOUT"}
    s = b.load_state()
    if s.get("status") in terminal and b.SUMMARY.exists() and b.FINAL_MD.exists():
        b.prepare_handoff("DEJA_TERMINE_"+s["status"]); b.autoloop_finish(c,"DEJA_TERMINE"); return
    if not b.MASTER.exists(): b.MASTER.write_text("",encoding="utf-8")
    for p in (b.ERR,b.STOP):
        try: p.unlink()
        except FileNotFoundError: pass
    b.set_state(status="RUNNING",phase="INITIALISATION"); b.write_runtime_status(c,"Initialisation v0.15")
    b.log("MT5 AUTOLAB v0.15 LOCAL - ATR CROSS-REGIME - ZERO CODEX")
    if not b.TERM.exists() or not b.LIVE_METAEDITOR.exists(): raise RuntimeError("MT5/MetaEditor absent")
    b.sync_standard_library(); b.preflight_local(c)
    marker = b.A/"CLEANUP_PREVIOUS_VERSIONS_DONE.txt"
    if not marker.exists():
        b.cleanup_previous_autolab_versions(); marker.write_text("OK apres preflight v0.15\n",encoding="utf-8")
    candidates = b.run_discovery(c); shortlist = b.shortlist_candidates(c,candidates); b.write_candidates_csv(candidates,[])
    if not shortlist:
        status="NO_GO_DISCOVERY"; b.set_state(status=status,phase="TERMINE"); b.write_final(c,status,candidates,shortlist,[])
        b.write_summary(c,status,candidates); b.prepare_handoff(status); b.autoloop_finish(c,status); return
    stability = b.run_stability(c,shortlist); b.write_candidates_csv(candidates,stability); selected = b.select_stable(stability)
    if selected is None:
        status="NO_GO_STABILITY"; b.set_state(status=status,phase="TERMINE"); b.write_final(c,status,candidates,shortlist,stability)
        b.write_summary(c,status,candidates); b.prepare_handoff(status); b.autoloop_finish(c,status); return
    info = b.freeze_selected(selected)
    hold = b.run_frozen_phase(c,"holdout",c["holdout_from"],c["holdout_to"],info["sha256"])
    if not b.FROZEN.exists() or b.sha256(b.FROZEN) != info["sha256"]: raise RuntimeError("Hash frozen modifie pendant holdout")
    status = "PASS_HOLDOUT" if b.holdout_pass(c,hold) else "NO_GO_HOLDOUT"
    b.set_state(status=status,phase="TERMINE"); b.write_final(c,status,candidates,shortlist,stability,info,None,hold)
    b.write_summary(c,status,candidates,info,"NON_APPLICABLE",status,hold); b.prepare_handoff(status); b.autoloop_finish(c,status)


b.main = main

if __name__ == "__main__":
    if "--bundle-only" in sys.argv:
        b.prepare_handoff("PAQUET_MANUEL"); sys.exit(0)
    try:
        b.main()
    except KeyboardInterrupt:
        try:
            c=b.load_cfg(); b.set_state(status="ARRET_DEMANDE",phase="ARRET"); b.write_summary(c,"ARRET_DEMANDE")
        except Exception: c=None
        b.prepare_handoff("ARRET_DEMANDE")
        if c is not None: b.autoloop_finish(c,"ARRET_DEMANDE")
        sys.exit(2)
    except Exception as e:
        b.ERR.write_text("".join(traceback.format_exception(e)),encoding="utf-8")
        try:
            c=b.load_cfg(); b.set_state(status="ERREUR",phase="ERREUR"); b.write_summary(c,"ERREUR")
        except Exception: c=None
        b.prepare_handoff("ERREUR")
        if c is not None:
            try: b.autoloop_finish(c,"ERREUR")
            except Exception: pass
        sys.exit(1)
