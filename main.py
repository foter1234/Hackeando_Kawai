import uiautomator2 as u2
import time
import random

DEVICE_ID = "ZF525J6NKX"
KWAI_PACKAGE = "com.kwai.video"

d = u2.connect(DEVICE_ID)


def abrir_kwai():
    d.app_start(KWAI_PACKAGE)
    time.sleep(5)


def assistir_videos(quantidade=50):
    """Fica na aba For You assistindo vídeos para ganhar gold."""
    print(f"Iniciando automação — assistindo {quantidade} vídeos...")

    for i in range(quantidade):
        tempo = random.uniform(15, 30)
        print(f"Vídeo {i+1}/{quantidade} — assistindo por {tempo:.0f}s")
        time.sleep(tempo)

        # Swipe para o próximo vídeo
        d.swipe(540, 1400, 540, 400, duration=0.3)
        time.sleep(random.uniform(1, 2))

    print("Sessão finalizada.")


def curtir_video():
    """Tenta curtir o vídeo atual."""
    try:
        d.double_click(540, 900)
        time.sleep(1)
    except Exception:
        pass


def assistir_e_curtir(quantidade=50, curtir_a_cada=5):
    """Assiste vídeos e curte de tempos em tempos."""
    print(f"Iniciando — {quantidade} vídeos, curtindo 1 a cada {curtir_a_cada}...")

    abrir_kwai()

    for i in range(quantidade):
        tempo = random.uniform(15, 30)
        print(f"Vídeo {i+1}/{quantidade} — {tempo:.0f}s")

        if (i + 1) % curtir_a_cada == 0:
            curtir_video()
            print("  ❤ curtido")

        time.sleep(tempo)
        d.swipe(540, 1400, 540, 400, duration=0.3)
        time.sleep(random.uniform(1, 3))

    print("Sessão finalizada.")


if __name__ == "__main__":
    abrir_kwai()
    assistir_e_curtir(quantidade=50, curtir_a_cada=5)
