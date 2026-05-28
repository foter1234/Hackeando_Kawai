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


def ler_timer():
    """Lê o timer da tela e retorna o número."""
    d = conectar()

    print("Começando a ler o timer...")
    print("Deixe o vídeo tocando e vou imprimir o timer a cada 2 segundos\n")

    time.sleep(3)

    while True:
        xml = d.dump_hierarchy()
        root = ET.fromstring(xml)

        # Procura por números (0-60) que aparecem na tela
        timers_encontrados = []
        for node in root.iter():
            text = node.attrib.get('text', '').strip()

            # Verifica se é um número simples (timer)
            if text.isdigit() and 0 <= int(text) <= 60:
                bounds_str = node.attrib.get('bounds', '')
                timers_encontrados.append({
                    'text': text,
                    'bounds': bounds_str
                })

        if timers_encontrados:
            # Pega o primeiro que encontrou (geralmente é o timer)
            timer_valor = timers_encontrados[0]['text']
            print(f"⏱️  Timer: {timer_valor}s")
        else:
            print("⏱️  Timer: não detectado (pode ter acabado)")

        time.sleep(2)


if __name__ == "__main__":
    ler_timer()
