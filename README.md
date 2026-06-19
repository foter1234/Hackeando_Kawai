# Kwai Farm

Automação Python que controla um Android real via ADB para assistir vídeos no Kwai e acumular Kwai Golds de forma contínua. O bot opera como um **agente autônomo** — ele percebe o estado da tela, decide qual ação tomar e age, registrando cada decisão para estudo posterior.

---

## Como funciona em alto nível

O fluxo que o bot executa é exatamente o que um humano faria:

```
Abrir Kwai
  → Aba Perfil (rodapé)
    → Menu ⋯ (canto superior direito)
      → "Ganhar dinheiro"
        → Card "Assista a vídeos para ganhar até X Kwai Golds"
          → Assistir o vídeo inteiro (lê o timer até zerar)
            → Esperar 5–10s
              → Voltar
                → Se aparecer modal "Ganhar mais": clicar e continuar
                → Se voltar direto: clicar no card novamente
                  → repetir para sempre
```

Quando o algoritmo do Kwai começa a pagar pouco (shadow limit), o bot detecta a queda, tenta outros cards de recompensa disponíveis, scrolla o feed organicamente e entra em cooldown antes de retomar.

---

## Requisitos

- Python 3.10+
- Android com **Depuração USB** ativada
- Kwai instalado e com conta logada
- Cabo USB
- ADB instalado no sistema

```bash
# verificar se ADB está disponível
adb version
```

---

## Instalação

```bash
git clone https://github.com/seu-usuario/Hackeando_Kawai
cd Hackeando_Kawai

python3 -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate           # Windows

pip install uiautomator2
python3 -m uiautomator2 init      # instala o agente UIAutomator no celular
```

---

## Como usar

1. Conecte o celular via USB
2. Confirme a autorização RSA no celular (aparece uma janela de diálogo)
3. Execute:

```bash
source venv/bin/activate
python3 farm.py
```

Se houver mais de um dispositivo conectado, o bot lista e pede para escolher. Se houver apenas um, conecta automaticamente.

Os logs ficam em `logs/` — um arquivo `.log`, uma pasta `dumps_*/` com os XMLs da UI e um `relatorio_*.md` com o histórico de decisões de cada execução.

---

## Parâmetros de configuração (`farm.py`, topo do arquivo)

| Constante | Padrão | Descrição |
|---|---|---|
| `ESPERA_POS_TIMER` | `(5, 10)` | Segundos de espera após o timer zerar, antes de apertar Voltar |
| `MAX_ESPERA_VIDEO` | `180` | Teto de segurança por vídeo em segundos |
| `TIMEOUT_SEM_TIMER` | `25` | Segundos sem detectar timer → trata como anúncio sem timer |
| `INTERVALO_LEITURA_TIMER` | `1.5` | Intervalo entre leituras do timer (segundos) |
| `GOLD_BAIXO_THRESHOLD` | `100` | Gold por vídeo abaixo disso conta como "pagando pouco" |
| `STREAK_RUIM_PARA_COOLDOWN` | `3` | Quantos vídeos ruins consecutivos disparam o cooldown |
| `COOLDOWN_SEG` | `(300, 720)` | Faixa de pausa do cooldown (5–12 minutos, aleatório) |

---

## Arquitetura do código

O bot segue o ciclo **PERCEBER → DECIDIR → AGIR** a cada passo, nunca tomando decisões com base em estado presumido — sempre lê a tela antes de agir.

### 1. Logging (`_Tee`, `iniciar_logging`, `relatorio`, `_salvar_xml`)

Toda saída é duplicada: vai para o console **e** para um arquivo `.log` simultâneamente via a classe `_Tee` (que implementa `write` e `flush` para múltiplos streams).

A cada execução são criados:
- `logs/farm_YYYYMMDD_HHMMSS.log` — tudo que o bot imprimiu
- `logs/dumps_YYYYMMDD_HHMMSS/` — XMLs numerados da hierarquia de UI, salvos nos momentos importantes (não durante o loop do timer, para não gerar centenas de arquivos)
- `logs/relatorio_YYYYMMDD_HHMMSS.md` — relatório markdown de cada decisão tomada, com timestamp, para revisar o desempenho

---

### 2. Percepção — `Elemento`, `Tela`, `capturar_tela`

**`Elemento`**: representa um nó da árvore de UI do Android. Armazena texto, content-desc, resource-id, classe, package, se é clicável/scrollable e os bounds (retângulo na tela). O centro `(cx, cy)` é calculado automaticamente dos bounds.

