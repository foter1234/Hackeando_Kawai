import uiautomator2 as u2
import time
import subprocess
import xml.etree.ElementTree as ET

DEVICE_ID = "ZF525J6NKX"
KWAI_PACKAGE = "com.kwai.video"


def conectar():
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    if DEVICE_ID not in result.stdout:
        raise RuntimeError("Dispositivo não encontrado")
    d = u2.connect(DEVICE_ID)
    return d


def dump_completo(d):
    print("\n" + "="*80)
    print("DUMP COMPLETO DA TELA COM COORDENADAS")
    print("="*80 + "\n")

    xml = d.dump_hierarchy()
    root = ET.fromstring(xml)

    elementos = []
    for node in root.iter():
        text = node.attrib.get('text', '').strip()
        desc = node.attrib.get('content-desc', '').strip()
        bounds_str = node.attrib.get('bounds', '')
        resource_id = node.attrib.get('resource-id', '')
        class_name = node.attrib.get('class', '')
        clickable = node.attrib.get('clickable', 'false')

        if bounds_str:
            try:
                bounds = eval(bounds_str)
                left, top, right, bottom = bounds[0][0], bounds[0][1], bounds[1][0], bounds[1][1]
                center_x = (left + right) // 2
                center_y = (top + bottom) // 2

                # Armazena elemento com todas as infos
                elemento = {
                    'text': text,
                    'desc': desc,
                    'bounds': bounds_str,
                    'center': (center_x, center_y),
                    'left': left,
                    'top': top,
                    'right': right,
                    'bottom': bottom,
                    'resource_id': resource_id,
                    'class': class_name,
                    'clickable': clickable
                }
                elementos.append(elemento)

                # Printa elementos com texto ou descrição
                if text or desc:
                    print(f"[{center_x:4d}, {center_y:4d}] Clickable={clickable:5s}")
                    if text:
                        print(f"  Text: {text[:70]}")
                    if desc:
                        print(f"  Desc: {desc[:70]}")
                    print(f"  Bounds: ({left}, {top}) → ({right}, {bottom})")
                    if resource_id:
                        print(f"  ID: {resource_id}")
                    print()
            except Exception as e:
                pass

    print("\n" + "="*80)
    print("PROCURANDO POR 'kwai Golds recebidos'")
    print("="*80 + "\n")

    # Busca especificamente por "kwai Golds recebidos"
    encontrados = [e for e in elementos if 'golds' in e['text'].lower() or 'golds' in e['desc'].lower()]

    if encontrados:
        for e in encontrados:
            print(f"✓ ENCONTRADO: {e['text'] or e['desc']}")
            print(f"  Coordenadas centro: ({e['center'][0]}, {e['center'][1]})")
            print(f"  Bounds: ({e['left']}, {e['top']}) → ({e['right']}, {e['bottom']})")
            print(f"  Clickable: {e['clickable']}")
            print()
    else:
        print("✗ 'kwai Golds recebidos' NÃO ENCONTRADO NA TELA")
        print("\nElementos com 'Ganhar', 'recebido', 'prêmio':")
        keywords = ['ganhar', 'recebido', 'prêmio', 'recompensa', 'ir', 'ganhar mais', 'sair']
        for keyword in keywords:
            matches = [e for e in elementos if keyword.lower() in (e['text'].lower() + ' ' + e['desc'].lower())]
            if matches:
                print(f"\n  Contém '{keyword}':")
                for e in matches:
                    print(f"    [{e['center'][0]}, {e['center'][1]}] {e['text'] or e['desc']}")


if __name__ == "__main__":
    d = conectar()
    print("\n>>> App iniciando...")
    d.app_start(KWAI_PACKAGE)
    time.sleep(5)

    print("\n>>> Vá manualmente para a tela de 'kwai Golds recebidos' e pressione ENTER quando estiver lá...")
    input()

    dump_completo(d)
