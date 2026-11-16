# 00-BIBLIA: o que o Jarvis é (fonte única)

Versão: 16/11/2026. Descreve o estado vigente deste repositório. Regra: se o código muda, muda primeiro o `01-DECISOES` e depois este arquivo, nas seções afetadas. Etiquetas: `[D-xxx]`, `[H-xx]`, `[proposta]`, `[levantado: data]`, `[relatado: fonte]` (ver `01-DECISOES.md`). **Aprovado pelo Lucas em 16/11/2026.**

As referências apontam para arquivos e nomes no código (funções, constantes), não para números de linha, que mudam a cada edição.

## 01. Propósito e escopo

**Propósito.** Assistente de voz pessoal no Mac: conversa em tempo real, age no computador, pesquisa, assiste e estuda, e guarda memória em arquivos Markdown que o Claude Code também lê. [D-001] [D-004]

**Escopo.** Uso individual, em um Mac. Fora do escopo: multiusuário, nuvem própria, distribuição do app, funcionamento 100% local (revertido em [D-003]).

**Princípios (invariantes).**
1. O Jarvis só afirma que fez algo se uma ferramenta rodou. [D-020a]
2. O que é destrutivo ou externo exige o sim do usuário. Nada é apagado de vez: `mac.py` move para a Lixeira. [D-010]
3. O cofre é a verdade; entre dois fatos vale o mais recente. O `busca.db` é só um índice descartável. [D-004] [D-015] [levantado: 16/11/2026, `busca.py`]
4. O trabalho longo não altera nada: entrega texto, plano ou prompt. [D-021] [levantado: 16/11/2026, `trabalho.py`]
5. Mudança no código só depois de `testes.py` passar. [relatado: memória do projeto, 11/11]
6. Texto que o usuário vai usar vai inteiro para a tela. [D-020b]

## 02. Usuários e experiência

**Usuário.** Uma pessoa, em português do Brasil, tratada pelo nome (`user_name` no `config.json`). [D-005]

**Experiência de voz.**
- Conversa pelo Gemini Live; o usuário pode interromper; modos de interrupção `normal`, `firme` e `nunca` (chave `interrupcao`). [D-001] [D-020g] [levantado: 16/11/2026, `realtime_input_config` em `server.py`]
- Duas palmas abrem o app e começam a conversa; o ponto laranja indica o microfone aberto. [D-006]
- F5 liga e desliga a escuta. Mudo solta o microfone, mas mantém a conversa e as tarefas. [D-009] [D-020d] · [H-01]
- Fala curta (uma a três frases); o que não couber vai por escrito com `mostrar_texto`. [D-020b] [levantado: 16/11/2026, `prompts/persona.pt-BR.md`]
- Quando uma tarefa longa termina com o microfone mudo, soa um aviso e o Dock pula. [relatado: relatório da noite de 13/11]

**Interface** [levantado: 16/11/2026, `static/`, `app/Jarvis.swift`].
- Tela inicial: reator central (roxo = executando, com a etapa escrita embaixo [D-020c]), widgets (clima, agenda, pendências, projeto, atividade, Notas) e gaveta de conversa, com estética de vidro, para ser leve, parecida com o macOS e editável na própria tela. [C-01]
- **Agenda**: calendário do Jarvis, editado por voz e revisado em conversa toda noite, com arrastar tarefa para outro dia e campo Arquivos; fica só em `calendario.json`, sem sincronizar com o Google Calendar. [D-018] [C-02] · [H-10]
- **Notas**: widget no estilo do Notas da Apple. [D-017]
- **Studio**: 3 painéis (Fontes, Chat com citações, Studio com resumo em áudio, vídeo, slides, mapa mental, relatórios, cartões, quiz, infográfico e tabela). [D-011]
- **Chat com anexos**: imagem, recorte de tela, PDF e texto, só na conversa atual. [D-025]

**Evolução da interface.** 03/11 página local → app nativo [D-004]; 05/11 vidro e widgets [C-01]; 07/11 aba Estudos e Studio estilo AI Studio [D-011]; 09/11 Studio estilo NotebookLM; 11/11 widget de Notas [D-017]; 13/11 reator roxo com progresso [D-020c]; 15/11 chat com anexos [D-025].

