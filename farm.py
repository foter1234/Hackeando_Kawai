import uiautomator2 as u2
import time
import subprocess
import xml.etree.ElementTree as ET
import re

DEVICE_ID = "ZF525J6NKX"
KWAI_PACKAGE = "com.kwai.video"

d = None


def conectar_dispositivo(retries=3, delay=5):
    global d
    for attempt in range(1, retries + 1):
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        if DEVICE_ID in result.stdout and "offline" not in result.stdout:
            print(f"Dispositivo {DEVICE_ID} detectado. Conectando...")
            d = u2.connect(DEVICE_ID)
            print("Conectado com sucesso.")
            return
        print(f"[{attempt}/{retries}] Dispositivo {DEVICE_ID} não encontrado. Aguardando {delay}s...")
        print("Dispositivos ADB disponíveis:")
        print(result.stdout.strip() or "  (nenhum)")
        time.sleep(delay)
    raise RuntimeError(
        f"Dispositivo {DEVICE_ID} não está online após {retries} tentativas.\n"
        "Verifique: cabo USB conectado, Depuração USB ativada e autorização RSA aceita no celular."
    )


def abrir_kwai():
    d.app_start(KWAI_PACKAGE)
    time.sleep(5)


def confirmar_perfil():
    """Confirma se a tela atual é o perfil."""
    checks = [
        {'text': 'Editar perfil'},
        {'text': 'Editar'},
        {'text': 'Meus vídeos'},
        {'text': 'Seguindo'},
        {'text': 'Seguidores'},
        {'description': 'Editar perfil'},
        {'description': 'Profile'},
    ]
    for sel in checks:
        if d(**sel).exists:
            print(f"Tela de perfil confirmada por {sel}")
            return True
    return False


def clicar_perfil_por_seletor():
    selectors = [
        {'text': 'Perfil'},
        {'text': 'Me'},
        {'text': 'Profile'},
        {'text': 'Eu'},
        {'description': 'Perfil'},
        {'description': 'Me'},
        {'description': 'Profile'},
        {'description': 'Eu'},
        {'resourceId': 'com.kwai.video:id/tab_profile'},
        {'resourceId': 'com.kwai.video:id/profile_tab'},
    ]

    for sel in selectors:
        elem = d(**sel)
        if elem.exists:
            print(f"Encontrado seletor de perfil: {sel}")
            elem.click()
            time.sleep(4)
            if confirmar_perfil():
                return True
            print("Clique não confirmou perfil; tentarei outro seletor.")
    return False


def entrar_perfil():
    """Tenta abrir a aba de perfil do Kwai."""
    print("Tentando entrar no perfil do Kwai...")

    if clicar_perfil_por_seletor():
        return

    print("Não encontrou seletor de perfil. Tentando fallback por coordenadas.")
    width, height = d.window_size()
    fallback_x = int(width * 0.92)
    fallback_y = int(height * 0.92)

    try:
        d.click(fallback_x, fallback_y)
        time.sleep(4)
        if confirmar_perfil():
            print("Perfil aberto com clique de fallback.")
            return
        print("Clique de fallback não confirmou perfil.")
    except Exception as exc:
        print(f"Falha ao tentar abrir o perfil por coordenadas: {exc}")

    print("Tentando dump de hierarquia para debug...")
    try:
        xml = d.dump_hierarchy() if hasattr(d, 'dump_hierarchy') else None
        if xml:
            print(xml[:1000])
        else:
            print("Dump de hierarquia não disponível no objeto d.")
    except Exception as exc:
        print(f"Falha ao gerar dump de hierarquia: {exc}")

    raise RuntimeError("Não foi possível abrir o perfil do Kwai")


