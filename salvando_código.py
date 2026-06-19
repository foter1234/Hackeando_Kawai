#!/usr/bin/env python3
"""
Kwai Farm — automação que assiste vídeos do Kwai para juntar Kwai Golds.

Arquitetura "PERCEBER → DECIDIR → AGIR" (como um agente):
    1. PERCEBER: captura a tela inteira num snapshot — TODOS os elementos com suas
       coordenadas (capturar_tela). Nunca se decide sem antes olhar a tela toda.
    2. DECIDIR : raciocina sobre o snapshot para achar o alvo certo (card, 'Ir',
       timer, modal 'Ganhar mais', popup de anúncio).
    3. AGIR    : clica/espera/volta, registrando a decisão.

Fluxo (exatamente o diagrama combinado):
    Abrir Kwai -> Perfil -> 3 pontinhos (canto sup. direito) -> "Ganhar dinheiro"
    -> achar "Assista a vídeos para ganhar até X Kwai golds" e clicar nele
       (se o clique no card não funcionar, clicar no "Ir" à direita dele)
    -> dentro do vídeo, ler o timer (topo da tela, normalmente à direita) até zerar
    -> esperar 5–10s -> apertar Voltar
    -> se aparecer a tela "Ganhar mais" / "Sair": clicar "Ganhar mais"
       se simplesmente voltar: clicar de novo no card
    -> repetir

Tudo é registrado: console + arquivo .log (toda a saída) + dumps XML da UI +
relatório markdown de decisões (logs/relatorio_<data>.md), para revisar o desempenho.
"""

import uiautomator2 as u2
import time
import subprocess
import xml.etree.ElementTree as ET
import re
import os
import sys
import random
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
KWAI_PACKAGE = "com.kwai.video"
ESPERA_POS_TIMER = (5, 10)      # segundos a esperar depois que o timer zera, antes de voltar
MAX_ESPERA_VIDEO = 180          # teto de segurança para um único vídeo (s)
TIMEOUT_SEM_TIMER = 25          # s sem detectar timer => provável anúncio sem timer
INTERVALO_LEITURA_TIMER = 1.5   # s entre leituras do timer

DEVICE_ID = None
d = None

# ---------------------------------------------------------------------------
# Logging para estudo: toda a saída (prints + erros) vai para um arquivo por
# execução; cada dump da árvore de UI é salvo como XML numerado; e cada decisão
# é registrada num relatório markdown que serve para avaliar o desempenho.
# ---------------------------------------------------------------------------
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_DUMP_DIR = None
_DUMP_SEQ = 0
_RELATORIO_PATH = None