**Evolução da inteligência.**
- 03/11: voz do Mac pelo Atticus → Gemini Live, com o Claude executando. [D-003]
- 03–04/11: pesquisa por Claude Code (rápida e profunda). [D-008]
- 04–05/11: visão da tela e ações rápidas no Mac sem IA. [D-010]
- 07–10/11: vídeo (imagem e áudio), projetos, gravação de tela e modo curso. [D-011] [D-012]
- 11/11: busca por trechos, git, testes e Ollama de reserva. [D-015]
- 13/11: honestidade verificável, texto na tela, postura de assessor, trabalho longo. [D-020] [D-021]
- A persona passou de 5.425 para 9.670 e depois 14.186 caracteres até 13/11 [relatado: relatório da noite de 13/11]; não foi remedida.

## 03. Arquitetura e regras

### 3.1 Visão geral [levantado: 16/11/2026]
```text
Usuário (voz) -> Jarvis.app (Swift, WKWebView) -> servidor Python (aiohttp, 127.0.0.1:8765) -> Gemini Live (nuvem)
                                                        |
        +------------+-------------+------------+-------+----------+
        |            |             |            |                  |
   Claude Code    Atticus       Gemini REST   Cofre Markdown   macOS (AppleScript,
   `claude -p`    (opcional,    (tela, links, (memória, notas, screencapture, ScreenCaptureKit,
   (pesquisa,     ações curtas  vídeo, TTS)   conversas)       Keychain, caffeinate)
   trabalho longo) no Mac)                    + Ollama qwen3:8b (plano B de texto)
```

### 3.2 Componentes [levantado: 16/11/2026]
| Arquivo | Papel |
|---|---|
| `app/Jarvis.swift`, `app/main.swift` | App do Mac: janela web, inicia o servidor, som e Dock |
| `app/Claps.swift`, `app/MuteKey.swift` | Duas palmas; tecla F5 e aviso na tela |
| `app/Gravar.swift` | `jarvis-gravar`: grava tela e som do sistema (ScreenCaptureKit) |
| `app/build.sh` | Compila e assina com um certificado local fixo (ou assinatura ad hoc se faltar) |
| `static/index.html`, `static/studio.js`, `static/studio.css` | Interface e Studio |
| `prompts/persona.pt-BR.md` | Persona e regras de comportamento do Jarvis |
| `server.py` | Centro: 25 declarações de ferramentas, `Session`, `on_tool`, detector de afirmações, rotas, `--check` |
| `config.py`, `paths.py`, `core.py` | Configuração, caminhos, log, Keychain, cofre, `clean_env`, leitura rápida com Gemini |
| `gem.py` | Chamada confiável ao Gemini REST (corrida entre modelos, rodadas) e plano B Ollama |
| `vault.py`, `busca.py` | Memória no cofre (escrita atômica); índice SQLite FTS5 (trechos de 1.200 caracteres) |
| `research.py`, `trabalho.py` | Pesquisa e trabalho longo por Claude Code sem interface |
| `mac.py` | Ações rápidas no Mac sem IA |
| `video.py`, `sources.py`, `course.py`, `estudo.py` | Vídeo, fontes, modo curso e gravação |
| `notebook.py`, `projects.py`, `rotas_projetos.py` | Studio e projetos |
| `agenda.py`, `notas.py`, `rotas_agenda.py` | Agenda e Notas |
| `anexos_chat.py` | Anexos do chat |
| `testes.py` | Testes de fumaça (processos falsos; não chamam Gemini nem Claude) |

Dependência opcional fora do repositório: o `atticus.py` do app Atticus (ações no Mac que pedem raciocínio). Sem ele, `executar_no_mac` não é oferecida ao Gemini.

### 3.3 Fluxos
**Conversa.** A página captura o microfone com cancelamento de eco e envia pelo WebSocket `/ws`. Cada conexão monta o `setup` com: persona, memória do cofre, resumo da agenda, títulos das Notas e contexto do projeto aberto. Transcrição de entrada e saída ligadas, compressão de contexto "sliding window" e retomada por handle. `ThoughtFilter` descarta raciocínio entre asteriscos. As falas vão para `Conversas/AAAA-MM-DD.md` ou para a conversa do projeto aberto. [levantado: 16/11/2026, `server.py`, `core.py`]

