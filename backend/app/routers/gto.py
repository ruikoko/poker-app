"""
GTO Brain — Router para importação e gestão de trees HRC.
Matching engine v3 com scoring calibrado.
"""
import json, logging, os, zipfile, io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.db import get_conn, query
from app.auth import require_auth

router = APIRouter(prefix="/api/gto", tags=["gto"])
logger = logging.getLogger("gto")

MIGRATION_SQL = [
    """CREATE TABLE IF NOT EXISTS gto_trees (id SERIAL PRIMARY KEY, name TEXT NOT NULL, format TEXT,
        num_players INT, tournament_phase TEXT, hero_position TEXT,
        hero_stack_bb_min NUMERIC, hero_stack_bb_max NUMERIC, villain_stack_bb NUMERIC,
        hero_covers BOOLEAN, covers_at_least_one BOOLEAN DEFAULT FALSE,
        covered_by_at_least_one BOOLEAN DEFAULT FALSE, tags TEXT[] DEFAULT '{}',
        settings_json JSONB, equity_json JSONB, uploaded_by TEXT, source_file TEXT,
        node_count INT DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""",
    "CREATE INDEX IF NOT EXISTS idx_gto_trees_lookup ON gto_trees(num_players, format)",
    """CREATE TABLE IF NOT EXISTS gto_nodes (id SERIAL PRIMARY KEY, tree_id INT REFERENCES gto_trees ON DELETE CASCADE,
        node_index INT NOT NULL, player INT NOT NULL, street INT DEFAULT 0,
        sequence JSONB DEFAULT '[]', actions JSONB NOT NULL, hands JSONB NOT NULL,
        is_terminal BOOLEAN DEFAULT FALSE, has_mixed BOOLEAN DEFAULT FALSE, UNIQUE(tree_id, node_index))""",
    "CREATE INDEX IF NOT EXISTS idx_gto_nodes_tree ON gto_nodes(tree_id, node_index)",
]
_migrated = False
def ensure_gto_schema():
    global _migrated
    if _migrated: return
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for sql in MIGRATION_SQL:
                try: cur.execute(sql)
                except: conn.rollback()
        conn.commit(); _migrated = True
    finally: conn.close()

HAND_ORDER = [
    "AA","KK","QQ","JJ","TT","99","88","77","66","55","44","33","22",
    "AKs","AQs","AJs","ATs","A9s","A8s","A7s","A6s","A5s","A4s","A3s","A2s",
    "KQs","KJs","KTs","K9s","K8s","K7s","K6s","K5s","K4s","K3s","K2s",
    "QJs","QTs","Q9s","Q8s","Q7s","Q6s","Q5s","Q4s","Q3s","Q2s",
    "JTs","J9s","J8s","J7s","J6s","J5s","J4s","J3s","J2s",
    "T9s","T8s","T7s","T6s","T5s","T4s","T3s","T2s",
    "98s","97s","96s","95s","94s","93s","92s","87s","86s","85s","84s","83s","82s",
    "76s","75s","74s","73s","72s","65s","64s","63s","62s","54s","53s","52s","43s","42s","32s",
    "AKo","AQo","AJo","ATo","A9o","A8o","A7o","A6o","A5o","A4o","A3o","A2o",
    "KQo","KJo","KTo","K9o","K8o","K7o","K6o","K5o","K4o","K3o","K2o",
    "QJo","QTo","Q9o","Q8o","Q7o","Q6o","Q5o","Q4o","Q3o","Q2o",
    "JTo","J9o","J8o","J7o","J6o","J5o","J4o","J3o","J2o",
    "T9o","T8o","T7o","T6o","T5o","T4o","T3o","T2o",
    "98o","97o","96o","95o","94o","93o","92o","87o","86o","85o","84o","83o","82o",
    "76o","75o","74o","73o","72o","65o","64o","63o","62o","54o","53o","52o","43o","42o","32o",
]

def _compress_hands(hd):
    r = []
    for h in HAND_ORDER: r.append([hd[h]["weight"],hd[h]["played"],hd[h]["evs"]] if h in hd else None)
    return r

def _has_mixed(hd):
    for d in hd.values():
        if any(0.01<p<0.99 for p in d.get("played",[])): return True
    return False