**`Tela`**: snapshot imutável com todos os elementos visíveis. Oferece métodos de consulta:
- `com_texto()` — elementos com texto ou content-desc
- `por_regex(pattern)` — busca por expressão regular no conteúdo
- `por_texto_exato(*opcoes)` — match exato normalizado (ignora maiúsculas/minúsculas e espaços extras)
- `contendo(termo)` — substring case-insensitive
- `por_rid_contendo(*tokens)` — elementos cujo resource-id contém os tokens
- `clicavel_que_contem(elem)` — acha o menor container clicável que envolve um elemento não-clicável (resolve o caso clássico onde o texto do card não é clicável mas o card em si é)

**`capturar_tela(motivo)`**: chama `d.dump_hierarchy()` via uiautomator2, parseia o XML com `xml.etree.ElementTree`, constrói a lista de `Elemento` e retorna uma `Tela`. Salva o XML na pasta de dumps (exceto nas leituras de alta frequência do timer, onde `salvar=False` para não poluir o log).

---

### 3. Ações (`clicar_ponto`, `clicar_alvo`, `voltar`, `rolar_para_baixo`)

**`clicar_ponto(x, y, motivo)`**: clica em coordenadas absolutas via `d.click()`. Loga no console e no relatório.

**`clicar_alvo(tela, elem, motivo)`**: versão inteligente — se o elemento não é clicável (`clickable=False`), busca o menor container clicável que o envolve e clica nele. Resolve o caso frequente no Kwai onde o texto do card não é clicável diretamente.

**`voltar(motivo)`**: pressiona BACK via `d.press("back")`. Fallback via `adb shell input keyevent 4` se o uiautomator2 falhar.

**`rolar_para_baixo()`**: swipe de 72% para 35% da altura da tela, no centro horizontal — equivale a um scroll humano.

---

### 4. Popups e anúncios (`tratar_popups`, `_achar_fechar_popup`, `_eh_tela_recompensa_ad`)

**`tratar_popups()`**: roda até 3 rodadas de detecção. A cada rodada captura a tela e decide:
1. Se tem "Ganhar mais" → é a modal de recompensa do fluxo principal, **não fecha**
2. Se é a tela de recompensa-AD → chama `_dispensar_tela_recompensa_ad`
3. Se tem botão de fechar → fecha

**`_achar_fechar_popup(tela)`**: busca affordâncias de fechar com confiança decrescente:
1. `resource-id` contendo `close`, `dismiss`, `btn_close` etc. (mais confiável)
2. `content-desc` de fechar
3. Glifos × ✕ ✖ ╳
4. Textos como "Pular", "Agora não", "Fechar", "Não obrigado" (menos confiável)

**`_eh_tela_recompensa_ad(tela)`**: detecta a tela pós-anúncio pelo padrão: tem "Sair" **E** algum de ("Kwai Golds obtidas", "Assista mais um para ganhar", "Kwai Golds a receber"), **sem** "Ganhar mais". Essa tela tem todos os elementos com `clickable=False`, então os taps usam coordenada direta.

**`_dispensar_tela_recompensa_ad(tela)`**: clica em "Sair" por coordenada. **Não** clica em "Receba X Kwai Golds agora" — esse botão abre o Google Play Store, saindo do fluxo. O gold já é creditado automaticamente ao término do timer.

---

### 5. Recuperação de app (`_estamos_no_kwai`, `retornar_ao_kwai`)

**`_estamos_no_kwai()`**: consulta `adb shell dumpsys window windows` e verifica se `com.kwai.video` está no foco (`mCurrentFocus` / `mFocusedApp`). Anúncios podem abrir o browser ou Play Store — essa verificação detecta isso.

**`retornar_ao_kwai()`**: se não está no Kwai, pressiona BACK até 6 vezes esperando o Kwai voltar. Se não voltar, força `app_start` como último recurso.

---

### 6. Navegação inicial

**`conectar_dispositivo()`**: lista dispositivos via `adb devices`. Se houver um, conecta automaticamente. Se houver mais, exibe menu de escolha. Inicializa a instância global `d` (uiautomator2).

**`abrir_kwai()`**: para o app (`app_stop`) e reabre (`app_start`). O cold start garante que o Kwai sempre abre no feed — não numa tela de busca ou detalhe de vídeo de sessão anterior.

