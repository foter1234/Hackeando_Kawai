# Hackeando Kwai

Automação Python para mineração de Kwai Gold via ADB no Android real.

## Requisitos

- Python 3.10+
- Celular Android com **Depuração USB** ativada
- Kwai instalado e logado no celular
- Cabo USB

## Instalação

```bash
pip install uiautomator2
python -m uiautomator2 init
```

## Como usar

1. Conecte o celular via USB e confirme a permissão de depuração
2. Verifique se o dispositivo aparece:
   ```bash
   adb devices
   ```
3. Copie o ID do dispositivo e cole em `DEVICE_ID` no `main.py`
4. Execute:
   ```bash
   python main.py
   ```

## Como funciona

O script conecta ao celular via ADB, abre o Kwai e simula uso humano: assiste vídeos por tempo aleatório (15–30s) e curte a cada 5 vídeos com double-tap. Tempos aleatórios evitam detecção de bot.

## Ajustes principais (`main.py`)

| Parâmetro | Descrição |
|---|---|
| `quantidade` | Número de vídeos por sessão |
| `curtir_a_cada` | Curte 1 vídeo a cada N |