def parse_hrc_zip(zb):
    with zipfile.ZipFile(io.BytesIO(zb)) as zf:
        names=zf.namelist()
        sn=next((n for n in names if n.endswith("settings.json")),None)
        if not sn: raise ValueError("settings.json não encontrado")
        settings=json.loads(zf.read(sn))
        en=next((n for n in names if n.endswith("equity.json")),None)
        equity=json.loads(zf.read(en)) if en else {}
        nn=sorted([n for n in names if "nodes/" in n and n.endswith(".json") and "settings" not in n and "equity" not in n],
            key=lambda x:int(os.path.splitext(os.path.basename(x))[0]))
        if not nn: raise ValueError("Nenhum nó encontrado")
        nodes=[]
        for nm in nn:
            ni=int(os.path.splitext(os.path.basename(nm))[0]); nd=json.loads(zf.read(nm))
            nodes.append({"node_index":ni,"player":nd.get("player",0),"street":nd.get("street",0),
                "sequence":nd.get("sequence",[]),"actions":nd.get("actions",[]),
                "hands":_compress_hands(nd.get("hands",{})),"is_terminal":nd.get("children",1)==0,
                "has_mixed":_has_mixed(nd.get("hands",{}))})
    hd=settings.get("handdata",{}); st=hd.get("stacks",[]); bl=hd.get("blinds",[]); bo=hd.get("bounties",[])
    bb=max(bl[:2]) if len(bl)>=2 else 1; sbb=[round(s/bb,1) for s in st]; np=len(st)
    hb=any(b>0 for b in bo); hs=sbb[0] if sbb else 0; ot=sbb[1:]
    ca=any(hs>s for s in ot); cb=any(hs<s for s in ot)
    return {"settings":settings,"equity":equity,"nodes":nodes,
        "meta":{"num_players":np,"stacks_bb":sbb,"hero_stack_bb":hs,"bb_raw":bb,"bounties":bo,
            "has_bounty":hb,"format":"PKO" if hb else "vanilla","covers_at_least_one":ca,
            "covered_by_at_least_one":cb,"hero_covers":ca and not cb,"node_count":len(nodes)}}

# ── Scoring Engine v3 ─────────────────────────────────────────────────────────

POS_GROUPS = {'BTN':'steal','CO':'steal','HJ':'mid','MP':'mid','MP1':'mid','MP+1':'mid',
    'UTG':'early','UTG1':'early','UTG+1':'early','UTG2':'early','UTG+2':'early','SB':'blinds','BB':'blinds'}
GROUP_ORDER = ['steal','mid','early','blinds']
PHASE_ORDER = ['early','middle','bubble','itm','final_table']
POS_MAPS = {
    5:['UTG','CO','BTN','SB','BB'], 6:['UTG','MP','CO','BTN','SB','BB'],
    7:['UTG','UTG+1','MP','CO','BTN','SB','BB'], 8:['UTG','UTG+1','MP','HJ','CO','BTN','SB','BB'],
    9:['UTG','UTG+1','MP','MP+1','HJ','CO','BTN','SB','BB'],
}

def _phase_score(pt,ph):
    if pt=='unknown' or ph=='unknown': return 50
    try: d=abs(PHASE_ORDER.index(pt)-PHASE_ORDER.index(ph))
    except: return 50
    return {0:100,1:60,2:25,3:5}.get(d,0)

def _pos_score(a,b):
    if not a or not b: return 50
    if a==b: return 100
    ga=POS_GROUPS.get(a,'?'); gb=POS_GROUPS.get(b,'?')
    if ga=='?' or gb=='?': return 50
    if ga==gb: return 66
    try: d=abs(GROUP_ORDER.index(ga)-GROUP_ORDER.index(gb))
    except: return 5
    return {1:33,2:5,3:5}.get(d,5)

def _stack_score(a,b):
    if a<=0 or b<=0: return 0
    pct=abs(a-b)/max(a,b)*100
    if pct<=5: return 100
    if pct<=15: return 80
    if pct<=25: return 50
    if pct<=40: return 25
    if pct<=60: return 10
    return 0

def _remaining_n_score(a,b):
    d=abs(a-b); return {0:100,1:60,2:20}.get(d,0)