**`ir_para_perfil()`**: localiza a aba "Perfil" na barra inferior pelo resource-id que termina com `tab_me` ou `me_button`. Fallback por texto ("Perfil", "Eu", "Me") na parte inferior da tela. Confirma que está no perfil procurando por "Editar perfil", "Meus vídeos" ou "Seguidores".

**`abrir_menu_3pontos()`**: localiza o botão de menu (⋯) pelo resource-id que termina com `more_btn`, `_more` ou `btn_more`. Fallback por content-desc ("menu", "mais opções"). Último fallback: o elemento clicável mais à direita no topo da tela.

**`clicar_ganhar_dinheiro()`**: busca o item "Ganhar dinheiro" no menu por regex (descartando convites de amigos que têm texto parecido). Fallback por resource-id contendo `earn_coin`, `earn`, `coin`, `wallet`, `gold`.

---

### 7. Card de vídeos (`achar_card`, `achar_ir_do_card`, `iniciar_video_pelo_card`)

**`achar_card(tela)`**: identifica o card "Assista a vídeos para ganhar até X Kwai Golds" com três condições simultâneas:
- Tem `assist*` + `vídeo` + `ganh*`
- Tem `até` OU `kwai gold`
- **Não** tem `amig`, `chame`, `convid`, `curt` (descarta convites e "curtir vídeo")

Retorna o elemento de menor área (o rótulo do texto, mais específico que o container).

**`achar_ir_do_card(tela, card)`**: dos vários botões "Ir" que podem existir na tela (um por card), escolhe o que pertence ao card correto. Lógica geométrica:
1. Só considera "Ir" à **direita** do card
2. Prioriza os que têm sobreposição vertical com o card (mesma linha)
3. Fallback: os mais próximos verticalmente
4. Desempate: mais próximo horizontalmente

**`iniciar_video_pelo_card()`**: tenta iniciar o vídeo em três níveis:
1. Clica no card diretamente (via `clicar_alvo` — container clicável)
2. Se o clique não funcionou (card ainda visível, sem timer): clica no botão "Ir" à direita
3. Fallback geométrico: clica na lateral direita do card pela posição calculada

Confirma que o vídeo iniciou detectando o timer ou percebendo que o card sumiu da tela.

---

### 8. Timer do vídeo (`_extrair_segundos`, `ler_timer`, `assistir_ate_timer_acabar`)

**`_extrair_segundos(texto)`**: extrai segundos de texto. Aceita:
- `"15s"`, `"15 segundos"` — formato com unidade
- `"1:30"` — formato mm:ss
- Rejeita número solto (`"15"`) para evitar falso positivo com relógio do sistema ou contadores de recompensa

**`ler_timer(tela)`**: restringe a busca à faixa entre 60px (abaixo da status bar) e 30% da altura da tela (onde o timer do Kwai fica). Ignora elementos do `com.android.systemui`. Entre os candidatos, prefere o mais à direita da tela.

**`assistir_ate_timer_acabar()`**: loop de leitura a cada 1,5s com três condições de saída:
- Timer chegou a 0 → `return True`
- Timer estava presente e sumiu → `return True` (vídeo terminou)
- 25s sem ver nenhum timer → `return False` (provável anúncio sem timer — volta e pula)
- Teto de 180s atingido → `return False`

---

### 9. Pós-vídeo (`lidar_pos_video`)

Após o timer zerar, espera 5–10s aleatórios e aperta Voltar. Verifica o que apareceu:

| Situação detectada | Ação |
|---|---|
| Tela de recompensa-AD (`Sair` + `Kwai Golds obtidas`) | Clica "Sair" por coordenada (clickable=False) |
| Modal `Ganhar mais` + `Sair` | Clica "Ganhar mais" para iniciar o próximo vídeo automaticamente |
| Card de vídeos visível | Não faz nada — o loop recomeça e clica no card |
| Estado indefinido | Aguarda até 5 tentativas de 2s cada |

Em qualquer caso tenta extrair o gold ganho da tela antes de sair, para alimentar o rastreamento de rendimento.

---

### 10. Detecção de rendimento e cooldown anti-shadow

O Kwai tem um mecanismo de shadow limit: após muitos vídeos seguidos, reduz drasticamente o gold pago (pode cair para 1 gold por vídeo).

**`_extrair_gold_tela(tela)`**: faz parsing do gold na tela pós-vídeo. Procura padrões como `+150 Kwai Golds`, `Kwai Golds obtidas`, `ganhou 150` nos elementos visíveis.