class _Tee:
    """Escreve nos dois streams ao mesmo tempo (console + arquivo de log)."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass


def iniciar_logging():
    """Redireciona stdout/stderr para console + arquivo, cria a pasta de dumps e o relatório."""
    global _DUMP_DIR, _RELATORIO_PATH
    os.makedirs(LOG_DIR, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_log = os.path.join(LOG_DIR, f"farm_{carimbo}.log")
    _DUMP_DIR = os.path.join(LOG_DIR, f"dumps_{carimbo}")
    _RELATORIO_PATH = os.path.join(LOG_DIR, f"relatorio_{carimbo}.md")
    os.makedirs(_DUMP_DIR, exist_ok=True)

    arquivo = open(caminho_log, "a", encoding="utf-8", buffering=1)  # line-buffered
    sys.stdout = _Tee(sys.__stdout__, arquivo)
    sys.stderr = _Tee(sys.__stderr__, arquivo)

    with open(_RELATORIO_PATH, "w", encoding="utf-8") as f:
        f.write(f"# Relatório de execução — Kwai Farm\n\n")
        f.write(f"Início: {datetime.now().isoformat(timespec='seconds')}\n\n")
        f.write(f"Log: `{caminho_log}`  ·  Dumps: `{_DUMP_DIR}`\n")

    print("=" * 60)
    print(f"LOG INICIADO   : {datetime.now().isoformat(timespec='seconds')}")
    print(f"Arquivo de log : {caminho_log}")
    print(f"Pasta de dumps : {_DUMP_DIR}")
    print(f"Relatório      : {_RELATORIO_PATH}")
    print("=" * 60)
    return caminho_log


def relatorio(titulo, linhas=None):
    """Anexa uma entrada de decisão ao relatório markdown (para revisar o desempenho)."""
    if not _RELATORIO_PATH:
        return
    try:
        with open(_RELATORIO_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n### {datetime.now().strftime('%H:%M:%S')} — {titulo}\n")
            for ln in (linhas or []):
                f.write(f"- {ln}\n")
    except Exception as exc:
        print(f"[RELATORIO] Falha ao escrever: {exc}")


def _salvar_xml(xml, motivo):
    """Salva um XML de hierarquia já capturado, com nome numerado, para estudo."""
    global _DUMP_SEQ
    if not xml:
        return
    _DUMP_SEQ += 1
    try:
        if _DUMP_DIR:
            caminho = os.path.join(_DUMP_DIR, f"{_DUMP_SEQ:04d}_{motivo}.xml")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(xml)
            print(f"[DUMP] {caminho}")
    except Exception as exc:
        print(f"[DUMP] Falha ao salvar ({motivo}): {exc}")


# ---------------------------------------------------------------------------
# PERCEPÇÃO — Elemento e Tela (snapshot com TODOS os elementos e coordenadas)
# ---------------------------------------------------------------------------
def _parse_bounds(bounds_str):
    """Converte '[x1,y1][x2,y2]' (formato do dump de UI) em dict com cantos, centro e tamanho.

    Trabalhar com os bounds reais da UI (e não coordenadas fixas) é o que torna a lógica
    universal: serve para qualquer resolução de celular ou emulador.
    """
    pares = re.findall(r'\[(-?\d+),(-?\d+)\]', bounds_str or '')
    if len(pares) != 2:
        return None
    (x1, y1), (x2, y2) = pares
    left, top, right, bottom = int(x1), int(y1), int(x2), int(y2)
    if right <= left or bottom <= top:
        return None
    return {
        'left': left, 'top': top, 'right': right, 'bottom': bottom,
        'cx': (left + right) // 2, 'cy': (top + bottom) // 2,
        'width': right - left, 'height': bottom - top,
    }


class Elemento:
    """Um elemento da tela com tudo que precisamos para decidir e clicar."""
    __slots__ = ('text', 'desc', 'rid', 'clazz', 'pkg', 'clickable',
                 'scrollable', 'bounds', 'cx', 'cy', 'w', 'h')

    def __init__(self, node):
        a = node.attrib
        self.text = (a.get('text') or '').strip()
        self.desc = (a.get('content-desc') or '').strip()
        self.rid = (a.get('resource-id') or '').strip()
        self.clazz = a.get('class') or ''
        self.pkg = a.get('package') or ''
        self.clickable = a.get('clickable') == 'true'
        self.scrollable = a.get('scrollable') == 'true'
        self.bounds = _parse_bounds(a.get('bounds', ''))
        if self.bounds:
            self.cx, self.cy = self.bounds['cx'], self.bounds['cy']
            self.w, self.h = self.bounds['width'], self.bounds['height']
        else:
            self.cx = self.cy = self.w = self.h = 0

    @property
    def conteudo(self):
        return (self.text + ' ' + self.desc).strip()

    def __repr__(self):
        rid_curto = self.rid.split('/')[-1] if self.rid else ''
        return (f"<'{self.text}'|'{self.desc}' rid={rid_curto} "
                f"({self.cx},{self.cy}) clk={'S' if self.clickable else 'N'}>")


class Tela:
    """Snapshot da tela inteira. Todas as consultas operam sobre esta foto."""

    def __init__(self, elementos, largura, altura):
        self.elementos = elementos
        self.largura = largura
        self.altura = altura

    @staticmethod
    def _norm(s):
        return re.sub(r'\s+', ' ', (s or '').strip().lower())

    def com_texto(self):
        """Elementos que têm texto ou content-desc."""
        return [e for e in self.elementos if e.conteudo]

    def por_regex(self, pattern):
        rx = re.compile(pattern, re.IGNORECASE)
        return [e for e in self.elementos if e.conteudo and rx.search(e.conteudo)]

    def por_texto_exato(self, *opcoes):
        alvos = {self._norm(o) for o in opcoes}
        return [e for e in self.elementos
                if self._norm(e.text) in alvos or self._norm(e.desc) in alvos]

    def contendo(self, termo):
        t = termo.lower()
        return [e for e in self.elementos if t in e.conteudo.lower()]

    def por_rid_contendo(self, *tokens):
        toks = [t.lower() for t in tokens]
        return [e for e in self.elementos
                if e.rid and any(tok in e.rid.lower() for tok in toks)]

    def existe_texto(self, *opcoes):
        return bool(self.por_texto_exato(*opcoes))

    def clicavel_que_contem(self, elem):
        """Menor elemento clicável cujos bounds contêm o centro de `elem` (o 'dono' clicável).

        Resolve o caso clássico: o texto do card não é clicável, mas o container que o
        envolve é. Clicar no container é o certo.
        """
        cx, cy = elem.cx, elem.cy
        donos = []
        for e in self.elementos:
            if not e.clickable or not e.bounds:
                continue
            b = e.bounds
            if b['left'] <= cx <= b['right'] and b['top'] <= cy <= b['bottom']:
                donos.append(e)
        if not donos:
            return None
        donos.sort(key=lambda e: e.w * e.h)  # menor área = mais específico
        return donos[0]


def capturar_tela(motivo, salvar=True):
    """PERCEBER: lê a árvore de UI inteira e devolve uma Tela com todos os elementos.

    Salva o XML para estudo (salvar=False nas leituras de alta frequência do timer,
    para não gerar centenas de arquivos).
    """
    try:
        xml = d.dump_hierarchy()
    except Exception as exc:
        print(f"[PERCEPÇÃO] Falha ao capturar a tela ({motivo}): {exc}")
        return Tela([], 0, 0)

    if salvar:
        _salvar_xml(xml, motivo)

    try:
        root = ET.fromstring(xml)
        elementos = [el for el in (Elemento(n) for n in root.iter()) if el.bounds]
    except Exception as exc:
        print(f"[PERCEPÇÃO] Falha ao parsear ({motivo}): {exc}")
        elementos = []

    try:
        largura, altura = d.window_size()
    except Exception:
        largura = altura = 0

    return Tela(elementos, largura, altura)


def logar_tela(tela, label="", apenas_com_texto=True, limite=40):
    """Imprime os elementos da tela (com coordenadas) — a base para qualquer decisão."""
    elems = tela.com_texto() if apenas_com_texto else tela.elementos
    print(f"\n--- Tela [{label}] : {len(elems)} elementos com texto / "
          f"{len(tela.elementos)} no total ({tela.largura}x{tela.altura}) ---")
    for e in elems[:limite]:
        print(f"  {e!r}")
    if len(elems) > limite:
        print(f"  ... e mais {len(elems) - limite}")
    print("-" * 50)


# ---------------------------------------------------------------------------
# AÇÕES (sempre logadas)
# ---------------------------------------------------------------------------
def clicar_ponto(x, y, motivo=""):
    print(f"👆 Clique em ({x},{y}) — {motivo}")
    relatorio(f"Clique ({x},{y})", [motivo] if motivo else None)
    try:
        d.click(x, y)
        return True
    except Exception as exc:
        print(f"   ❌ Falha no clique: {exc}")
        return False


def clicar_alvo(tela, elem, motivo=""):
    """Clica no elemento — se ele não for clicável, clica no container clicável que o contém."""
    dono = elem if elem.clickable else (tela.clicavel_que_contem(elem) or elem)
    if dono is not elem:
        print(f"   (texto não-clicável; clicando no container {dono!r})")
    return clicar_ponto(dono.cx, dono.cy, motivo or f"elemento {elem!r}")


def voltar(motivo=""):
    print(f"⬅️  Voltar (BACK) — {motivo}")
    relatorio("Voltar (BACK)", [motivo] if motivo else None)
    try:
        d.press("back")
    except Exception:
        try:
            subprocess.run(["adb", "-s", DEVICE_ID, "shell", "input", "keyevent", "4"], check=False)
        except Exception as exc:
            print(f"   ❌ Falha ao voltar: {exc}")


def rolar_para_baixo():
    if not (tela_largura() and tela_altura()):
        return
    x = int(tela_largura() * 0.5)
    y1 = int(tela_altura() * 0.72)
    y2 = int(tela_altura() * 0.35)
    try:
        d.swipe(x, y1, x, y2, duration=0.4)
        time.sleep(1)
    except Exception as exc:
        print(f"   ❌ Falha ao rolar: {exc}")


def tela_largura():
    try:
        return d.window_size()[0]
    except Exception:
        return 0


def tela_altura():
    try:
        return d.window_size()[1]
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# POPUPS / ANÚNCIOS no meio da tela
# ---------------------------------------------------------------------------
_FECHAR_RID = ['close', 'btn_close', 'iv_close', 'ic_close', 'dialog_close', 'dismiss', 'popup_close']
_FECHAR_DESCS = ['fechar', 'close', 'cancelar', 'cancel', 'dismiss', 'dispensar']
_FECHAR_GLIFOS = {'✕', '×', '✖', '╳', '⨯', '✗'}
_FECHAR_TEXTOS = {
    'fechar', 'agora não', 'agora nao', 'mais tarde', 'depois', 'pular',
    'pular anúncio', 'pular anuncio', 'não, obrigado', 'nao, obrigado',
    'não obrigado', 'nao obrigado', 'dispensar', 'ignorar', 'entendi',
}


def _achar_fechar_popup(tela):
    """Procura, no snapshot, uma afordância de fechar popup. Retorna (Elemento, motivo) ou None.

    Confiança decrescente: resource-id de fechar > content-desc de fechar > glifo X >
    texto dispensativo. Comparação exata para não clicar em qualquer coisa.
    """
    candidatos = []
    for e in tela.elementos:
        rid_l = e.rid.lower()
        if any(tok in rid_l for tok in _FECHAR_RID):
            candidatos.append((1, e, f"resource-id='{e.rid}'"))
        elif e.desc.lower() in _FECHAR_DESCS:
            candidatos.append((2, e, f"desc='{e.desc}'"))
        elif e.text in _FECHAR_GLIFOS or e.desc in _FECHAR_GLIFOS:
            candidatos.append((3, e, f"glifo='{e.text or e.desc}'"))
        elif Tela._norm(e.text) in _FECHAR_TEXTOS:
            candidatos.append((4, e, f"text='{e.text}'"))
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: c[0])
    return candidatos[0][1], candidatos[0][2]


def _eh_tela_recompensa_ad(tela):
    """Detecta a tela de recompensa que aparece após um anúncio (AD).

    Padrão confirmado no dump real: a tela tem 'Sair' E algum marcador de recompensa
    ('Kwai Golds obtidas', 'Assista mais um para ganhar'), SEM 'Ganhar mais'
    (que é da modal de fluxo principal). Todos os elementos são clickable=False,
    então qualquer ação deve usar tap por coordenada direta.
    """
    if tela.existe_texto('Ganhar mais'):
        return False
    tem_sair = bool(tela.por_texto_exato('Sair'))
    tem_recompensa = bool(
        tela.contendo('Kwai Golds obtidas')
        or tela.contendo('Assista mais um para ganhar')
        or tela.contendo('Kwai Golds a receber')
    )
    return tem_sair and tem_recompensa


def _dispensar_tela_recompensa_ad(tela):
    """Clica 'Sair' para fechar a tela de recompensa-AD e voltar ao card list.

    ATENÇÃO: NÃO clica em 'Receba X Kwai Golds agora' — esse botão é uma armadilha
    de anúncio que abre o Google Play Store/browser, saindo do fluxo do Kwai. O gold
    já é creditado automaticamente quando o timer do vídeo termina.

    Como todos os elementos dessa tela têm clickable=False (confirmado nos dumps reais),
    os taps vão por coordenada direta via d.click(x, y).
    """
    _salvar_xml(d.dump_hierarchy(), "tela_recompensa_ad")
    relatorio("Tela recompensa-AD detectada", [
        "padrão: 'Sair' + 'Kwai Golds obtidas' sem 'Ganhar mais'",
        "ação: clicar Sair (NÃO clicar Receba — é botão de anúncio que abre Play Store)",
    ])

    sair = tela.por_texto_exato('Sair')
    if sair:
        e = sair[0]
        print(f"[AD-REWARD] Clicando 'Sair' em ({e.cx},{e.cy}) para voltar ao card list.")
        d.click(e.cx, e.cy)
        time.sleep(2.5)
        return True

    # fallback: pressiona Voltar do sistema
    print("[AD-REWARD] 'Sair' não encontrado — pressionando BACK.")
    voltar("fechar tela recompensa-AD")
    time.sleep(2)
    return True


def _estamos_no_kwai():
    """Verifica se o app em primeiro plano é o Kwai. Retorna True/False."""
    try:
        result = subprocess.run(
            ["adb", "-s", DEVICE_ID, "shell",
             "dumpsys", "window", "windows"],
            capture_output=True, text=True, timeout=5
        )
        # Procura pela atividade em foco
        for linha in result.stdout.splitlines():
            if 'mCurrentFocus' in linha or 'mFocusedApp' in linha:
                return KWAI_PACKAGE in linha
    except Exception:
        pass
    return True  # assume Kwai em caso de falha (evita loop infinito de BACK)


def retornar_ao_kwai(max_tentativas=6):
    """Se o bot acabou em outro app (Play Store, browser etc.), volta para o Kwai.

    Isso pode acontecer quando um botão de anúncio é clicado por engano. Pressiona
    BACK repetidamente até o Kwai estar em foco, com até max_tentativas.
    """
    if _estamos_no_kwai():
        return True

    print("[RETORNO] Bot fora do Kwai — pressionando BACK para retornar...")
    relatorio("Fora do Kwai", ["app em primeiro plano não é Kwai; pressionando BACK"])
    for i in range(max_tentativas):
        voltar(f"retornar ao Kwai (tentativa {i+1})")
        time.sleep(1.5)
        if _estamos_no_kwai():
            print(f"[RETORNO] ✅ Kwai em foco após {i+1} pressionamentos de BACK.")
            relatorio("Retornou ao Kwai", [f"{i+1} pressionamentos de BACK"])
            time.sleep(2)
            return True

    # Último recurso: inicia o Kwai diretamente
    print("[RETORNO] ❌ Não voltou via BACK — forçando abertura do Kwai.")
    relatorio("Kwai não retornou via BACK", ["forçando app_start"])
    try:
        d.app_start(KWAI_PACKAGE)
        time.sleep(5)
    except Exception as exc:
        print(f"[RETORNO] Falha ao abrir Kwai: {exc}")
    return False


def tratar_popups(max_rodadas=3):
    """Detecta e fecha popups/anúncios no meio da tela. PERCEBE antes de cada ação.

    Trata também a tela de recompensa-AD (padrão 'Sair'+'Kwai Golds obtidas' sem
    'Ganhar mais'), que bloqueia toda a navegação e tem todos os elementos
    clickable=False. Não mexe na modal principal ('Ganhar mais' + 'Sair').
    Retorna True se fechou algo.
    """
    fechou = False
    for rodada in range(max_rodadas):
        tela = capturar_tela(f"popup_check_r{rodada + 1}", salvar=False)

        if tela.existe_texto('Ganhar mais'):
            print("[POPUP] Modal de recompensa presente ('Ganhar mais'); não fecho nada.")
            return fechou

        # tela de recompensa-AD tem prioridade (bloqueia toda a navegação)
        if _eh_tela_recompensa_ad(tela):
            print("[POPUP] Tela de recompensa-AD detectada. Dispensando...")
            _dispensar_tela_recompensa_ad(tela)
            fechou = True
            continue

        achado = _achar_fechar_popup(tela)
        if achado is None:
            if rodada == 0:
                print("[POPUP] Nenhum popup detectado.")
            return fechou

        elem, motivo = achado
        print(f"[POPUP] Popup detectado ({motivo}) em ({elem.cx},{elem.cy}). Fechando...")
        relatorio("Popup/anúncio detectado", [
            f"motivo do match: {motivo}",
            f"elemento: {elem!r}",
            "ação: fechar para continuar o fluxo",
        ])
        _salvar_xml(d.dump_hierarchy(), f"popup_detectado_r{rodada + 1}")
        clicar_alvo(tela, elem, f"fechar popup ({motivo})")
        fechou = True
        time.sleep(1.5)

    return fechou


# ---------------------------------------------------------------------------
# NAVEGAÇÃO inicial (conectar, abrir, perfil, menu, ganhar dinheiro)
# ---------------------------------------------------------------------------
def _listar_dispositivos():
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    return [ln.split("\t")[0].strip()
            for ln in result.stdout.splitlines()[1:] if "\tdevice" in ln]


def conectar_dispositivo():
    global d, DEVICE_ID
    dispositivos = _listar_dispositivos()
    if not dispositivos:
        raise RuntimeError(
            "Nenhum dispositivo encontrado.\n"
            "Verifique: cabo USB, Depuração USB ativada e autorização RSA aceita no celular."
        )
    if len(dispositivos) == 1:
        DEVICE_ID = dispositivos[0]
        print(f"Dispositivo detectado automaticamente: {DEVICE_ID}")
    else:
        print("Múltiplos dispositivos encontrados:")
        for i, dev in enumerate(dispositivos):
            print(f"  [{i+1}] {dev}")
        escolha = input("Escolha o número do dispositivo: ").strip()
        DEVICE_ID = dispositivos[int(escolha) - 1]
        print(f"Usando dispositivo: {DEVICE_ID}")

    d = u2.connect(DEVICE_ID)
    print("Conectado com sucesso.")
    relatorio("Conectado", [f"device = {DEVICE_ID}"])


def abrir_kwai():
    print("\n>>> Abrindo o Kwai (cold start para estado consistente)...")
    # app_start sozinho apenas RETOMA a última tela (ex.: a busca). Paramos e reabrimos
    # para sempre cair no feed inicial — estado previsível para a navegação.
    try:
        d.app_stop(KWAI_PACKAGE)
        time.sleep(1)
    except Exception:
        pass
    try:
        d.app_start(KWAI_PACKAGE, stop=True)
    except TypeError:
        d.app_start(KWAI_PACKAGE)
    time.sleep(6)
    tratar_popups()  # fecha anúncio/splash de abertura, se houver
    relatorio("Kwai aberto", [f"pacote = {KWAI_PACKAGE} (cold start)"])


def _confirmar_perfil(tela):
    """Confirma que estamos no perfil próprio. Usa marcadores FORTES do perfil — evita
    'Seguindo' sozinho, que também é uma ABA do feed (deu falso positivo no dump real)."""
    for m in ['Editar perfil', 'Meus vídeos', 'Seguidores']:
        if tela.contendo(m):
            print(f"   Perfil confirmado por '{m}'.")
            return True
    return False


def _clicavel_por_rid(tela, *tokens):
    """Primeiro elemento (ou seu dono) clicável cujo resource-id contém algum dos tokens."""
    toks = [t.lower() for t in tokens]
    for e in tela.elementos:
        if e.rid and any(t in e.rid.lower() for t in toks):
            if e.clickable:
                return e
            dono = tela.clicavel_que_contem(e)
            if dono:
                return dono
    return None


def ir_para_perfil():
    print("\n>>> Indo para o Perfil (aba inferior)...")
    tela = capturar_tela("antes_perfil")
    logar_tela(tela, "antes_perfil")

    # Seletor REAL (do dump): aba inferior 'Perfil' = id_home_bottom_tab_me / fake_me_button.
    # A aba às vezes não é marcada clicável, mas clicar no centro dela funciona.
    # Casa pelo FIM do rid: 'tab_me' bate em 'id_home_bottom_tab_me' mas NÃO em
    # 'id_home_bottom_tab_message' (substring pegava a aba Mensagens por engano).
    alvo = None
    for e in tela.elementos:
        rl = e.rid.lower()
        if rl.endswith('tab_me') or rl.endswith('me_button'):
            alvo = e
            break
    if alvo is None:
        # por texto 'Perfil'/'Eu' na barra inferior (evita a aba 'Seguindo' do feed)
        for e in tela.elementos:
            if e.cy > tela.altura * 0.85 and Tela._norm(e.text) in ('perfil', 'eu', 'me'):
                alvo = e
                break

    if alvo is not None:
        clicar_ponto(alvo.cx, alvo.cy, f"abrir perfil (aba inferior) rid={alvo.rid.split('/')[-1]}")
    else:
        print("Não achei a aba de perfil por seletor; usando o canto inferior direito.")
        clicar_ponto(int(tela.largura * 0.9), int(tela.altura * 0.94), "fallback aba perfil")
    time.sleep(3)

    prof = capturar_tela("apos_perfil")
    logar_tela(prof, "apos_perfil")
    if _confirmar_perfil(prof):
        relatorio("Perfil aberto", ["confirmado por marcador forte"])
    else:
        print("⚠️  Não confirmei o perfil por marcador forte; seguindo para capturar o menu (estudo).")
        relatorio("Perfil incerto", ["sem marcador forte; seguindo para capturar o menu"])


def abrir_menu_3pontos():
    print("\n>>> Abrindo o menu (3 pontinhos / canto superior direito)...")
    tela = capturar_tela("antes_menu")
    logar_tela(tela, "tela_perfil")

    # 1) botão 'more' (3 pontinhos) no topo — rid real descoberto no dump: more_btn.
    #    (NÃO usamos 'setting': leva ao 'Editar perfil', não ao menu de recursos.)
    alvo = None
    for e in tela.elementos:
        rl = e.rid.lower()
        if e.clickable and (rl.endswith('more_btn') or rl.endswith('_more') or rl.endswith('btn_more')):
            alvo = e
            break

    # 2) por desc de menu
    if alvo is None:
        for e in tela.elementos:
            if e.clickable and Tela._norm(e.desc) in ('menu', 'mais opções', 'mais opcoes',
                                                      'more options', 'mais', 'opções', 'opcoes'):
                alvo = e
                break

    # 3) o clicável mais à direita no topo (onde fica o menu do perfil)
    if alvo is None:
        topo_dir = [e for e in tela.elementos
                    if e.clickable and e.cy < tela.altura * 0.15
                    and e.cx > tela.largura * 0.78 and e.pkg != 'com.android.systemui']
        if topo_dir:
            topo_dir.sort(key=lambda e: -e.cx)
            alvo = topo_dir[0]

    if alvo is not None:
        clicar_alvo(tela, alvo, f"abrir menu {alvo!r}")
        relatorio("Menu aberto", [f"{alvo!r}"])
    else:
        print("Não achei o menu por seletor; usando fallback no canto superior direito.")
        clicar_ponto(int(tela.largura * 0.93), int(tela.altura * 0.06), "fallback menu")
        relatorio("Menu", ["via fallback de coordenadas"])
    time.sleep(3)
    capturar_tela("apos_menu")  # captura o que abriu, para estudo


def clicar_ganhar_dinheiro():
    print("\n>>> Procurando 'Ganhar dinheiro'...")
    tela = capturar_tela("antes_ganhar_dinheiro")
    logar_tela(tela, "menu/recursos")

    # 1) por texto 'Ganhar dinheiro' (descartando convite de amigos)
    for pattern in [r'ganhar dinheiro', r'ganhe dinheiro', r'ganhar.*dinheiro']:
        achados = [e for e in tela.por_regex(pattern)
                   if not re.search(r'amig|chame|convid', e.conteudo, re.IGNORECASE)]
        if achados:
            achados.sort(key=lambda e: e.w * e.h)
            print(f"'Ganhar dinheiro' via regex '{pattern}': {achados[0]!r}")
            clicar_alvo(tela, achados[0], "clicar 'Ganhar dinheiro'")
            time.sleep(4)
            relatorio("Ganhar dinheiro", [f"via texto '{pattern}'"])
            return

    # 2) por resource-id de moeda/carteira (descoberto no dump: 'earn_coin_container')
    alvo = _clicavel_por_rid(tela, 'earn_coin', 'earn', 'coin', 'wallet', 'money', 'cash', 'gold')
    if alvo is not None:
        print(f"Entrada de moedas via resource-id: {alvo!r}")
        clicar_alvo(tela, alvo, "clicar entrada de moedas (earn_coin)")
        time.sleep(4)
        relatorio("Ganhar dinheiro", [f"via rid {alvo!r}"])
        return

    raise RuntimeError("Não encontrei 'Ganhar dinheiro' — veja o dump 'antes_ganhar_dinheiro' para mapear.")


# ---------------------------------------------------------------------------
# CARD de vídeos + botão 'Ir'
# ---------------------------------------------------------------------------
def achar_card(tela):
    """Acha o card 'Assista a vídeos para ganhar até X Kwai golds'.

    Exige a combinação que identifica o card de verdade — assist* + vídeo + ganh* E
    ('até' OU 'kwai gold') — e descarta falsos positivos parecidos da mesma tela
    (convite de amigos, 'curtir vídeo'). Calibrado contra dump real do device.
    Devolve o elemento de MENOR área (o rótulo, com a linha/altura certa) ou None.
    """
    RUINS = re.compile(r'amig|chame|convid|curt', re.IGNORECASE)
    candidatos = []
    for e in tela.com_texto():
        c = e.conteudo
        if RUINS.search(c):
            continue
        tem_base = (re.search(r'assist\w*', c, re.IGNORECASE)
                    and re.search(r'v[ií]deo', c, re.IGNORECASE)
                    and re.search(r'ganh', c, re.IGNORECASE))
        tem_premio = re.search(r'at[ée]\b', c, re.IGNORECASE) or re.search(r'kwai\s*gold', c, re.IGNORECASE)
        if tem_base and tem_premio:
            candidatos.append(e)
    if not candidatos:
        return None
    candidatos.sort(key=lambda e: e.w * e.h)
    return candidatos[0]


def _eh_ir(texto):
    """True se o rótulo é exatamente 'Ir' (ignora caixa e setas tipo 'Ir >').
    Evita falsos positivos: 'Sair', 'Abrir', 'Assistir', 'Ouvir'."""
    return re.sub(r'[^a-z]', '', (texto or '').lower()) == 'ir'


def achar_ir_do_card(tela, card):
    """DECIDIR: dentre todos os 'Ir' da tela, escolhe o que pertence ao card.

    O 'Ir' fica sempre à direita e na MESMA linha do card. Como pode haver outros cards
    (com seu próprio 'Ir') acima/abaixo, a escolha é geométrica:
      1. só os 'Ir' à direita do card;
      2. prioriza os cuja faixa vertical se sobrepõe à do card (mesma linha de fato);
      3. fallback: centro vertical próximo;
      4. empate: o mais próximo horizontalmente.
    Loga cada candidato. Devolve o Elemento 'Ir' ou None.
    """
    irs = [e for e in tela.elementos if _eh_ir(e.text) or _eh_ir(e.desc)]
    print(f"[IR] {len(irs)} botão(ões) 'Ir' na tela. "
          f"Card: centro=({card.cx},{card.cy}) altura={card.h}")

    com_overlap, proximos = [], []
    for ib in irs:
        lado = "dir" if ib.cx > card.cx else "esq"
        overlap = min(ib.bounds['bottom'], card.bounds['bottom']) - max(ib.bounds['top'], card.bounds['top'])
        dist_v = abs(ib.cy - card.cy)
        dist_h = ib.cx - card.cx
        if ib.cx <= card.cx:
            print(f"[IR]   descartado (lado={lado}) {ib!r}")
            continue
        if overlap > 0:
            com_overlap.append((dist_v, dist_h, ib))
            print(f"[IR]   MESMA-LINHA {ib!r} overlap_v={overlap} dist_v={dist_v}")
        elif dist_v <= max(card.h, ib.h) * 1.5:
            proximos.append((dist_v, dist_h, ib))
            print(f"[IR]   PRÓXIMO {ib!r} dist_v={dist_v}")
        else:
            print(f"[IR]   descartado (outra linha) {ib!r} dist_v={dist_v}")

    grupo = com_overlap or proximos
    if not grupo:
        print("[IR] Nenhum 'Ir' à direita e alinhado.")
        return None
    grupo.sort(key=lambda t: (t[0], t[1]))
    escolhido = grupo[0][2]
    print(f"[IR] Escolhido ({'mesma-linha' if com_overlap else 'proximidade'}): {escolhido!r}")
    return escolhido


def iniciar_video_pelo_card(max_scrolls=6):
    """Acha o card e clica para começar a assistir. Se o clique no card não der certo,
    clica no 'Ir' à direita (tratamento de erro do diagrama). Rola se o card não aparecer.

    Retorna True se conseguiu iniciar (entrou no vídeo), False caso contrário.
    """
    for tentativa in range(max_scrolls):
        tratar_popups()  # anúncios podem cobrir o card
        tela = capturar_tela(f"procura_card_t{tentativa + 1}")
        logar_tela(tela, f"procura_card_t{tentativa + 1}")

        card = achar_card(tela)
        if card is None:
            print(f"Card não encontrado. Rolando ({tentativa + 1}/{max_scrolls})...")
            relatorio("Card não encontrado", [f"tentativa {tentativa + 1}, rolando a tela"])
            rolar_para_baixo()
            continue

        print(f"Card encontrado: {card!r}")
        relatorio("Card encontrado", [f"{card!r}"])

        # 1) tenta clicar no próprio card
        clicar_alvo(tela, card, "clicar no card de vídeos")
        time.sleep(4)

        # PERCEBER de novo: o clique funcionou?
        depois = capturar_tela("apos_clicar_card")
        if ler_timer(depois) is not None:
            print("✅ Vídeo iniciou (timer detectado).")
            relatorio("Vídeo iniciado", ["clique no card funcionou (timer presente)"])
            return True
        card_ainda = achar_card(depois)
        if card_ainda is None:
            print("✅ Saiu da lista (provável carregamento do vídeo).")
            relatorio("Vídeo iniciado", ["card sumiu após o clique"])
            return True

        # 2) tratamento de erro: clicar no 'Ir' à direita do card
        print("Clique no card não iniciou o vídeo. Tentando o botão 'Ir' à direita...")
        relatorio("Fallback 'Ir'", ["clique no card não funcionou; procurando 'Ir' à direita"])
        ir = achar_ir_do_card(depois, card_ainda)
        if ir is not None:
            clicar_alvo(depois, ir, "clicar no 'Ir' à direita do card")
            time.sleep(4)
            checar = capturar_tela("apos_clicar_ir")
            if ler_timer(checar) is not None or achar_card(checar) is None:
                print("✅ Vídeo iniciou via 'Ir'.")
                relatorio("Vídeo iniciado", ["via botão 'Ir'"])
                return True

        # 3) fallback geométrico: lateral direita na altura do card
        cb = card_ainda.bounds
        x = max(cb['right'] - max(20, cb['width'] // 6), int((depois.largura or cb['right']) * 0.88))
        print(f"Fallback geométrico: clique na lateral direita em ({x},{card_ainda.cy}).")
        clicar_ponto(x, card_ainda.cy, "fallback lateral direita do card")
        time.sleep(4)
        checar = capturar_tela("apos_fallback_lateral")
        if ler_timer(checar) is not None or achar_card(checar) is None:
            relatorio("Vídeo iniciado", ["via fallback lateral direita"])
            return True

        print("Ainda na lista; rolando e tentando de novo.")
        rolar_para_baixo()

    print("❌ Não consegui iniciar o vídeo pelo card.")
    relatorio("Falha", ["não consegui iniciar o vídeo pelo card após scrolls"])
    return False


# ---------------------------------------------------------------------------
# TIMER do vídeo
# ---------------------------------------------------------------------------
def _extrair_segundos(texto, permitir_bare=False):
    """Extrai segundos do texto do timer. Por padrão aceita só formatos com UNIDADE
    ('15s', '15 segundos') ou 'mm:ss' — nunca número solto, que dá falso positivo
    (relógio, contadores de recompensa). `permitir_bare=True` libera número curto isolado.
    """
    if not texto:
        return None
    t = texto.strip()
    m = re.search(r'\b(\d{1,3})\s*(?:s\b|segundos?\b)', t, re.IGNORECASE)  # "15s" / "15 segundos"
    if m:
        v = int(m.group(1))
        return v if 0 <= v <= 600 else None
    m = re.search(r'\b(\d{1,2}):(\d{2})\b', t)            # mm:ss
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    if permitir_bare and re.fullmatch(r'\d{1,2}', t):     # número curto isolado (só sob pedido)
        v = int(t)
        return v if 0 <= v <= 60 else None
    return None


def ler_timer(tela):
    """DECIDIR: lê o timer (contagem regressiva) do vídeo — no TOPO, normalmente à direita.

    Restringe à faixa logo abaixo da status bar e acima de 30% da altura (onde o timer do
    Kwai fica), ignora a status bar do sistema, e só aceita formatos com unidade/relógio
    (nunca número solto). Isso elimina relógio, 'Expira em ...' e contadores da página de
    recompensa — falsos positivos confirmados no dump real. Devolve segundos ou None.
    """
    band_topo = 60                                        # abaixo da status bar
    band_base = tela.altura * 0.30 if tela.altura else None
    candidatos = []
    for e in tela.com_texto():
        if e.pkg == 'com.android.systemui':
            continue
        if band_base is not None and not (band_topo < e.cy < band_base):
            continue
        v = _extrair_segundos(e.text)
        if v is None:
            v = _extrair_segundos(e.desc)
        if v is not None:
            candidatos.append((e.cx, v))
    if not candidatos:
        return None
    candidatos.sort(key=lambda c: -c[0])  # mais à direita primeiro
    return candidatos[0][1]


def assistir_ate_timer_acabar():
    """Lê o timer repetidamente até zerar ou desaparecer.

    Retorna True quando o vídeo terminou (timer zerou/sumiu),
    False quando passou TIMEOUT_SEM_TIMER sem nunca ver timer (anúncio sem timer).
    """
    print("\n🎬 Assistindo o vídeo — lendo o timer...")
    relatorio("Assistindo vídeo", ["lendo o timer até zerar"])
    inicio = time.time()
    ultimo = None
    detectou = False
    sem_timer_desde = None

    while time.time() - inicio < MAX_ESPERA_VIDEO:
        tela = capturar_tela("video_timer", salvar=False)
        v = ler_timer(tela)

        if v is not None:
            detectou = True
            sem_timer_desde = None
            if v != ultimo:
                print(f"⏱️  Timer: {v}s restantes")
                ultimo = v
            if v <= 0:
                print("✅ Timer zerou — vídeo finalizado.")
                relatorio("Timer zerou", [f"último valor lido = {v}s"])
                _salvar_xml(d.dump_hierarchy(), "timer_zerou")
                return True
        else:
            if detectou:
                print(f"✅ Timer desapareceu (último: {ultimo}s) — vídeo finalizado.")
                relatorio("Timer desapareceu", [f"após contagem (último {ultimo}s)"])
                _salvar_xml(d.dump_hierarchy(), "timer_sumiu")
                return True
            if sem_timer_desde is None:
                sem_timer_desde = time.time()
                print("⏳ Ainda sem timer detectável...")
            elif time.time() - sem_timer_desde > TIMEOUT_SEM_TIMER:
                print(f"⚠️  {TIMEOUT_SEM_TIMER}s sem timer — provável anúncio sem timer.")
                relatorio("Sem timer", [f"{TIMEOUT_SEM_TIMER}s sem detectar; tratando como anúncio"])
                _salvar_xml(d.dump_hierarchy(), "sem_timer_25s")
                return False

        time.sleep(INTERVALO_LEITURA_TIMER)

    print(f"⚠️  Teto de {MAX_ESPERA_VIDEO}s atingido aguardando o timer.")
    relatorio("Timeout do vídeo", [f"teto de {MAX_ESPERA_VIDEO}s"])
    return False


# ---------------------------------------------------------------------------
# PÓS-VÍDEO: esperar, voltar, tratar 'Ganhar mais' / 'Sair'
# ---------------------------------------------------------------------------
def esperar_pos_timer():
    seg = random.randint(*ESPERA_POS_TIMER)
    print(f"Aguardando {seg}s antes de voltar (conforme o fluxo)...")
    relatorio("Espera pós-timer", [f"{seg}s (faixa {ESPERA_POS_TIMER[0]}–{ESPERA_POS_TIMER[1]}s)"])
    time.sleep(seg)


def lidar_pos_video():
    """Aperta Voltar e trata as possibilidades do diagrama após o timer acabar.

    Possibilidades (em ordem de verificação):
      (a) tela de recompensa-AD  → coletar + 'Sair' para voltar ao card list.
      (b) modal 'Ganhar mais' + 'Sair' → clicar 'Ganhar mais' (próximo vídeo auto-inicia).
      (c) voltou direto para a lista → nada a fazer, loop reabre o card.
      (d) transição em curso → aguarda e tenta novamente.
    """
    voltar("encerrar vídeo")
    time.sleep(2)

    for tentativa in range(5):
        # Salva dump apenas na 1ª e na última tentativa para não criar centenas de arquivos
        salvar = tentativa in (0, 4)
        tela = capturar_tela(f"pos_voltar_t{tentativa + 1}", salvar=salvar)

        # (a) tela de recompensa-AD — detectar E tratar antes de qualquer outra coisa
        if _eh_tela_recompensa_ad(tela):
            print(f"[PÓS-VÍDEO] Tela de recompensa-AD detectada (tentativa {tentativa+1}).")
            _dispensar_tela_recompensa_ad(tela)
            relatorio("Pós-vídeo: recompensa-AD dispensada",
                      ["'Sair'+'Kwai Golds obtidas' → coletou e saiu"])
            return

        # (b) modal 'Ganhar mais' + 'Sair'
        gm = tela.por_texto_exato('Ganhar mais')
        sair = tela.por_texto_exato('Sair')
        if gm and sair:
            print("✅ Modal 'Ganhar mais' + 'Sair' → clicando em 'Ganhar mais'.")
            relatorio("Modal pós-vídeo", ["'Ganhar mais'+'Sair' → clicou 'Ganhar mais'"])
            clicar_alvo(tela, gm[0], "clicar 'Ganhar mais'")
            time.sleep(4)
            return

        # (c) card visível — voltou direto para a lista
        if achar_card(tela):
            print("Voltou direto para a lista de cards.")
            relatorio("Pós-vídeo", ["voltou para lista de cards"])
            return

        # (d) ainda transicionando — aguarda
        print(f"[PÓS-VÍDEO] Aguardando transição (tentativa {tentativa+1}/5)...")
        time.sleep(2)

    print("Pós-vídeo: estado não identificado; o loop vai tentar reabrir o card.")
    relatorio("Pós-vídeo indefinido", ["loop reabrirá o card"])


# ---------------------------------------------------------------------------
# LOOP principal
# ---------------------------------------------------------------------------
def loop_assistir_videos():
    print("\n" + "=" * 60)
    print("INICIANDO O LOOP DE ASSISTIR VÍDEOS")
    print("=" * 60)
    n = 0
    while True:
        n += 1
        print(f"\n{'='*60}\n>>>>> VÍDEO #{n}\n{'='*60}")
        relatorio(f"=== Iteração {n} ===")

        # PERCEBER primeiro: garante que estamos no Kwai (anúncios podem abrir outros apps)
        retornar_ao_kwai()
        tratar_popups()
        tela = capturar_tela(f"iter{n}_estado")

        if ler_timer(tela) is None:
            # Não há vídeo rodando -> precisa iniciar um pelo card
            if not iniciar_video_pelo_card():
                print("Não consegui iniciar o vídeo; aguardando 3s e tentando de novo.")
                time.sleep(3)
                continue

        # ASSISTIR
        terminou = assistir_ate_timer_acabar()

        if terminou is False:
            # anúncio sem timer: volta e segue para a próxima iteração
            print("Anúncio sem timer — voltando para continuar.")
            voltar("fechar anúncio sem timer")
            time.sleep(2)
            tratar_popups()
            continue

        # Timer terminou normalmente -> espera 5–10s, volta e trata modal
        esperar_pos_timer()
        lidar_pos_video()


if __name__ == "__main__":
    iniciar_logging()
    try:
        conectar_dispositivo()
        abrir_kwai()
        ir_para_perfil()
        abrir_menu_3pontos()
        clicar_ganhar_dinheiro()
        loop_assistir_videos()
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
        relatorio("Interrompido", ["KeyboardInterrupt"])
    except Exception:
        import traceback
        print("\n" + "=" * 60)
        print("ERRO FATAL — traceback completo abaixo (também salvo no log):")
        print("=" * 60)
        traceback.print_exc()
        relatorio("ERRO FATAL", ["ver traceback no .log"])
        raise
