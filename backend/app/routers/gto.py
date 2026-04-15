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
    """
    Mesa-vs-mesa scoring. The hero's presence is irrelevant for matching.
    We match the entire table setup: all positions + all stacks.
    Then the hero's position determines which tree player corresponds to them.
    
    Weights (calibrated with Rui):
    1. Phase: 20%  2. Hero pos: 20%  3. Hero stack: 20%
    4. Active pos: 15%  5. Active stacks: 15%
    6. Remaining count: 5%  7. Remaining stacks: 5%
    """
    tp=_phase_from_settings(settings); hp=hi.get('phase','unknown')
    s1=_phase_score(tp,hp)
    
    # Build position maps for BOTH table sizes
    tree_np=len(tree_sbb); hand_np=hi.get('num_players', tree_np)
    tree_pm=POS_MAPS.get(tree_np, POS_MAPS.get(6))[:tree_np]
    hand_pm=POS_MAPS.get(hand_np, POS_MAPS.get(6))[:hand_np]
    
    # All hand players: hero + active + remaining
    hand_players=[]  # list of {pos, stack_bb}
    hpos=hi.get('hero_position',''); hbb=hi.get('hero_stack_bb',0)
    if hpos and hbb>0:
        hand_players.append({'pos':hpos,'stack_bb':hbb,'is_hero':True})
    for i,ap in enumerate(hi.get('active_positions',[])):
        stk=hi.get('active_stacks_bb',[])
        s=stk[i] if i<len(stk) else 0
        if ap and s>0: hand_players.append({'pos':ap,'stack_bb':s,'is_hero':False})
    for i,rp in enumerate(hi.get('remaining_positions',[])):
        stk=hi.get('remaining_stacks_bb',[])
        s=stk[i] if i<len(stk) else 0
        if rp and s>0: hand_players.append({'pos':rp,'stack_bb':s,'is_hero':False})
    
    # Match each hand player to best tree player (greedy by combined pos+stack score)
    tree_available=list(range(tree_np))  # indices
    mapping={}  # hand_player_idx -> tree_player_idx
    hero_tree_idx=0
    
    # Sort hand players: hero first, then by importance
    hp_sorted=sorted(range(len(hand_players)),key=lambda i: (0 if hand_players[i]['is_hero'] else 1))
    
    for hi_idx in hp_sorted:
        hp2=hand_players[hi_idx]
        best_combined=-1; best_ti=-1
        for ti in tree_available:
            tp2=tree_pm[ti] if ti<len(tree_pm) else ''
            ps=_pos_score(hp2['pos'],tp2)
            ss=_stack_score(hp2['stack_bb'],tree_sbb[ti] if ti<len(tree_sbb) else 0)
            combined=ps*0.5+ss*0.5  # equal weight for greedy matching
            if combined>best_combined: best_combined=combined; best_ti=ti
        if best_ti>=0:
            mapping[hi_idx]=best_ti
            tree_available.remove(best_ti)
            if hp2.get('is_hero'): hero_tree_idx=best_ti
    
    # Now score using the mapping
    hero_hp=next((p for p in hand_players if p.get('is_hero')),None)
    if hero_hp and 0 in mapping:
        hero_ti=mapping[0]  # hero is always first in hp_sorted
        s2=_pos_score(hero_hp['pos'], tree_pm[hero_ti] if hero_ti<len(tree_pm) else '')
        s3=_stack_score(hero_hp['stack_bb'], tree_sbb[hero_ti] if hero_ti<len(tree_sbb) else 0)
    else:
        s2=50; s3=50; hero_ti=0
    
    # Active players scores (those already in the pot)
    active_pos_scores=[]; active_stk_scores=[]
    active_positions=hi.get('active_positions',[])
    active_stacks=hi.get('active_stacks_bb',[])
    for i,hp_idx in enumerate(hp_sorted):
        if hand_players[hp_idx].get('is_hero'): continue
        if hand_players[hp_idx]['pos'] not in active_positions: continue
        ti=mapping.get(hp_idx)
        if ti is not None:
            active_pos_scores.append(_pos_score(hand_players[hp_idx]['pos'], tree_pm[ti] if ti<len(tree_pm) else ''))
            active_stk_scores.append(_stack_score(hand_players[hp_idx]['stack_bb'], tree_sbb[ti] if ti<len(tree_sbb) else 0))
    s4=sum(active_pos_scores)/len(active_pos_scores) if active_pos_scores else 50
    s5=sum(active_stk_scores)/len(active_stk_scores) if active_stk_scores else 50
    
    # Remaining players
    rem_positions=hi.get('remaining_positions',[])
    rem_stk_scores=[]
    for i,hp_idx in enumerate(hp_sorted):
        if hand_players[hp_idx].get('is_hero'): continue
        if hand_players[hp_idx]['pos'] not in rem_positions: continue
        ti=mapping.get(hp_idx)
        if ti is not None:
            rem_stk_scores.append(_stack_score(hand_players[hp_idx]['stack_bb'], tree_sbb[ti] if ti<len(tree_sbb) else 0))
    rc=len(rem_positions); tr=tree_np-hero_ti-1
    s6=_remaining_n_score(rc,max(0,tr))
    s7=sum(rem_stk_scores)/len(rem_stk_scores) if rem_stk_scores else 50
    
    # Num players penalty (not in the 7 factors but important)
    np_pen=0
    if abs(tree_np-hand_np)==1: np_pen=5
    elif abs(tree_np-hand_np)==2: np_pen=15
    elif abs(tree_np-hand_np)>2: np_pen=30
    
    total=s1*0.20+s2*0.20+s3*0.20+s4*0.15+s5*0.15+s6*0.05+s7*0.05-np_pen
    total=max(0,min(100,total))
    
    thbb=tree_sbb[hero_ti] if hero_ti<len(tree_sbb) else 0
    return {"score":round(total,1),"phase":round(s1,1),"position":round(s2,1),"hero_stack":round(s3,1),
        "active_pos":round(s4,1),"active_stk":round(s5,1),"remaining_n":round(s6,1),"remaining_stk":round(s7,1),
        "tree_phase":tp,"hero_match_idx":hero_ti,"hero_stack_diff":round(abs(hbb-thbb),1),
        "mapping":{str(k):v for k,v in mapping.items()}}

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