def clicar_menu_tres_pontos():
    """Clica nos três pontinhos no canto superior direito do Kwai."""
    print("Tentando clicar nos 3 pontinhos no canto superior direito...")
    selectors = [
        {'description': 'Mais opções'},
        {'description': 'Menu'},
        {'description': 'More options'},
        {'description': 'Mais'},
        {'description': 'Opções'},
        {'text': '...'},
        {'text': '⋮'},
        {'text': '•••'},
    ]

    for sel in selectors:
        elem = d(**sel)
        if elem.exists:
            print(f"Encontrado menu 3 pontos via {sel}")
            elem.click()
            time.sleep(3)
            return

    width, height = d.window_size()
    fallback_x = int(width * 0.92)
    fallback_y = int(height * 0.08)
    print(f"Não encontrou seletor de menu. Usando fallback no coordenadas {fallback_x},{fallback_y}.")

    try:
        d.click(fallback_x, fallback_y)
        time.sleep(3)
        print("Clique de fallback no canto superior direito executado.")
    except Exception as exc:
        print(f"Falha ao clicar nos 3 pontinhos: {exc}")
        raise RuntimeError("Não foi possível clicar nos 3 pontinhos do menu")


def clicar_ganhar_dinheiro():
    """Clica no ícone ou botão 'Ganhar dinheiro'."""
    print("Tentando clicar em 'Ganhar dinheiro'...")
    patterns = [
        r'(?i).*ganhar dinheiro.*',
        r'(?i).*ganhe dinheiro.*',
        r'(?i).*ganhar.*dinheiro.*',
        r'(?i).*dinheiro.*ganhar.*',
        r'(?i).*kwai golds?.*',
    ]

    def buscar_e_clicar():
        for pattern in patterns:
            print(f"Buscando elemento com regex '{pattern}'...")
            for query in [
                {'textMatches': pattern},
                {'descriptionMatches': pattern},
                {'textContains': 'Ganhar dinheiro'},
                {'descriptionContains': 'Ganhar dinheiro'},
            ]:
                elem = d(**query)
                if elem.exists:
                    print(f"Encontrado elemento por {query}")
                    _clicar_elemento(elem)
                    return True
        return False

    if buscar_e_clicar():
        return

    print("Não encontrou o botão 'Ganhar dinheiro' diretamente. Tentando busca alternativa por ambos 'ganhar' e 'dinheiro'...")
    alt_xpath = (
        "//*[ (contains(@text,'Ganhar') and contains(@text,'dinheiro')) "
        "or (contains(@text,'dinheiro') and contains(@text,'Ganhar')) "
        "or (contains(@content-desc,'Ganhar') and contains(@content-desc,'dinheiro')) "
        "or (contains(@content-desc,'dinheiro') and contains(@content-desc,'Ganhar')) ]"
    )
    try:
        elems = d.xpath(alt_xpath)
        if elems.exists:
            for elem in elems:
                print("Encontrado elemento via XPath com 'Ganhar' e 'dinheiro'")
                _clicar_elemento(elem)
                return True
    except Exception as exc:
        print(f"XPath falhou: {exc}")

    print("Não encontrou o botão com texto completo. Procurando candidatos mais amplos, mas evitando falsos positivos...")
    broader = [
        {'textContains': 'Ganhar'},
        {'descriptionContains': 'Ganhar'},
        {'textContains': 'dinheiro'},
        {'descriptionContains': 'dinheiro'},
    ]
    bad_terms = ['jogo', 'jogos', 'game', 'games', 'play', 'jogar', 'assistir', 'video']
    for query in broader:
        elem = d(**query)
        if elem.exists:
            info = elem.info
            text = ((info.get('text') or '') + ' ' + (info.get('description') or '')).strip()
            if any(bad in text.lower() for bad in bad_terms):
                print(f"Ignorando candidato com texto: {text}")
                continue
            print(f"Clicando candidato amplo: {text}")
            _clicar_elemento(elem)
            return

    print("Não foi possível localizar um elemento de 'Ganhar dinheiro' diretamente. Verifique se o menu abriu corretamente.")
    raise RuntimeError("Não foi possível clicar no ícone 'Ganhar dinheiro' após scroll")