**Ferramenta de voz.** `toolCall` → `on_tool` em tarefa assíncrona → mensagens `busy` (reator roxo e etapa) → `toolResponse`. Se a conexão estiver fechada, o resultado vai para a fila `outbox` (até 20 itens) e sai na volta. [levantado: 16/11/2026, `server.py`]

**Ação no Mac.** `mac_rapido` (sem IA, menos de 1 s) para o simples. `executar_no_mac` chama o Atticus com limite `task_timeout` (300 s); uma resposta do tipo "iniciei em segundo plano" ou "te aviso quando" vira erro "Não concluído" (`NOT_DONE`). [levantado: 16/11/2026, `server.py`] · [D-020a]

**Pesquisa.** `pesquisar_web` → `claude -p` com WebSearch e WebFetch, modo `rapida` (sonnet, esforço baixo, 150 s) ou `profunda` (sonnet, esforço alto, 420 s). Devolve `fala`, `resposta` em Markdown com citações `[n]` e `fontes`. [levantado: 16/11/2026, `research.py`] · [D-008]

**Trabalho longo.** `trabalho_longo` (iniciar, status, cancelar) → `claude -p --model sonnet --effort high`, ferramentas Read/Glob/Grep/WebSearch/WebFetch (só a web é pré-aprovada), `--add-dir` do cofre, `--strict-mcp-config`, `--no-session-persistence`, hooks desligados, stdin fechado. Limite de 25 minutos e um trabalho por vez. Ao fim: texto no chat, nota "Trabalho — <título>" no cofre marcada "confira antes de tratar como fato", e aviso ao Jarvis. Erro ou tempo esgotado viram "NÃO foi concluído". [levantado: 16/11/2026, `trabalho.py`] · [D-021]

**Vídeo, gravação e curso.** `assistir_video`: o Gemini analisa imagem e áudio; o resultado vira fonte do projeto e nota no cofre. `gravar_tela`: `jarvis-gravar` (tela e som do sistema, não o microfone). `estudar_curso`: Chrome por AppleScript e JavaScript, `caffeinate` enquanto roda, `curso.json` guarda onde parou. Não se baixa vídeo protegido. [relatado: plano do modo curso] · [D-012]

**Projetos e Studio.** Cada projeto em `projetos/<id>/` tem `projeto.json`, `conversa.jsonl`, `fontes/` e `arquivos/`. Chat com citações numeradas; geração em `notebook.py` (voz do Studio por Gemini TTS). [levantado: 16/11/2026] · [D-011]

**Memória.** `lembrar` (um fato por tópico em `Memória do Jarvis.md`), `anotar` e `ler_nota` (notas em áreas do cofre), `substituir` (só após confirmação), `buscar_memoria` (FTS5), `## Resumo` nos dias passados. [levantado: 16/11/2026, `vault.py`, `busca.py`] · [D-007]

**Anexos do chat.** Imagem em `clientContent` junto do texto; PDF transcrito por um Gemini comum e inserido como texto; até 10 itens; nada em disco. [levantado: 16/11/2026, `anexos_chat.py`] · [D-025]

### 3.4 As 25 ferramentas de voz [levantado: 16/11/2026, `server.py`]
| Grupo | Ferramentas |
|---|---|
| Ver e ler | `olhar_tela`, `abas_chrome`, `ler_abas_chrome`, `pesquisar_no_chrome`, `ler_link` |
| Pesquisar e lembrar | `pesquisar_web`, `buscar_memoria` |
| Agir no Mac | `mac_rapido`, `executar_no_mac`, `ajustar_permissao` |
| Trabalho longo e texto | `trabalho_longo`, `mostrar_texto` |
| Vídeo e estudo | `assistir_video`, `gravar_tela`, `estudar_curso`, `rever_trecho`, `video_na_tela`, `projeto`, `fonte_projeto` |
| Memória | `lembrar`, `anotar`, `ler_nota`, `substituir` |
| Organização | `agenda`, `notas` |