@router.post("/navigate")
def navigate_tree(data: dict, _=Depends(require_auth)):
    """
    Navigate a tree following a sequence of real hand actions.
    Input: {tree_id, actions: [{player_idx, type: 'F'|'C'|'R', amount_bb}]}
    Returns: the node reached after following all actions.
    """
    ensure_gto_schema()
    tid = data.get("tree_id")
    actions_seq = data.get("actions", [])
    if not tid: raise HTTPException(400, "tree_id required")
    
    # Get tree settings for BB conversion
    trees = query("SELECT settings_json FROM gto_trees WHERE id=%s", (tid,))
    if not trees: raise HTTPException(404, "Tree not found")
    settings = trees[0].get("settings_json") or {}
    if isinstance(settings, str):
        try: settings = json.loads(settings)
        except: settings = {}
    hd = settings.get("handdata", {})
    blinds = hd.get("blinds", [])
    tree_bb = max(blinds[:2]) if len(blinds) >= 2 else 1
    
    # Start at root
    current_node_idx = 0
    path = [0]
    
    for act in actions_seq:
        # Get current node
        rows = query("SELECT node_index,player,actions,is_terminal FROM gto_nodes WHERE tree_id=%s AND node_index=%s", (tid, current_node_idx))
        if not rows: break
        node = rows[0]
        if node["is_terminal"]: break
        
        node_actions = node["actions"]
        if isinstance(node_actions, str):
            try: node_actions = json.loads(node_actions)
            except: break
        
        act_type = act.get("type", "F").upper()  # F, C, R
        act_amount_bb = act.get("amount_bb", 0)
        act_amount_chips = act_amount_bb * tree_bb  # convert to tree chips
        
        # Find best matching action in tree
        best_action = None
        best_dist = float('inf')
        
        for ta in node_actions:
            ta_type = ta.get("type", "")
            if ta_type != act_type: continue
            if act_type == 'F' or act_type == 'C':
                best_action = ta
                break  # Only one fold/call per node
            elif act_type == 'R':
                # Match raise by closest amount
                ta_amount = ta.get("amount", 0)
                dist = abs(ta_amount - act_amount_chips)
                if dist < best_dist:
                    best_dist = dist
                    best_action = ta
        
        if not best_action:
            # If no exact type match, try fold as fallback
            for ta in node_actions:
                if ta.get("type") == "F":
                    best_action = ta
                    break
        
        if best_action and best_action.get("node") is not None:
            current_node_idx = best_action["node"]
            path.append(current_node_idx)
        else:
            break
    
    # Fetch final node with hands
    rows = query("SELECT node_index,player,street,sequence,actions,hands,is_terminal,has_mixed FROM gto_nodes WHERE tree_id=%s AND node_index=%s", (tid, current_node_idx))
    if not rows: raise HTTPException(404, "Node not found")
    node = dict(rows[0])
    ha = node["hands"]
    if isinstance(ha, list):
        hd2 = {}
        for i, h in enumerate(HAND_ORDER):
            if i < len(ha) and ha[i] is not None:
                w, p, e = ha[i]; hd2[h] = {"weight": w, "played": p, "evs": e}
        node["hands"] = hd2
    node["hand_order"] = HAND_ORDER
    node["path"] = path
    return node

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
        'active_positions':ap,'active_stacks_bb':ask,'remaining_count':len(rp),
        'remaining_positions':rp,'remaining_stacks_bb':rsk,'num_players':num_players}
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