def _phase_from_level(lv,site='Winamax'):
    if not lv or lv<=0: return 'unknown'
    if site in ('Winamax','winamax','WN'):
        if lv<=7: return 'early'
        if lv<=13: return 'middle'
        if lv<=18: return 'bubble'
        return 'itm'
    if lv<=6: return 'early'
    if lv<=12: return 'middle'
    if lv<=18: return 'bubble'
    return 'itm'

def _phase_from_settings(s):
    eq=s.get("eqmodel",{}); ot=eq.get("otherstacks",[]); pr=eq.get("structure",{}).get("prizes",{})
    np=len(s.get("handdata",{}).get("stacks",[])); tot=np+len(ot); paid=len(pr)
    if paid<=0 or tot<=0: return 'unknown'
    r=tot/paid
    if r>3: return 'early'
    if r>1.5: return 'middle'
    if r>1.05: return 'bubble'
    if tot<=np: return 'final_table'
    return 'itm'

def calc_score(settings, tree_sbb, hi):
    tp=_phase_from_settings(settings); hp=hi.get('phase','unknown')
    s1=_phase_score(tp,hp)
    # Position
    np=len(tree_sbb); pm=POS_MAPS.get(np,POS_MAPS.get(6))[:np]
    hpos=hi.get('hero_position',''); best_ps=0; best_hi=0
    for i,tp2 in enumerate(pm):
        ps=_pos_score(hpos,tp2)
        if ps>best_ps: best_ps=ps; best_hi=i
    s2=best_ps
    # Hero stack
    hbb=hi.get('hero_stack_bb',0); thbb=tree_sbb[best_hi] if best_hi<len(tree_sbb) else 0
    s3=_stack_score(hbb,thbb)
    # Active positions
    ap=hi.get('active_positions',[]); s4=50
    if ap:
        tpos=[pm[i] for i in range(np) if i!=best_hi]; used=set(); scores=[]
        for a in ap:
            best=0; bj=-1
            for j,t in enumerate(tpos):
                if j in used: continue
                ps2=_pos_score(a,t)
                if ps2>best: best=ps2; bj=j
            if bj>=0: used.add(bj)
            scores.append(best)
        s4=sum(scores)/len(scores) if scores else 50
    # Active stacks
    astk=hi.get('active_stacks_bb',[]); s5=50
    if astk:
        rem=[s for i,s in enumerate(tree_sbb) if i!=best_hi]; scores=[]
        for a in astk:
            if rem:
                b=min(rem,key=lambda s:abs(s-a)); scores.append(_stack_score(a,b)); rem.remove(b)
            else: scores.append(0)
        s5=sum(scores)/len(scores) if scores else 50
    # Remaining count
    rc=hi.get('remaining_count',0); tr=np-best_hi-1
    s6=_remaining_n_score(rc,max(0,tr))
    # Remaining stacks
    rstk=hi.get('remaining_stacks_bb',[]); s7=50
    if rstk:
        ta=tree_sbb[best_hi+1:] if best_hi+1<len(tree_sbb) else []; scores=[]
        for r in rstk:
            if ta:
                b=min(ta,key=lambda s:abs(s-r)); scores.append(_stack_score(r,b)); ta.remove(b)
            else: scores.append(0)
        s7=sum(scores)/len(scores) if scores else 50
    total=s1*0.20+s2*0.20+s3*0.20+s4*0.15+s5*0.15+s6*0.05+s7*0.05
    return {"score":round(total,1),"phase":round(s1,1),"position":round(s2,1),"hero_stack":round(s3,1),
        "active_pos":round(s4,1),"active_stk":round(s5,1),"remaining_n":round(s6,1),"remaining_stk":round(s7,1),
        "tree_phase":tp,"hero_match_idx":best_hi,"hero_stack_diff":round(abs(hbb-thbb),1)}

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/import")
async def import_tree(file:UploadFile=File(...),name:str=Form(...),format:Optional[str]=Form(None),
    num_players:Optional[int]=Form(None),tournament_phase:Optional[str]=Form(None),
    hero_position:Optional[str]=Form(None),hero_stack_bb_min:Optional[float]=Form(None),
    hero_stack_bb_max:Optional[float]=Form(None),villain_stack_bb:Optional[float]=Form(None),
    hero_covers:Optional[bool]=Form(None),tags:Optional[str]=Form(None),
    uploaded_by:Optional[str]=Form(None),_=Depends(require_auth)):
    ensure_gto_schema()
    zb=await file.read()
    if not zb: raise HTTPException(400,"Ficheiro vazio")
    try: p=parse_hrc_zip(zb)
    except Exception as e: raise HTTPException(400,f"Erro: {e}")
    m=p["meta"]; tl=json.loads(tags) if tags else []
    tf=format or m["format"]; tnp=num_players or m["num_players"]
    thc=hero_covers if hero_covers is not None else m["hero_covers"]
    tsn=hero_stack_bb_min or m["hero_stack_bb"]; tsx=hero_stack_bb_max or m["hero_stack_bb"]
    conn=get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO gto_trees(name,format,num_players,tournament_phase,hero_position,
                hero_stack_bb_min,hero_stack_bb_max,villain_stack_bb,hero_covers,covers_at_least_one,
                covered_by_at_least_one,tags,settings_json,equity_json,uploaded_by,source_file,node_count)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (name,tf,tnp,tournament_phase,hero_position,tsn,tsx,villain_stack_bb,thc,
                 m["covers_at_least_one"],m["covered_by_at_least_one"],tl,
                 json.dumps(p["settings"]),json.dumps(p["equity"]) if p["equity"] else None,
                 uploaded_by,file.filename,m["node_count"]))
            tid=cur.fetchone()["id"]
            for n in p["nodes"]:
                cur.execute("""INSERT INTO gto_nodes(tree_id,node_index,player,street,sequence,actions,hands,is_terminal,has_mixed)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(tree_id,node_index) DO NOTHING""",
                    (tid,n["node_index"],n["player"],n["street"],json.dumps(n["sequence"]),
                     json.dumps(n["actions"]),json.dumps(n["hands"]),n["is_terminal"],n["has_mixed"]))
        conn.commit()
    except: conn.rollback(); raise
    finally: conn.close()
    return {"id":tid,"name":name,"format":tf,"num_players":tnp,"node_count":m["node_count"],"meta":m}