**`_registrar_gold(gold, n_video)`**: adiciona o valor ao histórico (mantém os últimos 20). Se o gold está abaixo de `GOLD_BAIXO_THRESHOLD` (100), incrementa `_streak_ruim`. Se não, zera o streak. Calcula e loga a média dos últimos 5 vídeos. Retorna `True` se o streak atingiu `STREAK_RUIM_PARA_COOLDOWN` (3 ruins consecutivos).

**`executar_cooldown()`**: sequência completa de recuperação:

```
1. _voltar_para_ganhar_dinheiro()   → pressiona BACK inteligentemente até ver o card list
2. _explorar_outras_atividades()    → procura outros cards (check-in, tarefas, missões, bônus)
3. _scroll_feed_organico(N segundos)→ abre o feed e scrolla com timing humano (3–8s por vídeo)
4. time.sleep(restante)             → stand-by para o algoritmo "esfriar"
5. abrir_kwai() → ir_para_perfil()  → retoma o fluxo do zero
   → abrir_menu_3pontos()
   → clicar_ganhar_dinheiro()
```

O tempo total de pausa é aleatório entre 5 e 12 minutos. Um terço desse tempo é gasto scrollando o feed (máximo 2 minutos).

**`_explorar_outras_atividades()`**: rola a tela de "Ganhar dinheiro" procurando cards que não sejam de assistir vídeos, mas que ainda ofereçam gold: check-in diário, tarefas, missões, bônus, ao vivo etc. Descarta cards de convite de amigos. Clica no que encontrar, volta e registra no relatório.

---

### 11. Loop principal (`loop_assistir_videos`)

```
enquanto True:
    n += 1
    retornar_ao_kwai()         # garante que estamos no Kwai
    tratar_popups()            # fecha qualquer popup aberto
    tela = capturar_tela()

    se não há timer rodando:
        iniciar_video_pelo_card()   # navega até o vídeo

    terminou = assistir_ate_timer_acabar()

    se terminou == False:      # anúncio sem timer
        voltar()
        tratar_popups()
        continuar

    esperar_pos_timer()        # 5–10s aleatórios
    gold = lidar_pos_video()   # trata modal, extrai gold

    se gold detectado:
        _registrar_gold(gold, n)
        se streak ruim >= 3:
            executar_cooldown()    # pausa + outras atividades + retoma
```

---

## Estrutura de arquivos

```
Hackeando_Kawai/
├── farm.py           # bot principal (este documento descreve)
├── logs/
│   ├── farm_YYYYMMDD_HHMMSS.log        # saída completa da execução
│   ├── relatorio_YYYYMMDD_HHMMSS.md    # decisões em markdown
│   └── dumps_YYYYMMDD_HHMMSS/
│       ├── 0001_antes_perfil.xml       # hierarquia de UI em momentos-chave
│       ├── 0002_apos_perfil.xml
│       └── ...
└── venv/             # ambiente virtual Python
```

---

## Decisões técnicas relevantes

**Por que ler a hierarquia de UI e não usar coordenadas fixas?**
Coordenadas fixas quebram em qualquer resolução diferente. O dump de UI do uiautomator2 devolve os bounds reais de cada elemento, então a lógica funciona em qualquer celular.

**Por que cold start no `abrir_kwai()`?**
`app_start` sem `stop=True` apenas retoma a última tela. Se o Kwai estava numa busca ou num vídeo detalhe, a navegação para "Ganhar dinheiro" falharia. O cold start (`app_stop` + `app_start`) garante estado previsível.

**Por que não clicar em "Receba X Kwai Golds agora" na tela de recompensa?**
Esse botão abre o Google Play Store ou um browser para instalar um anúncio, saindo completamente do fluxo do Kwai. O gold já é creditado automaticamente quando o timer termina — o botão é armadilha de anúncio.

**Por que o timer usa restrição de faixa vertical?**
A tela do Kwai tem vários números: o relógio do sistema no topo, contadores de curtidas, timers de "Expira em X dias". Restringir para a faixa entre 60px e 30% da altura (onde o timer do vídeo aparece) e exigir formato com unidade (`15s`, `1:30`) elimina todos os falsos positivos confirmados em dump real.

**Por que o cooldown inclui scroll orgânico?**
O shadow limit do Kwai parece ser baseado em padrão de uso — muitos vídeos consecutivos sem interação com o feed ativa o limite. Scrollar o feed simula uso humano e pode ajudar a resetar o contador interno.
