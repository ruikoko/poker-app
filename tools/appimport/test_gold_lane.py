"""Testes da lane das gold images (process_gold_dir) — canalização do cliente.
Sem rede: sessão falsa. Valida dry-run, envio+move, falha fica, e o dedup do
cliente (após mover, a 2ª corrida não vê o ficheiro)."""
import os, tempfile, shutil
import app_import as A


class _Resp:
    def __init__(self, code, body=None):
        self.status_code = code
        self._body = body or {"status": "queued", "message": "ok"}
        self.text = str(self._body)
    def json(self): return self._body


class _Session:
    def __init__(self, code=200, body=None):
        self.code = code; self.body = body; self.posts = []
    def post(self, url, files=None, data=None, timeout=None):
        # consome o ficheiro como o requests faria
        files["file"][1].read()
        self.posts.append(url)
        return _Resp(self.code, self.body)


def _setup(tmp, names):
    gold = os.path.join(tmp, "Documents"); os.makedirs(gold)
    parent = os.path.join(tmp, "Batmen"); os.makedirs(os.path.join(parent, "done", "gold"))
    for n in names:
        with open(os.path.join(gold, n), "wb") as f: f.write(b"\x89PNG fake " + n.encode())
    A.GOLD_DIR = gold; A.PARENT_DIR = parent
    return gold, parent


def test_dry_run_lista_todas_sem_mover():
    tmp = tempfile.mkdtemp()
    try:
        gold, parent = _setup(tmp, ["a_#1.png", "b_#2.png", "c_#3.jpg"])
        res = A.process_gold_dir(_Session(), live=False)
        assert res == (3, 0)
        # dry-run não move nada
        assert len(A._imgs_in(gold)) == 3
        assert len(os.listdir(os.path.join(parent, "done", "gold"))) == 0
    finally:
        shutil.rmtree(tmp)


def test_ao_vivo_envia_e_move_para_done_gold():
    tmp = tempfile.mkdtemp()
    try:
        gold, parent = _setup(tmp, ["a_#1.png", "b_#2.png"])
        s = _Session(200)
        res = A.process_gold_dir(s, live=True)
        assert res == (2, 0)
        assert all(u.endswith("/api/screenshots") for u in s.posts)
        assert len(s.posts) == 2
        # moveu para done/gold e esvaziou a GOLD_DIR (sai da Documents)
        assert len(A._imgs_in(gold)) == 0
        assert sorted(os.listdir(os.path.join(parent, "done", "gold"))) == ["a_#1.png", "b_#2.png"]
    finally:
        shutil.rmtree(tmp)


def test_falha_fica_para_retry():
    tmp = tempfile.mkdtemp()
    try:
        gold, parent = _setup(tmp, ["a_#1.png"])
        res = A.process_gold_dir(_Session(500), live=True)
        assert res == (0, 1)
        # falha → não move (fica na GOLD_DIR p/ retry)
        assert len(A._imgs_in(gold)) == 1
        assert len(os.listdir(os.path.join(parent, "done", "gold"))) == 0
    finally:
        shutil.rmtree(tmp)


def test_segunda_corrida_nao_reenvia_dedup_cliente():
    tmp = tempfile.mkdtemp()
    try:
        gold, parent = _setup(tmp, ["a_#1.png", "b_#2.png"])
        A.process_gold_dir(_Session(200), live=True)   # 1ª corrida: move tudo
        s2 = _Session(200)
        res2 = A.process_gold_dir(s2, live=True)        # 2ª corrida
        assert res2 == (0, 0)
        assert s2.posts == []                            # nada reenviado
    finally:
        shutil.rmtree(tmp)


def test_gold_dir_nao_configurada_salta():
    A.GOLD_DIR = None
    assert A.process_gold_dir(_Session(), live=True) is None