def _clicar_elemento(elem):
    try:
        if not elem.exists:
            raise RuntimeError("Elemento não existe no momento do clique")

        print(f"Clicando no elemento: {elem}")
        try:
            elem.click()
            time.sleep(4)
            return
        except Exception as exc_click:
            print(f"Clique direto falhou: {exc_click}")

        info = elem.info
        bounds = info.get('bounds') or info.get('visibleBounds') or info.get('boundsInParent')
        if bounds and all(k in bounds for k in ('left', 'top', 'right', 'bottom')):
            x = (bounds['left'] + bounds['right']) // 2
            y = (bounds['top'] + bounds['bottom']) // 2
            print(f"Tentando clique por coordenadas {x},{y}...")
            d.click(x, y)
            time.sleep(4)
            return

        raise RuntimeError("Não foi possível clicar no elemento e não há bounds válidos para fallback")
    except Exception as exc:
        print(f"Erro ao clicar no elemento: {exc}")
        raise


def scroll_down(retries=5):
    width, height = d.window_size()
    x = int(width * 0.5)
    start_y = int(height * 0.75)
    end_y = int(height * 0.35)
    for _ in range(retries):
        d.swipe(x, start_y, x, end_y, duration=0.4)
        time.sleep(1)


def clicar_assista_videos():
    """Rola a tela e clica no card de recompensa de vídeos com botão 'Ir'."""
    print("Procurando o card 'Assistir vídeos para ganhar até ...'...")
    patterns = [
        r'(?i).*assistir v[ií]deos para ganhar.*até.*',
        r'(?i).*assistir v[ií]deos para ganhar.*',
        r'(?i).*assista.*v[ií]deos para ganhar.*',
        r'(?i).*assistir v[ií]deos.*ganhar.*',
        r'(?i).*v[ií]deos para ganhar.*',
    ]

    for attempt in range(6):
        card_elem = _find_card_by_regex(patterns)
        if card_elem is not None:
            print("Encontrado card principal com o texto correto.")
            if _clicar_ir_relacionado(card_elem):
                return
            print("Não conseguiu clicar diretamente no botão 'Ir' relacionado. Tentando clicar no próprio card.")
            try:
                _clicar_elemento(card_elem)
                return
            except Exception as exc:
                print(f"Falha ao clicar no card principal: {exc}")

        print(f"Card não encontrado. Rolando a tela ({attempt + 1}/6)...")
        scroll_down(retries=1)

    raise RuntimeError("Não foi possível encontrar o card 'Assista a vídeos para ganhar...' após scroll")


def _find_card_by_regex(patterns):
    for pattern in patterns:
        print(f"Buscando card com regex '{pattern}'...")
        for selector_type in ['textMatches', 'descriptionMatches']:
            query = {selector_type: pattern}
            elem = d(**query)
            if elem.exists:
                print(f"Encontrado card por {selector_type}")
                return elem
    return None


