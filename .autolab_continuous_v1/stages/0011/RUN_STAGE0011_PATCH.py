import RESEARCH_STAGE0011 as m

# Technical correction only.
# The frozen family/parameter grid produces 30 hypotheses, not 48.
# No scientific family, parameter, hold, gate, validation rule or live setting changes.
m.PROTOCOL_SHA = "323791a6189506b0508bf86df2b685cca8b1063f86b4f102cc4d2d075d93b8d4"

def hypotheses_stage0011():
    H=[]
    for fam in ("streak_continuation","streak_reversal"):
        for n in (3,5,7):
            for hold in (8,24,72):
                H.append({"family":fam,"run_len":n,"hold":hold})
    for fam in ("alternation_continuation","alternation_reversal"):
        for n in (4,6):
            for hold in (8,24,72):
                H.append({"family":fam,"alt_len":n,"hold":hold})
    if len(H)!=30:
        raise RuntimeError(f"hypothesis count {len(H)} != 30")
    for h in H:
        span=h.get("run_len",h.get("alt_len"))
        key="RUN" if "run_len" in h else "ALT"
        h["id"]=f'{h["family"]}__{key}{span}__H{h["hold"]}'
    return H

m.hypotheses = hypotheses_stage0011

if __name__=="__main__":
    raise SystemExit(m.run())
