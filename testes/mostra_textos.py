import uiautomator2 as u2
import time
import subprocess
import xml.etree.ElementTree as ET

DEVICE_ID = "ZF525J6NKX"


def conectar():
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    if DEVICE_ID not in result.stdout:
        raise RuntimeError("Dispositivo não encontrado")
    return u2.connect(DEVICE_ID)


if __name__ == "__main__":
    d = conectar()

    print("Enquanto o vídeo está tocando, imprimo todos os textos da tela...\n")
    time.sleep(2)

    for i in range(10):
        print(f"\n--- Leitura {i+1} ---")
        xml = d.dump_hierarchy()
        root = ET.fromstring(xml)

        textos = set()
        for node in root.iter():
            text = node.attrib.get('text', '').strip()
            if text and len(text) > 0:
                textos.add(text)

        if textos:
            for txt in sorted(textos):
                print(f"  • {txt}")
        else:
            print("  (nenhum texto encontrado)")

        time.sleep(2)
