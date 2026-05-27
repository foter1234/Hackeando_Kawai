import uiautomator2 as u2
import time

DEVICE_ID = "ZF525J6NKX"
KWAI_PACKAGE = "com.kwai.video"

d = u2.connect(DEVICE_ID)


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
    selectors = [
        {'text': 'Ganhar dinheiro'},
        {'description': 'Ganhar dinheiro'},
        {'text': 'Ganhar dinheiro!'},
        {'text': 'ganhar dinheiro'},
        {'description': 'ganhar dinheiro'},
    ]

    for sel in selectors:
        elem = d(**sel)
        if elem.exists:
            print(f"Encontrado botão 'Ganhar dinheiro' via {sel}")
            elem.click()
            time.sleep(4)
            return

    print("Não encontrou o botão 'Ganhar dinheiro' por selector. Tentando fallback de posição.")
    width, height = d.window_size()
    fallback_x = int(width * 0.55)
    fallback_y = int(height * 0.45)

    try:
        d.click(fallback_x, fallback_y)
        time.sleep(4)
        print("Clique de fallback em 'Ganhar dinheiro' executado.")
    except Exception as exc:
        print(f"Falha ao clicar em 'Ganhar dinheiro': {exc}")
        raise RuntimeError("Não foi possível clicar no ícone 'Ganhar dinheiro'")


if __name__ == "__main__":
    abrir_kwai()
    entrar_perfil()
    clicar_menu_tres_pontos()
    clicar_ganhar_dinheiro()