### 3.5 Modelos e serviços [levantado: 16/11/2026]
| Serviço | Uso | Onde |
|---|---|---|
| Gemini Live `models/gemini-3.8-live` | Voz | `server.py` (`MODEL`) |
| Gemini REST `gemini-3.5-flash-lite` e `gemini-3.5-flash` (reserva `gemini-3.6-flash`) | Tela, links, páginas, PDFs | `core.py` (`READERS`) |
| Gemini (vídeo; TTS `gemini-3.8-flash-tts`) | Análise de vídeo; voz do Studio | `video.py`, `notebook.py` |
| Claude Code `claude -p` (sonnet) | Pesquisa e trabalho longo | `research.py`, `trabalho.py` |
| Atticus (opcional) | Ações no Mac que pedem raciocínio | `server.py` |
| Ollama `qwen3:8b` (local) | Plano B só de texto (até 60.000 caracteres); a voz não tem reserva [C-06] | `gem.py` |
| macOS | AppleScript, `screencapture`, `sips`, ScreenCaptureKit, Keychain, `caffeinate` | `server.py`, `app/` |

*Os nomes dos modelos são os que estão no código; não foram conferidos na documentação pública dos fornecedores.*

### 3.6 Dados e onde moram [levantado: 16/11/2026]
| Dado | Lugar | Observação |
|---|---|---|
| Memória e conversas | cofre (`vault` no `config.json`), em `08 - Jarvis/` | Fonte da verdade |
| Configuração | `config.json` (modelo em `config.example.json`) | Escrita atômica; fora do git |
| Agenda e Notas | `calendario.json`, `notas.json` | Fora do git |
| Projetos | `projetos/` | Fora do git |
| Índice de busca | `busca.db` | Reconstruível; fora do git |
| Anexos | `anexos/`, `arquivos/` | Fora do git |
| Log | `jarvis.log` | Base das métricas de queda e erro |
| Chave do Gemini | Keychain, serviço `jarvis-gemini` (`scripts/set-key.sh`), ou `GEMINI_API_KEY` | Nunca em arquivo |

### 3.7 Regras de honestidade [levantado: 16/11/2026, `server.py`] · [D-020a]
- `ONGOING` ("em segundo plano", "em andamento"…) só vale com ferramenta rodando.
- `DONE` ("finalizei", "terminei"…) só vale se uma ferramenta rodou desde a última fala do usuário, ou se um trabalho bem-sucedido ocorreu nos últimos 30 minutos (`RECENT_WORK`).
- Negação antes, na mesma frase ("nada está em andamento"), torna a fala honesta.
- Se não vale: aviso vermelho no chat e mensagem de correção ao Gemini, que não manda executar nada. A fala de correção não é checada de novo.
- **Limite:** funciona por frases; uma mentira dita de outro jeito passa. [H-08]

### 3.8 Segurança e privacidade
- Visão da tela, internet e ações no Mac são interruptores (visão desligada por padrão); o que a tela mostra vai para o Google, e a persona manda avisar se aparecer senha ou dado bancário. [levantado: 16/11/2026, `config.example.json`, persona]
- O servidor escuta só em `127.0.0.1`. [levantado: 16/11/2026]
- `clean_env()` remove variáveis `CLAUDE*`, `ATTICUS_*`, `ANTHROPIC_*`, `MCP_*` e `OTEL_*` herdadas, para o Claude não anexar à sessão errada. [levantado: 16/11/2026, `core.py`]
- Trabalho longo e pesquisa: só leitura, nas pastas do código e do cofre; só a web é pré-aprovada, então uma leitura fora delas é recusada. [levantado: 16/11/2026, `trabalho.py`]
- Remover, enviar e-mail e esvaziar a Lixeira pedem o sim do usuário. [D-010]
- Anexos do chat não vão para disco. [D-025]

### 3.9 Resiliência
Reconexão ao Gemini com handle de retomada; fila de saída de até 20 mensagens; escrita atômica no cofre e na configuração; corrida entre modelos e Ollama de reserva; limites de tempo em tudo (300 s, 150/420 s, 25 min). [levantado: 16/11/2026, `server.py`, `vault.py`, `core.py`, `gem.py`] Espera crescente de até 30 s e fila de correção após queda [relatado: relatório da noite de 13/11]. [C-11]