@router.get("/trees")
def list_trees(format:Optional[str]=None,num_players:Optional[int]=None,_=Depends(require_auth)):
    ensure_gto_schema()
    c=[]; p=[]
    if format: c.append("format=%s"); p.append(format)
    if num_players: c.append("num_players=%s"); p.append(num_players)
    w=("WHERE "+" AND ".join(c)) if c else ""
    return query(f"SELECT id,name,format,num_players,tournament_phase,hero_position,hero_stack_bb_min,hero_stack_bb_max,villain_stack_bb,hero_covers,covers_at_least_one,covered_by_at_least_one,tags,uploaded_by,source_file,node_count,created_at FROM gto_trees {w} ORDER BY created_at DESC",p or None)

@router.get("/trees/{tid}")
def get_tree(tid:int,_=Depends(require_auth)):
    r=query("SELECT * FROM gto_trees WHERE id=%s",(tid,))
    if not r: raise HTTPException(404,"Not found")
    return r[0]

@router.get("/trees/{tid}/node/{ni}")
def get_node(tid:int,ni:int,_=Depends(require_auth)):
    r=query("SELECT node_index,player,street,sequence,actions,hands,is_terminal,has_mixed FROM gto_nodes WHERE tree_id=%s AND node_index=%s",(tid,ni))
    if not r: raise HTTPException(404,"Not found")
    n=dict(r[0]); ha=n["hands"]
    if isinstance(ha,list):
        hd={}
        for i,h in enumerate(HAND_ORDER):
            if i<len(ha) and ha[i] is not None: w,p,e=ha[i]; hd[h]={"weight":w,"played":p,"evs":e}
        n["hands"]=hd
    n["hand_order"]=HAND_ORDER; return n

