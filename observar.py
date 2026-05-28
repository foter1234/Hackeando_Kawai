#!/usr/bin/env python3
"""Modo observação: descreve a tela do Kwai a cada N segundos.

Abre o Kwai e fica lendo a hierarquia de elementos enquanto você navega
manualmente. Imprime tudo que aparece na tela com coordenadas.

Uso:
    python observar.py                  # intervalo 4s, 60 frames
    python observar.py --intervalo 3    # mais rápido
    python observar.py --nao-abrir      # observa o app já aberto
"""

import uiautomator2 as u2
import time
import subprocess
import re
import argparse
from datetime import datetime

KWAI_PACKAGE = "com.kwai.video"
NBSP = " "

d = None
DEVICE_ID = None


def _adb(*args, capture=True):
    cmd = ["adb"]
    if DEVICE_ID:
        cmd += ["-s", DEVICE_ID]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=capture, text=True)


def _norm(s):
    return (s or "").replace(NBSP, " ").strip()


def _attr(node, name):
    m = re.search(r'\b' + re.escape(name) + r'="([^"]*)"', node)
    return m.group(1) if m else ""


def _elementos():
    try:
        xml = d.dump_hierarchy()
    except Exception:
        return []
    elems = []
    for m in re.finditer(r'<node[^>]*>', xml):
        node = m.group(0)
        b = re.findall(r'-?\d+', _attr(node, "bounds"))
        if len(b) != 4:
            continue
        l, t, r, bot = map(int, b)
        txt = _norm(_attr(node, "text"))
        desc = _norm(_attr(node, "content-desc"))
        rid_full = _attr(node, "resource-id")
        rid = rid_full.split("/")[-1] if "/" in rid_full else rid_full
        cls = _attr(node, "class").split(".")[-1]
        clickable = _attr(node, "clickable") == "true"
        if not txt and not desc and not rid:
            continue
        elems.append({
            "text": txt,
            "desc": desc,
            "rid": rid,
            "cls": cls,
            "clickable": clickable,
            "bounds": (l, t, r, bot),
            "cx": (l + r) // 2,
            "cy": (t + bot) // 2,
            "w": r - l,
            "h": bot - t,
        })
    return elems


# ------------------------------------------------------------------ estados --

ESTADOS = {
    "VIDEO_RECOMPENSADO":    [r'seja recompensado', r'recompensado após'],
    "RECOMPENSA_COLETADA":   [r'golds recebidos'],
    "POS_VIDEO_GANHAR_MAIS": [r'ganhar mais'],
    "ANUNCIOS_PREMIADOS_TILE": [r'an[úu]ncios?\s+premiad'],
    "GANHAR_DINHEIRO_MAIN":  [r'kwai golds', r'check.in diário', r'convidar amigos'],
    "MENU_3PONTOS":          [r'ganhar\s*dinheiro', r'configurações'],
    "PERFIL":                [r'editar perfil', r'seguidores', r'seguindo'],
    "HOME_FEED":             [r'para você', r'descobrir', r'seguindo'],
    "AD_DRAG_SHEET":         [r'layout_drag'],  # detectado pelo rid
}


def _identificar_tela(elems):
    tudo = []
    rids = []
    for e in elems:
        campo = _norm(e["text"] + " " + e["desc"])
        if campo:
            tudo.append(campo.lower())
        if e["rid"]:
            rids.append(e["rid"].lower())

    texto_completo = " | ".join(tudo)

    if any("drag" in r and "close" in r for r in rids):
        return "AD_DRAG_SHEET"

    for estado, padroes in ESTADOS.items():
        if estado == "AD_DRAG_SHEET":
            continue
        for p in padroes:
            if re.search(p, texto_completo, re.I):
                return estado

    return "DESCONHECIDA"


# --------------------------------------------------------------- impressão --

def _descrever(frame, elems, tela):
    ts = datetime.now().strftime("%H:%M:%S")
    sep = "=" * 62
    print(f"\n{sep}")
    print(f"  Frame #{frame:03d}  {ts}  TELA: {tela}")
    print(sep)

    clicaveis = [e for e in elems if e["clickable"] and (e["text"] or e["desc"])]
    info = [e for e in elems if not e["clickable"] and (e["text"] or e["desc"])]

    if clicaveis:
        print("  [BOTOES / CLICAVEIS]")
        for e in clicaveis:
            label = e["text"] or e["desc"]
            rid_s = f"  #{e['rid']}" if e["rid"] else ""
            print(f"    ({e['cx']:4d},{e['cy']:4d})  {e['w']}x{e['h']:3d}  {label!r}{rid_s}")

    if info:
        print("  [TEXTOS NA TELA]")
        for e in info[:25]:
            label = e["text"] or e["desc"]
            if len(label) > 80:
                label = label[:77] + "..."
            rid_s = f"  #{e['rid']}" if e["rid"] else ""
            print(f"    ({e['cx']:4d},{e['cy']:4d})           {label!r}{rid_s}")


# ---------------------------------------------------------------- conexão --

def conectar():
    global d, DEVICE_ID
    r = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    online = []
    for line in r.stdout.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            online.append(parts[0])
    if not online:
        raise RuntimeError("Nenhum dispositivo adb online.")
    if len(online) > 1:
        print("Dispositivos disponíveis:")
        for i, s in enumerate(online):
            print(f"  [{i+1}] {s}")
        escolha = input("Escolha o número: ").strip()
        try:
            DEVICE_ID = online[int(escolha) - 1]
        except Exception:
            DEVICE_ID = online[0]
    else:
        DEVICE_ID = online[0]
    print(f"Conectando a {DEVICE_ID}...")
    d = u2.connect(DEVICE_ID)
    _ = d.info
    print("Conectado!\n")


def main():
    parser = argparse.ArgumentParser(description="Observa a tela do Kwai e descreve o que está visível.")
    parser.add_argument("--intervalo", type=float, default=4.0,
                        help="Segundos entre leituras (padrão: 4)")
    parser.add_argument("--frames", type=int, default=60,
                        help="Número de leituras (padrão: 60 ≈ 4 min)")
    parser.add_argument("--nao-abrir", action="store_true",
                        help="Não abre o Kwai; observa o que já está na tela")
    args = parser.parse_args()

    conectar()

    if not args.nao_abrir:
        print("Abrindo o Kwai...")
        d.app_start(KWAI_PACKAGE, use_monkey=True)
        time.sleep(5)
        print("Kwai aberto. Navegue manualmente no celular.\n")

    print(f"Capturando {args.frames} frames com intervalo de {args.intervalo}s.")
    print("Pressione Ctrl+C para parar a qualquer momento.\n")

    for i in range(1, args.frames + 1):
        elems = _elementos()
        tela = _identificar_tela(elems)
        _descrever(i, elems, tela)
        try:
            time.sleep(args.intervalo)
        except KeyboardInterrupt:
            print("\n[observação interrompida pelo usuário]")
            break

    print("\nObservação finalizada.")


if __name__ == "__main__":
    main()
