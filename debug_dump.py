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
    print("Conectado.")
    return d


def dump_textos(d):
    print("\n=== DUMP DE TEXTOS NA TELA ===")
    xml = d.dump_hierarchy()
    root = ET.fromstring(xml)
    for node in root.iter():
        text = node.attrib.get('text', '').strip()
        desc = node.attrib.get('content-desc', '').strip()
        cls = node.attrib.get('class', '')
        if text or desc:
            print(f"  text={repr(text):40s}  desc={repr(desc):40s}  class={cls.split('.')[-1]}")
    print("=== FIM DO DUMP ===\n")


if __name__ == "__main__":
    d = conectar()

    # Roda o app e navega até Ganhar dinheiro
    d.app_start(KWAI_PACKAGE)
    time.sleep(5)

    # Vai para perfil
    for sel in [{'text': 'Perfil'}, {'text': 'Me'}, {'text': 'Profile'}]:
        if d(**sel).exists:
            d(**sel).click()
            time.sleep(4)
            break

    dump_textos(d)
    print(">>> Dump após perfil. Agora clique manualmente nos 3 pontinhos e depois em Ganhar dinheiro. Aguardando 15s...")
    time.sleep(15)

    dump_textos(d)
    print(">>> Dump após Ganhar dinheiro. Rolando para baixo...")

    width, height = d.window_size()
    for i in range(4):
        d.swipe(width // 2, int(height * 0.75), width // 2, int(height * 0.35), duration=0.5)
        time.sleep(2)
        print(f"--- Após scroll {i+1} ---")
        dump_textos(d)