@router.get("/trees/{tid}/nodes")
def get_nodes_batch(tid:int,indices:str,_=Depends(require_auth)):
    try: il=[int(x) for x in indices.split(",") if x.strip()]
    except: raise HTTPException(400,"Bad indices")
    if len(il)>50: raise HTTPException(400,"Max 50")
    r=query("SELECT node_index,player,street,sequence,actions,hands,is_terminal,has_mixed FROM gto_nodes WHERE tree_id=%s AND node_index=ANY(%s)",(tid,il))
    out={}
    for row in r:
        n=dict(row); ha=n["hands"]
        if isinstance(ha,list):
            hd={}
            for i,h in enumerate(HAND_ORDER):
                if i<len(ha) and ha[i] is not None: w,p,e=ha[i]; hd[h]={"weight":w,"played":p,"evs":e}
            n["hands"]=hd
        out[n["node_index"]]=n
    return out

@router.delete("/trees/{tid}")
def delete_tree(tid:int,_=Depends(require_auth)):
    conn=get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM gto_trees WHERE id=%s RETURNING id",(tid,))
            if not cur.fetchone(): raise HTTPException(404,"Not found")
        conn.commit()
    finally: conn.close()
    return {"deleted":tid}

@router.patch("/trees/{tid}")
def update_tree(tid:int,data:dict,_=Depends(require_auth)):
    ok={"name","format","num_players","tournament_phase","hero_position","hero_stack_bb_min","hero_stack_bb_max","villain_stack_bb","hero_covers","tags","uploaded_by"}
    u={k:v for k,v in data.items() if k in ok}
    if not u: raise HTTPException(400,"Nothing to update")
    sc=", ".join(f"{k}=%s" for k in u); vals=list(u.values())+[tid]
    conn=get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE gto_trees SET {sc},updated_at=NOW() WHERE id=%s RETURNING id",vals)
            if not cur.fetchone(): raise HTTPException(404,"Not found")
        conn.commit()
    finally: conn.close()
    return {"updated":tid}

@router.get("/match")
def match_tree(hero_stack_bb:float, format:str, num_players:int,
    hero_position:Optional[str]=None, level:Optional[int]=None, site:Optional[str]=None,
    active_positions:Optional[str]=None, active_stacks_bb:Optional[str]=None,
    remaining_positions:Optional[str]=None, remaining_stacks_bb:Optional[str]=None,
    _=Depends(require_auth)):
    ensure_gto_schema()
    rows=query("SELECT id,name,format,num_players,node_count,settings_json FROM gto_trees WHERE format=%s",(format,))
    if not rows: return {"matches":[],"reason":"Nenhuma tree para este formato"}
    hp=_phase_from_level(level,site or 'Winamax') if level else 'unknown'
    ap=[x.strip() for x in active_positions.split(',')] if active_positions else []
    ask=[float(x) for x in active_stacks_bb.split(',')] if active_stacks_bb else []
    rp=[x.strip() for x in remaining_positions.split(',')] if remaining_positions else []
    rsk=[float(x) for x in remaining_stacks_bb.split(',')] if remaining_stacks_bb else []
    hi={'hero_position':hero_position or '','hero_stack_bb':hero_stack_bb,'phase':hp,
        'active_positions':ap,'active_stacks_bb':ask,'remaining_count':len(rp),'remaining_stacks_bb':rsk}
    results=[]
    for t in rows:
        s=t.get("settings_json") or {}
        if isinstance(s,str):
            try: s=json.loads(s)
            except: s={}
        hd=s.get("handdata",{}); ts=hd.get("stacks",[]); tb=hd.get("blinds",[])
        tbb=max(tb[:2]) if len(tb)>=2 else 1
        tsbb=[round(x/tbb,1) for x in ts] if tbb>0 else []
        if not tsbb: continue
        if abs(len(tsbb)-num_players)>2: continue
        sc=calc_score(s,tsbb,hi)
        results.append({"tree_id":t["id"],"name":t["name"],"format":t["format"],
            "num_players":len(tsbb),"node_count":t["node_count"],"tree_stacks_bb":tsbb,
            "phase":sc["tree_phase"],"confidence":sc["score"],"hero_match_idx":sc["hero_match_idx"],
            "hero_stack_diff":sc["hero_stack_diff"],
            "breakdown":{"phase":sc["phase"],"position":sc["position"],"hero_stack":sc["hero_stack"],
                "active_pos":sc["active_pos"],"active_stk":sc["active_stk"],
                "remaining_n":sc["remaining_n"],"remaining_stk":sc["remaining_stk"]}})
    results.sort(key=lambda x:-x["confidence"])
    return {"matches":results[:5]}
