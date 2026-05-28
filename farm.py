import uiautomator2 as u2
import time
import subprocess
import xml.etree.ElementTree as ET
import re

DEVICE_ID = None
KWAI_PACKAGE = "com.kwai.video"

d = None


def _listar_dispositivos():
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    dispositivos = []
    for line in result.stdout.splitlines()[1:]:
        if "\tdevice" in line:
            dispositivos.append(line.split("\t")[0].strip())
    return dispositivos


def conectar_dispositivo():
    global d, DEVICE_ID

    dispositivos = _listar_dispositivos()

    if not dispositivos:
        raise RuntimeError(
            "Nenhum dispositivo encontrado.\n"
            "Verifique: cabo USB conectado, Depuração USB ativada e autorização RSA aceita no celular."
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


def _log_todos_elementos():
    """Imprime todos os elementos visíveis na tela para debug."""
    try:
        xml = d.dump_hierarchy()
        root = ET.fromstring(xml)

        print("\n" + "="*60)
        print("🔍 DUMP DE TODOS OS ELEMENTOS NA TELA:")
        print("="*60)

        elementos_encontrados = []
        for i, node in enumerate(root.iter()):
            text = node.attrib.get('text', '').strip()
            desc = node.attrib.get('content-desc', '').strip()
            resource_id = node.attrib.get('resource-id', '').strip()

            if text or desc:
                elementos_encontrados.append({
                    'index': i,
                    'text': text,
                    'description': desc,
                    'resource-id': resource_id
                })

        # Imprime todos os elementos encontrados
        for elem in elementos_encontrados:
            linha = f"[{elem['index']}]"
            if elem['text']:
                linha += f" TEXT: '{elem['text']}'"
            if elem['description']:
                linha += f" DESC: '{elem['description']}'"
            if elem['resource-id']:
                linha += f" RID: '{elem['resource-id']}'"
            print(linha)

        print("="*60)
        print(f"Total de {len(elementos_encontrados)} elementos encontrados\n")

    except Exception as e:
        print(f"Erro ao fazer dump de elementos: {e}")


def clicar_assista_videos():
    """Rola a tela e clica no card de recompensa de vídeos com botão 'Ir'."""
    # Aguarda a tela carregar completamente
    time.sleep(3)

    # Log de debug: mostra todos os elementos
    _log_todos_elementos()

    print("Procurando o card 'Assistir vídeos para ganhar até ...'...")

    # Log de debug: elementos relevantes
    try:
        xml = d.dump_hierarchy()
        root = ET.fromstring(xml)

        print("\n" + "="*60)
        print("🔍 ELEMENTOS RELEVANTES (contém vídeo/ganhar):")
        print("="*60)

        palavras_chave = ['video', 'ganhar', 'assistir', 'card', 'recompensa', 'ir']
        for node in root.iter():
            text = (node.attrib.get('text', '') or '').lower()
            desc = (node.attrib.get('content-desc', '') or '').lower()

            if any(palavra in text or palavra in desc for palavra in palavras_chave):
                text_completo = node.attrib.get('text', '').strip()
                desc_completo = node.attrib.get('content-desc', '').strip()
                print(f"  TEXT: '{text_completo}' | DESC: '{desc_completo}'")

        print("="*60 + "\n")

    except Exception as e:
        print(f"Erro ao fazer dump relevante: {e}\n")

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

        # Log de debug após scroll
        try:
            xml = d.dump_hierarchy()
            root = ET.fromstring(xml)

            print(f"\n  [Após scroll {attempt + 1}] Elementos relevantes atuais:")
            palavras_chave = ['video', 'ganhar', 'assistir', 'card', 'recompensa', 'ir']
            count = 0
            for node in root.iter():
                text = (node.attrib.get('text', '') or '').lower()
                desc = (node.attrib.get('content-desc', '') or '').lower()

                if any(palavra in text or palavra in desc for palavra in palavras_chave):
                    text_completo = node.attrib.get('text', '').strip()
                    desc_completo = node.attrib.get('content-desc', '').strip()
                    if text_completo or desc_completo:
                        print(f"    TEXT: '{text_completo}' | DESC: '{desc_completo}'")
                        count += 1

            if count == 0:
                print(f"    (nenhum elemento relevante encontrado)")

        except Exception as e:
            print(f"  Erro ao fazer log após scroll: {e}")

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
    """Loop infinito: timer zerar → respiro 2s → encerrar vídeo → clicar 'Ganhar mais' → procurar próximo card → repete.
       Se ad sem timer, fecha e procura próximo card."""
    videos_assistidos = 0

    while True:
        videos_assistidos += 1
        print(f"\n{'='*60}")
        print(f"Aguardando fim do timer do vídeo {videos_assistidos}...")
        print(f"{'='*60}")

        # Passo 1: aguarda o timer chegar a 0
        timer_resultado = _aguardar_timer_acabar(max_espera_por_video)

        if timer_resultado is None:
            # AD foi detectado e fechado - procura próximo card
            print("\n" + "="*60)
            print("Procurando próximo card de vídeos (após fechar AD)...")
            print("="*60)
            try:
                clicar_assista_videos()
                print("✅ Próximo card encontrado após fechar AD!")
            except RuntimeError as e:
                print(f"⚠️  Não conseguiu encontrar o card: {e}")
                print("Tentando novamente em 3s...")
                time.sleep(3)
                try:
                    clicar_assista_videos()
                    print("✅ Segunda tentativa bem-sucedida!")
                except RuntimeError:
                    print("❌ Falha crítica. Tentando de novo em 5s...")
                    time.sleep(5)
                    continue
            continue

        if timer_resultado is False:
            # Ad sem timer detectável - encerra e procura próximo
            print("⚠️  Ad sem timer detectável. Encerrando e procurando próximo vídeo...")
            _encerrar_video(timeout=2)
            time.sleep(2)

            print(f"\n{'='*60}")
            print("Procurando próximo card de vídeos (após ad invisível)...")
            print(f"{'='*60}")
            try:
                clicar_assista_videos()
                print("✅ Próximo card encontrado e clicado!")
            except RuntimeError as e:
                print(f"⚠️  Não conseguiu encontrar o card: {e}")
                print("Tentando novamente em 3s...")
                time.sleep(3)
                try:
                    clicar_assista_videos()
                    print("✅ Segunda tentativa bem-sucedida!")
                except RuntimeError:
                    print("❌ Falha ao procurar o card após ad invisível. Tentando de novo em 5s...")
                    time.sleep(5)
                    continue
            continue

        print(f"✅ Vídeo #{videos_assistidos} finalizado!")

        # Passo 2: respiro de 2 segundos apenas
        print("Aguardando 2 segundos...")
        time.sleep(2)

        # Passo 3: tenta encerrar o vídeo IMEDIATAMENTE
        print("Encerrando vídeo agora...")
        _encerrar_video(timeout=2)

        # Passo 4: procura por "Ganhar mais" e clica
        if _procurar_clicar_ganhar_mais_com_retry():
            print(f"✅ 'Ganhar mais' clicado! Aguardando transição...")
            time.sleep(4)

            # Passo 5: procura pelo próximo card de vídeos
            print(f"\n{'='*60}")
            print("Procurando próximo card de vídeos...")
            print(f"{'='*60}")
            try:
                clicar_assista_videos()
                print("✅ Próximo card encontrado e clicado!")
            except RuntimeError as e:
                print(f"⚠️  Não conseguiu encontrar o card: {e}")
                print("Tentando novamente em 3s...")
                time.sleep(3)
                try:
                    clicar_assista_videos()
                    print("✅ Segunda tentativa bem-sucedida!")
                except RuntimeError:
                    print("❌ Falha ao procurar o card duas vezes. Tentando de novo em 5s...")
                    time.sleep(5)
                    continue
        else:
            print("⚠️  Não conseguiu processar a tela (sem 'Ganhar mais'). Tentando procurar o card novamente...")
            time.sleep(3)
            try:
                clicar_assista_videos()
                print("✅ Card encontrado mesmo sem 'Ganhar mais'!")
            except RuntimeError as e:
                print(f"❌ Falha crítica: {e}. Tentando de novo em 5s...")
                time.sleep(5)
                continue


def _log_tela_video(label=""):
    """Faz dump de todos os elementos visíveis durante o vídeo para debug."""
    try:
        xml = d.dump_hierarchy()
        root = ET.fromstring(xml)

        if label:
            print(f"\n🎬 {label}")
        print("="*60)
        print("ELEMENTOS NA TELA DO VÍDEO:")
        print("="*60)

        elementos = []
        for node in root.iter():
            text = node.attrib.get('text', '').strip()
            desc = node.attrib.get('content-desc', '').strip()

            if text or desc:
                elementos.append((text, desc))

        # Remove duplicatas mantendo ordem
        elementos_unicos = []
        vistos = set()
        for text, desc in elementos:
            chave = (text, desc)
            if chave not in vistos:
                vistos.add(chave)
                elementos_unicos.append((text, desc))

        for text, desc in elementos_unicos[:30]:  # Limita a 30 elementos
            if text:
                print(f"  TEXT: '{text}'")
            if desc:
                print(f"  DESC: '{desc}'")

        if len(elementos_unicos) > 30:
            print(f"  ... e mais {len(elementos_unicos) - 30} elementos")

        print("="*60 + "\n")

    except Exception as e:
        print(f"Erro ao fazer log da tela: {e}\n")


def _detectar_e_fechar_ad():
    """Detecta se é um ad e tenta fechá-lo (clicando na flechinha ou botão Sair)."""
    try:
        xml = d.dump_hierarchy()
        root = ET.fromstring(xml)

        # Procura por texto "AD" na tela
        eh_ad = False
        for node in root.iter():
            text = node.attrib.get('text', '').strip()
            if text.upper() == 'AD':
                eh_ad = True
                print("🎬 Detectado AD! Tentando fechar...")
                _log_tela_video("AD DETECTADO")
                break

        if not eh_ad:
            return False

        # Tenta clicar na flechinha de voltar (geralmente ao lado de "AD")
        print("Tentando clicar na flechinha de voltar do AD...")
        # Procura por botões com ícone de voltar próximos
        for sel in [
            {'description': 'voltar'},
            {'description': 'back'},
            {'descriptionMatches': r'(?i).*volta.*'},
            {'descriptionMatches': r'(?i).*back.*'},
        ]:
            elem = d(**sel)
            if elem.exists:
                try:
                    _clicar_elemento(elem)
                    print("✅ Flechinha de voltar clicada!")
                    time.sleep(2)
                    return True
                except Exception as e:
                    print(f"Erro ao clicar na flechinha: {e}")

        # Se não conseguiu clicar na flechinha, pressiona voltar do sistema
        print("Flechinha não encontrada. Pressionando voltar do sistema...")
        subprocess.run(["adb", "-s", DEVICE_ID, "shell", "input", "keyevent", "4"], check=True)
        time.sleep(2)

        # Procura por botão "Sair" que aparece após pressionar voltar
        print("Procurando por botão 'Sair'...")
        for tentativa in range(4):
            for sel in [
                {'text': 'Sair'},
                {'textMatches': r'(?i).*sair.*'},
                {'descriptionContains': 'Sair'},
            ]:
                elem = d(**sel)
                if elem.exists:
                    print("✅ Botão 'Sair' encontrado! Clicando...")
                    try:
                        _clicar_elemento(elem)
                        print("✅ AD fechado com sucesso!")
                        _log_tela_video("AD FECHADO")
                        return True
                    except Exception as e:
                        print(f"Erro ao clicar em Sair: {e}")
                        return False

            if tentativa < 3:
                print(f"  'Sair' não encontrado. Tentando novamente... ({tentativa + 1}/4)")
                time.sleep(1)

        print("❌ Não conseguiu fechar o AD")
        _log_tela_video("FALHA AO FECHAR AD")
        return False

    except Exception as e:
        print(f"Erro ao detectar/fechar AD: {e}")
        return False


def _aguardar_timer_acabar(max_espera):
    """Lê o timer do vídeo em dois formatos:
       1. Padrão: '15s Seja recompensado após'
       2. Com KWAI golds: '15 segundos | 150 Kwai golds a receber/...'

       Se passar 25s sem detectar timer = é um ad sem timer visível.
       Nesse caso, retorna False para sair e tentar novamente."""
    inicio = time.time()
    ultimo_timer = None
    detectou_kwai_golds = False
    primeira_iteracao = True
    tempo_sem_timer = 0
    TIMEOUT_SEM_TIMER = 25  # 25 segundos sem timer = ad invisível

    while time.time() - inicio < max_espera:
        try:
            xml = d.dump_hierarchy()
            root = ET.fromstring(xml)

            timer_agora = None

            # Padrão 1: "15s Seja recompensado após"
            for node in root.iter():
                text = node.attrib.get('text', '').strip()
                match = re.search(r'(\d+)s\s+Seja recompensado', text)
                if match:
                    timer_agora = int(match.group(1))
                    detectou_kwai_golds = False
                    break

            # Padrão 2: "15 segundos | 150 Kwai golds a receber/..." (com variações)
            if timer_agora is None:
                for node in root.iter():
                    text = node.attrib.get('text', '').strip()
                    # Procura por: "15 segundos" seguido de "|" e "Kwai golds"
                    match = re.search(r'(\d+)\s+segundos\s*\|\s*\d+\s+kwai\s+golds', text, re.IGNORECASE)
                    if match:
                        timer_agora = int(match.group(1))
                        detectou_kwai_golds = True
                        break

            # Padrão 3: "7s | Ganhe 198 Kwai Golds" (ad com timer curto)
            if timer_agora is None:
                for node in root.iter():
                    text = node.attrib.get('text', '').strip()
                    # Procura por: "7s | Ganhe XXX Kwai Golds"
                    match = re.search(r'(\d+)s\s*\|\s*Ganhe\s+\d+\s+kwai\s+golds', text, re.IGNORECASE)
                    if match:
                        timer_agora = int(match.group(1))
                        detectou_kwai_golds = True
                        break

            # Log inicial mostrando a tela do vídeo
            if primeira_iteracao and timer_agora is not None:
                _log_tela_video("PRIMEIRA DETECÇÃO DO VÍDEO")
                primeira_iteracao = False
                tempo_sem_timer = 0

            if timer_agora is not None:
                tempo_sem_timer = 0  # Reseta contador quando encontra timer
                if ultimo_timer != timer_agora:
                    tipo = "(KWAI golds)" if detectou_kwai_golds else "(padrão)"
                    print(f"⏱️  Timer: {timer_agora}s {tipo}")
                    ultimo_timer = timer_agora

                if timer_agora == 0:
                    print("⏱️  Timer zerou! Vídeo acabou.")
                    _log_tela_video("APÓS TIMER ZERAR")
                    return True
            else:
                # Timer não encontrado
                if ultimo_timer is not None:
                    # Timer desapareceu - significa que acabou
                    print("⏱️  Timer desapareceu - Vídeo finalizado!")
                    _log_tela_video("TIMER DESAPARECEU")
                    return True
                else:
                    # Ainda não encontrou timer uma única vez
                    tempo_sem_timer = time.time() - inicio
                    if tempo_sem_timer >= TIMEOUT_SEM_TIMER:
                        print(f"⚠️  Passou {TIMEOUT_SEM_TIMER}s sem detectar timer")
                        # Tenta fechar como AD
                        if _detectar_e_fechar_ad():
                            print("✅ AD detectado e fechado! Voltando ao loop...")
                            return None  # Sinal para tentar procurar novo card
                        else:
                            print("Encerrando este vídeo e tentando o próximo...")
                            _log_tela_video("AD SEM TIMER - ENCERRANDO")
                            return False

        except Exception as e:
            print(f"Erro ao ler timer: {e}")

        time.sleep(2)

    print(f"Timeout de {max_espera}s aguardando timer")
    return False


def _encerrar_video(timeout=2):
    """Encerra o vídeo imediatamente pressionando voltar uma única vez."""
    try:
        print("Pressionando voltar para encerrar vídeo...")
        _log_tela_video("ANTES DE ENCERRAR")

        # Pressiona voltar uma única vez (keyevent 4 = BACK)
        subprocess.run(["adb", "-s", DEVICE_ID, "shell", "input", "keyevent", "4"], check=True)
        print("✅ Voltar pressionado")
        time.sleep(1)

        _log_tela_video("APÓS ENCERRAR")
        return True
    except Exception as e:
        print(f"❌ Erro ao encerrar vídeo: {e}")
        _log_tela_video("ERRO AO ENCERRAR")
        return False


def _procurar_clicar_ganhar_mais_com_retry(timeout=6):
    """Procura por 'Ganhar mais' ou 'Sair' e clica em 'Ganhar mais'. Tenta continuamente."""
    print("Procurando por 'Ganhar mais'...")

    # Primeira tentativa: procura por até 6s
    if _procurar_e_clicar_ganhar_mais(timeout):
        return True

    print(f"'Ganhar mais' não encontrado após {timeout}s")
    return False


def _clicar_ganhar_mais(timeout=20):
    """Aguarda 'Ganhar mais' até 20s. Se não aparecer, pressiona voltar e tenta novamente."""
    print("Procurando por 'Ganhar mais'...")

    # Primeira tentativa: procura por até 20s
    if _procurar_e_clicar_ganhar_mais(timeout):
        return True

    # Se não encontrou, tenta pressionar voltar
    print("'Ganhar mais' não encontrado após 20s. Tentando pressionar voltar...")
    subprocess.run(["adb", "-s", DEVICE_ID, "shell", "input", "keyevent", "4"])  # 4 = BACK
    time.sleep(3)

    # Tenta novamente após voltar
    print("Procurando 'Ganhar mais' novamente após voltar...")
    if _procurar_e_clicar_ganhar_mais(timeout=5):
        return True

    print("'Ganhar mais' não encontrado mesmo após voltar. Encerrando.")
    return False


def _procurar_e_clicar_ganhar_mais(timeout):
    """Procura por 'Ganhar mais' E 'Sair' juntos (modal), e clica APENAS em 'Ganhar mais' quando ambos estão visíveis."""
    inicio = time.time()
    primeira_iteracao = True

    while time.time() - inicio < timeout:
        # Log inicial mostrando a tela
        if primeira_iteracao:
            _log_tela_video("PROCURANDO POR 'GANHAR MAIS'")
            primeira_iteracao = False

        # Verifica se AMBOS "Ganhar mais" E "Sair" estão visíveis (indicando a tela modal correta)
        ganhar_mais_elem = None
        sair_elem = None

        for sel in [
            {'text': 'Ganhar mais'},
            {'textMatches': r'(?i).*ganhar mais.*'},
            {'descriptionContains': 'Ganhar mais'},
            {'textContains': 'Ganhar mais'},
        ]:
            elem = d(**sel)
            if elem.exists:
                ganhar_mais_elem = elem
                break

        for sel in [
            {'text': 'Sair'},
            {'textMatches': r'(?i).*sair.*'},
            {'descriptionContains': 'Sair'},
            {'textContains': 'Sair'},
        ]:
            elem = d(**sel)
            if elem.exists:
                sair_elem = elem
                break

        # Se AMBOS foram encontrados, clica em "Ganhar mais"
        if ganhar_mais_elem and sair_elem:
            print("✅ 'Ganhar mais' E 'Sair' encontrados juntos! Modal confirmada. Clicando em 'Ganhar mais'...")
            try:
                info = ganhar_mais_elem.info
                bounds = info.get('bounds') or info.get('visibleBounds', {})
                if bounds and all(k in bounds for k in ('left', 'top', 'right', 'bottom')):
                    x = (bounds['left'] + bounds['right']) // 2
                    y = (bounds['top'] + bounds['bottom']) // 2
                    subprocess.run(["adb", "-s", DEVICE_ID, "shell", "input", "tap", str(x), str(y)], check=True)
                    time.sleep(2)
                    return True
            except Exception as e:
                print(f"❌ Erro ao tocar 'Ganhar mais': {e}")
                _log_tela_video("ERRO AO CLICAR EM 'GANHAR MAIS'")
                return False
        elif ganhar_mais_elem and not sair_elem:
            print("⚠️  Encontrado 'Ganhar mais' mas SEM 'Sair' (pode ser 'Ganhar agora' da tela anterior). Ignorando...")
        elif sair_elem and not ganhar_mais_elem:
            print("⚠️  Encontrado 'Sair' mas SEM 'Ganhar mais'. Aguardando modal completa...")

        time.sleep(5)

    print(f"❌ Timeout de {timeout}s: não foi encontrada a tela modal com 'Ganhar mais' e 'Sair' juntos")
    _log_tela_video("TIMEOUT - NÃO ENCONTROU 'GANHAR MAIS' COM 'SAIR'")
    return False


if __name__ == "__main__":
    conectar_dispositivo()
    abrir_kwai()
    entrar_perfil()
    clicar_menu_tres_pontos()
    clicar_ganhar_dinheiro()

    # Tenta encontrar o card com retry
    max_tentativas = 3
    for tentativa in range(1, max_tentativas + 1):
        try:
            print(f"\n{'='*60}")
            print(f"Tentativa {tentativa}/{max_tentativas} de encontrar o card...")
            print(f"{'='*60}")
            clicar_assista_videos()
            print("✅ Card encontrado com sucesso!")
            break
        except RuntimeError as e:
            if tentativa < max_tentativas:
                print(f"❌ Falha na tentativa {tentativa}: {e}")
                print(f"Aguardando 3s antes de tentar novamente...")
                time.sleep(3)
            else:
                print(f"❌ Falha em todas as {max_tentativas} tentativas. Encerrando.")
                raise

    # Inicia o loop de assistir vídeos
    aguardar_e_fechar_video()