### 3.10 Camada Claude Code e cofre
- O Claude Code do autor lê a mesma Memória do Jarvis e segue a regra do crítico. [D-019]
- Regras do cofre: frontmatter em toda nota, índice de pasta atualizado, "adicionar antes de criar", dias passados com `## Resumo`. Um cofre mínimo de exemplo está em `examples/vault-minimal/`.

## 04. Testes e pendências

### 4.1 Testes automáticos
`./run.sh --test` (ou `testes.py`): pasta temporária, cofre de `examples/vault-minimal`, processos falsos, sem Gemini e sem Claude. Resultado em 16/11/2026: "tudo certo: 155 verificações" (91 chamadas `check(` no arquivo; algumas rodam em laço) [levantado: 16/11/2026]. `run.sh --check` conecta ao Gemini de verdade e pede uma fala curta.

### 4.2 Testes de aceite (só se confirmam usando; nenhum foi executado nesta documentação)
| ID | Teste | Esperado |
|---|---|---|
| TA-01 | `run.sh --check` | `audio=…s tempo=…s fala='…'`; "fechou: 1007" indica configuração recusada |
| TA-02 | Pedir uma pesquisa de previsão do tempo | Reator roxo, linha de etapa, resultado falado ao fim |
| TA-03 | Apertar F5 no meio de uma pesquisa | Microfone solta, o roxo continua; ao fim, som e resultado no chat; desmutar continua a mesma conversa |
| TA-04 | Mudo por 3 min; `grep "Gemini closed" jarvis.log \| tail -3` | Sem "1008" no intervalo (H-01) |
| TA-05 | "Monta um prompt para o Claude Code corrigir…" | Texto inteiro no chat com botão Copiar; ele diz em uma frase que está lá |
| TA-06 | "Faz um diagnóstico do Jarvis em segundo plano e me avisa" | Chama `trabalho_longo` e mostra as etapas; se não chamar, aparece o aviso vermelho |
| TA-07 | Contar um plano com um furo | Ele aponta o ponto mais fraco, sem "entendido, perfeito" (H-03) |
| TA-08 | Anexar uma imagem e um PDF no chat | Ele vê a imagem e lê o PDF; nada fica gravado em disco |

### 4.3 Pendências
| ID | Item | Estado |
|---|---|---|
| P-03 | Persistir a preferência do Windguru (D-029) | Aberto |
| P-04 | Palavra de ativação ou novo nome de chamada (D-028, D-020h) | Aberto |
| P-05 | Faturar a chave do Gemini (H-04) | Decidido: continuar no gratuito; reavaliar se erros de cota atrapalharem mais de dois dias por semana (C-07) |
| P-06 | Refatorar `on_tool` (longa cadeia de `elif`) | Aberto [relatado: relatório da noite de 13/11] |
| P-07 | `asyncio.create_task(self.on_tool(call))` sem referência forte à tarefa | Aberto |
| P-08 | Áudio do raciocínio vazado: exige `thinkingConfig`, não adicionado por não ser testável | Aberto [relatado] |
| P-09 | Modo texto cai a cada 2 min por inatividade | Aberto [relatado] |
| P-10 | Modo curso preso a uma única plataforma | Aberto (ver README) |
| P-11 | `METRICAS.md` com horas e medições reais (H-07) | A produzir |
| P-13 | Confirmar C-01 a C-12 com as palavras do Lucas | Feito em 16/11/2026; documentos aprovados no mesmo dia |
| P-14 | Integrar a agenda com o Google Calendar (C-02, H-10) | Objetivo para a próxima versão |
| P-15 | Reserva para a voz quando o Gemini Live cair (C-06) | Risco aceito pelo Lucas por enquanto; o Ollama cobre só texto |

### 4.4 O que esta versão não verificou
Os testes de fumaça passaram (155 verificações), mas nenhum teste de aceite foi executado e o Gemini não foi chamado. Os números de operação (quedas de sessão, 429/503, tempos) vêm do relatório da noite de 13/11, não reconferidos. Os nomes de modelo não foram conferidos na documentação pública dos fornecedores.
