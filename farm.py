import uiautomator2 as u2
import time
import subprocess

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
        'Ganhar dinheiro',
        'Ganhe dinheiro',
        'Ganhar',
        'Ganha dinheiro',
        'Kwai gold',
        'Kwai golds',
    ]

    def buscar_e_clicar():
        for pattern in patterns:
            print(f"Buscando elemento com texto/descrição contendo '{pattern}'...")
            for query in [
                {'text': pattern},
                {'textContains': pattern},
                {'description': pattern},
                {'descriptionContains': pattern},
            ]:
                elem = d(**query)
                if elem.exists:
                    print(f"Encontrado elemento por {query}")
                    _clicar_elemento(elem)
                    return True

        if hasattr(d, 'xpath'):
            print("Tentando busca XPath por 'Ganhar'.")
            xpath = "//*[contains(@text, 'Ganhar') or contains(@content-desc, 'Ganhar') or contains(@text, 'ganhar') or contains(@content-desc, 'ganhar')]"
            elems = d.xpath(xpath)
            if elems.exists:
                for elem in elems:
                    print("Encontrado elemento via XPath com 'Ganhar'")
                    _clicar_elemento(elem)
                    return True
        return False

    if buscar_e_clicar():
        return

    print("Não encontrou sem scroll. Rolando a tela para baixo e tentando novamente...")
    for attempt in range(1, 5):
        scroll_down(retries=1)
        print(f"Pesquisa após scroll {attempt}/4")
        if buscar_e_clicar():
            return

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
    """Rola a tela e clica no card 'Asista a vídeos para ganhar X kwai golds'."""
    print("Procurando o card 'Asista a vídeos para ganhar X kwai golds'...")
    patterns = [
        'Asista a vídeos para ganhar',
        'Asista a vídeo para ganhar',
        'kwai golds',
        'kwai gold',
        'ganhar',
    ]

    for attempt in range(6):
        for pattern in patterns:
            elem = d(textContains=pattern)
            if elem.exists:
                print(f"Encontrado elemento com texto '{pattern}'")
                elem.click()
                time.sleep(4)
                return

        print(f"Não encontrado ainda. Rolando a tela ({attempt + 1}/6)...")
        scroll_down(retries=1)

    raise RuntimeError("Não foi possível encontrar o card 'Asista a vídeos para ganhar X kwai golds'")


if __name__ == "__main__":
    conectar_dispositivo()
    abrir_kwai()
    entrar_perfil()
    clicar_menu_tres_pontos()
    clicar_ganhar_dinheiro()
    clicar_assista_videos()