def _clicar_ir_relacionado(card_elem):
    if not card_elem.exists:
        return False

    info = card_elem.info
    bounds = info.get('bounds') or info.get('visibleBounds') or {}
    if not bounds or not all(k in bounds for k in ('left', 'top', 'right', 'bottom')):
        return False

    mid_y = (bounds['top'] + bounds['bottom']) // 2
    candidates = [
        {'text': 'Ir'},
        {'textMatches': r'(?i)^ir$'},
        {'description': 'Ir'},
        {'descriptionMatches': r'(?i)^ir$'},
    ]

    for query in candidates:
        cand = d(**query)
        if cand.exists:
            try:
                cand_info = cand.info
                cand_bounds = cand_info.get('bounds') or cand_info.get('visibleBounds') or {}
                if all(k in cand_bounds for k in ('left', 'top', 'right', 'bottom')):
                    cand_mid_y = (cand_bounds['top'] + cand_bounds['bottom']) // 2
                    if abs(cand_mid_y - mid_y) <= max((bounds['bottom'] - bounds['top']) * 2, 200):
                        print(f"Clicando botão 'Ir' próximo ao card usando {query}.")
                        _clicar_elemento(cand)
                        return True
                else:
                    print(f"Clicando botão 'Ir' sem bounds específicos usando {query}.")
                    _clicar_elemento(cand)
                    return True
            except Exception as exc:
                print(f"Falha ao avaliar candidato 'Ir': {exc}")
                continue

    print("Não encontrou botão 'Ir' próximo ao card. Tentando fallback na área do card.")
    try:
        x = bounds['right'] - max(20, (bounds['right'] - bounds['left']) // 6)
        y = mid_y
        print(f"Tentativa de clique na área direita do card em {x},{y}.")
        d.click(x, y)
        time.sleep(4)
        return True
    except Exception as exc:
        print(f"Falha no fallback do card: {exc}")
        return False


def aguardar_e_fechar_video(max_espera_por_video=120):
    """Loop: espera timer zerar → clica 'Ganhar mais' → repete."""
    videos_assistidos = 0

    while True:
        print(f"Aguardando fim do timer do vídeo {videos_assistidos + 1}...")

        # Passo 1: aguarda o timer chegar a 0
        if not _aguardar_timer_acabar(max_espera_por_video):
            print("Timer não terminou no tempo esperado. Parando.")
            return

        videos_assistidos += 1
        print(f"Vídeo #{videos_assistidos} finalizado!")
        time.sleep(2)

        # Passo 2: verifica se apareceu "Ganhar mais"
        if _clicar_ganhar_mais():
            print("Clicou em 'Ganhar mais'. Próximo vídeo em breve...")
            time.sleep(4)
        else:
            print("'Ganhar mais' não apareceu. Parando de assistir vídeos.")
            return


def _aguardar_timer_acabar(max_espera):
    """Lê o timer do vídeo (formato: '15s Seja recompensado após') e aguarda até zerar."""
    inicio = time.time()
    ultimo_timer = None

    while time.time() - inicio < max_espera:
        try:
            xml = d.dump_hierarchy()
            root = ET.fromstring(xml)

            timer_agora = None
            # Procura por padrão: "15s Seja recompensado após"
            for node in root.iter():
                text = node.attrib.get('text', '').strip()
                match = re.search(r'(\d+)s\s+Seja recompensado', text)
                if match:
                    timer_agora = int(match.group(1))
                    break

            if timer_agora is not None:
                if ultimo_timer != timer_agora:
                    print(f"⏱️  Timer: {timer_agora}s")
                    ultimo_timer = timer_agora

                if timer_agora == 0:
                    print("⏱️  Timer zerou! Vídeo acabou.")
                    return True
            else:
                # Timer desapareceu - significa que acabou
                if ultimo_timer is not None:
                    print("⏱️  Timer desapareceu - Vídeo finalizado!")
                    return True

        except Exception as e:
            print(f"Erro ao ler timer: {e}")

        time.sleep(2)

    print(f"Timeout de {max_espera}s aguardando timer")
    return False


def _clicar_ganhar_mais(timeout=15):
    """Aguarda e clica em 'Ganhar mais'. Retorna False se não aparecer."""
    inicio = time.time()
    while time.time() - inicio < timeout:
        for sel in [{'text': 'Ganhar mais'}, {'descriptionContains': 'Ganhar mais'}, {'textContains': 'Ganhar mais'}]:
            elem = d(**sel)
            if elem.exists:
                print("'Ganhar mais' encontrado. Tocando via adb...")
                try:
                    info = elem.info
                    bounds = info.get('bounds') or info.get('visibleBounds', {})
                    x = (bounds['left'] + bounds['right']) // 2
                    y = (bounds['top'] + bounds['bottom']) // 2
                    subprocess.run(["adb", "-s", DEVICE_ID, "shell", "input", "tap", str(x), str(y)], check=True)
                except Exception as e:
                    print(f"Erro ao tocar 'Ganhar mais': {e}")
                return True
        time.sleep(1)
    return False


if __name__ == "__main__":
    conectar_dispositivo()
    abrir_kwai()
    entrar_perfil()
    clicar_menu_tres_pontos()
    clicar_ganhar_dinheiro()
    clicar_assista_videos()
    aguardar_e_fechar_video()
