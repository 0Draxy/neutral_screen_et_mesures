import RESEARCH_STAGE0010 as m

_base_evaluate=m.evaluate

def evaluate_stage0010(h,e):
    hb=dict(h)
    hb.setdefault("lookback",0)
    r=_base_evaluate(hb,e)
    r["range_atr"]=h.get("range_atr","")
    r["close_location"]=h.get("close_location","")
    r["wick_share"]=h.get("wick_share","")
    return r

m.evaluate=evaluate_stage0010

if __name__=="__main__":
    raise SystemExit(m.run())
