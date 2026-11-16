# Jarvis: assistente de voz que conversa, pesquisa, estuda e executa no Mac

> 🎥 **Demonstração (3 min):** _link do vídeo aqui_

Assistente de voz para Mac, em português. Você conversa e o Jarvis responde por voz (Gemini Live), age no computador,
pesquisa com fontes, assiste e estuda vídeos e cursos, e guarda memória em notas Markdown (compatível com Obsidian),
que o Claude Code também lê.

Construído por Lucas Mandelblatt entre 03/11 e 16/11/2026, por vibe coding com o Claude Code. A documentação é
**retroativa**: foi escrita depois, a partir do código, do histórico de desenvolvimento e das conversas, para registrar
e tornar rastreáveis as decisões já tomadas. Cada decisão traz a fala do autor, a data e o efeito no código.

| Documento | O que tem |
|---|---|
| [`01-DECISOES.md`](01-DECISOES.md) | O que o autor decidiu, com fala literal, reversões, hipóteses e aprendizados |
| [`00-BIBLIA.md`](00-BIBLIA.md) | O que o Jarvis é: propósito, experiência, arquitetura, regras, testes e pendências |
| Este README | Apresentação, ficha do projeto e instalação |

## O que ele faz
- **Voz em tempo real** pelo Gemini Live: dá para interromper; mudo pela tecla F5 e ativação por duas palmas.
- **25 ferramentas de voz**: ver a tela e o Chrome, pesquisar na web com fontes, agir no Mac, assistir vídeos,
  estudar cursos, gravar a tela, agenda, notas, memória e busca na memória, entregar textos longos e rodar trabalho
  longo em segundo plano.
- **Pesquisa com fontes** por um Claude Code sem interface (só WebSearch e WebFetch).
- **Trabalho longo**: o Claude Code sem interface lê o código e o cofre por até 25 minutos, mostra cada passo na tela
  e entrega texto, plano ou prompt. Ele não altera nada.
- **Studio** (estilo NotebookLM): projetos com fontes, chat com citações e geração de resumo em áudio, slides, mapa
  mental, quiz e mais.
- **Memória em arquivos Markdown**, com busca por trechos (SQLite FTS5).
- **Honestidade verificável**: um detector acusa na tela quando o Jarvis diz que fez algo sem nenhuma ferramenta ter
  rodado.

## Por que isso importa para quem constrói agentes
| Capacidade | Onde o Jarvis mostra |
|---|---|
| Prompt engineering | Persona em blocos, com motivo e exemplo em cada regra (`prompts/persona.pt-BR.md`); prompts de método para execuções sem interface (`research.py`, `trabalho.py`) |
| Orquestração de agentes | O Gemini Live orquestra 25 ferramentas e delega ao Claude Code com ferramentas restritas; um trabalho longo por vez, com cancelamento e status |
| Automações | Leitura diária de sites marcados, agenda e notas por voz, ações rápidas no Mac sem IA, curso em fila com retomada |
| Vibe coding com controle | Histórico em git, testes de fumaça antes de cada mudança, revisão por subagente |
| APIs | Gemini Live (WebSocket), Gemini REST, Gemini TTS, Ollama local, Claude CLI, rotas HTTP próprias, ScreenCaptureKit |
| Análise de dados com IA | Análise de vídeo (imagem e áudio), busca por trechos, diagnóstico dos próprios logs |

**O que isto não prova:** impacto de negócio. O Jarvis é de uso individual, e as horas economizadas ainda não foram
medidas (hipótese H-07 em `01-DECISOES.md`).

## Arquitetura em uma figura
```text
Usuário (voz) -> App Mac (Swift + janela web) -> servidor Python local -> Gemini Live (nuvem do Google)
                                                     |
       +-------------+-------------+---------------+---------------+
       |             |             |               |               |
  Claude Code     Atticus      Gemini REST    Cofre Markdown   Ferramentas locais
  sem interface   (opcional,   (tela, links,  (memória,        (AppleScript, gravação
  (pesquisa,      ações no     vídeo, TTS)    notas,           de tela, agenda)
  trabalho longo) Mac)                        conversas)
```
Detalhes em [`00-BIBLIA.md`](00-BIBLIA.md).

## Evolução em 13 dias
- **03/11**: voz do Mac → o autor não gostou → Gemini Live → app nativo com memória no Obsidian.
- **04–05/11**: palmas, F5, visão da tela, pesquisa por Claude Code, interface de vidro com widgets.
- **07–10/11**: Studio estilo NotebookLM; gravação de tela para assistir cursos.
- **11/11**: widget de Notas, git, busca por trechos, Ollama de reserva, testes.
- **13/11**: noite autônoma em branch separada (honestidade, texto inteiro no chat, progresso visível, mudo sem
  derrubar a conversa) e trabalho longo de verdade.
- **15/11**: anexos no chat.

## Números
| O quê | Valor | Origem |
|---|---|---|
| Ferramentas de voz | 25 | contadas em `server.py` (16/11/2026) |
| Testes de fumaça (`testes.py`) | 155 verificações passando | `./run.sh --test`, 16/11/2026 |
| Tarefas curtas no Mac | 39 entre 03/11 e 13/11; mediana 7,2 s; p90 17,4 s | relatório de 13/11, não reconferido |
| Pesquisa rápida | 97,6 s antes; 26,4 s depois (perguntas diferentes, não é comparação justa) | relatório de 13/11, não reconferido |
| Curso estudado sozinho | 27 de 84 aulas, até o acesso ser encerrado | plano do modo curso |
| Horas economizadas | **não medido** | H-07 |

## Ficha do projeto
| Campo | Valor |
|---|---|
| Responsável (quem decide) | Lucas Mandelblatt |
| Quem implementa | Claude Code, sob direção do autor |
| Problema | Um assistente de voz que só responde não ajuda no trabalho real. O autor queria um que ouvisse, agisse no computador, lembrasse do que combinaram e dissesse a verdade sobre o que fez. [D-001] [D-020a] |
| Usuário | Uma pessoa, em um Mac |
| Linguagens | Python (servidor aiohttp), Swift (app macOS), HTML/JS (interface) |

---

# Instalação e uso

> Só macOS (usa Keychain, osascript, screencapture e um app Swift). Interface e persona em português do Brasil.

> **Estado atual:** o código ainda tem caminhos, nomes e convenções do autor fixos (persona, áreas do cofre,
> caminhos de ferramentas, clima, bundle id do app). A limpeza está em andamento; até ela terminar, um clone
> pode não funcionar por completo em outro Mac.

## O que sai do seu Mac
- O áudio da conversa vai para o Google (Gemini). Fotos da tela também, quando a "visão da tela" está ligada.
- Pesquisa e trabalho longo usam o Claude Code instalado por você, na sua conta.
- O resto (agenda, notas, projetos, memória) fica nos seus arquivos locais. O servidor escuta só em 127.0.0.1.

## Requisitos
- macOS 13 ou mais novo
- Python 3.11 ou mais novo (testado apenas no 3.15.2)
- Uma chave de API do Gemini: https://aistudio.google.com/apikey
- Opcionais: `yt-dlp` e `ffmpeg` (assistir vídeos), Claude Code (pesquisa e trabalho longo) e
  as Ferramentas de Linha de Comando do Xcode (compilar o app)

## Instalação
```bash
git clone <URL-do-repositório> jarvis-voz && cd jarvis-voz
./install.sh            # ambiente, dependências e config.json
./scripts/set-key.sh    # guarda a chave do Gemini no Keychain
./run.sh --check        # testa a conexão com o Gemini
./run.sh                # abre no navegador
```

Para ter janela própria, F5 como mudo, palmas e gravação de tela, compile o app:
```bash
./install.sh --app      # compila em ~/Applications/Jarvis.app
```
Na primeira vez o macOS pede o Microfone e, se você usar, a Gravação de Tela.

### Certificado de assinatura (recomendado)
O macOS liga essas permissões à assinatura do app. Sem um certificado fixo, o app é assinado "ad hoc" e a permissão
de Gravação de Tela cai a cada compilação. Para evitar isso, crie uma vez um certificado local:

1. Abra o **Acesso às Chaves** e vá em **Acesso às Chaves > Assistente de Certificado > Criar um Certificado**.
2. Nome: `Jarvis Local Signing`. Tipo de identidade: **Raiz autoassinada**. Tipo de certificado: **Assinatura de código**.
3. Compile de novo com `./install.sh --app`. O `app/build.sh` encontra o certificado pelo nome.

O certificado só vale no seu Mac; ele não serve para distribuir o app.

### Identidade do app
| Chave no `config.json` | Variável | Padrão |
|---|---|---|
| `bundle_id` | `JARVIS_BUNDLE_ID` | `local.jarvis-voz` |
| `sign_identity` | `JARVIS_SIGN_ID` | `Jarvis Local Signing` |
| `app_path` | `JARVIS_APP` | `~/Applications/Jarvis.app` |

A variável tem prioridade sobre o `config.json`. Mudar `bundle_id` ou `sign_identity` faz o macOS pedir as permissões de novo.

## Configuração (`config.json`, fora do git)
| Chave | Padrão | O que faz |
|---|---|---|
| `user_name` | `Usuário` | como o Jarvis te chama; também marca as suas falas nas transcrições. Mudou? Reinicie o Jarvis |
| `city` | Rio de Janeiro | cidade do widget de clima: `{"name", "region", "lat", "lon"}` |
| `voice` | `Charon` | voz do Gemini |
| `vault` | `~/Jarvis` | pasta de notas Markdown onde ficam a memória e as conversas |
| `port` | `8765` | porta local |
| `vision` / `internet` / `actions` | `false` / `true` / `true` | permissões; também mudam pelos interruptores do app |
| `task_timeout` | `300` | segundos para uma ação no Mac |
| `claps` | `true` | duas palmas acordam o Jarvis (só no app) |
| `interrupcao` | `normal` | `normal`, `firme` ou `nunca`: quanto a sua voz corta a fala do Jarvis |

Programas e pastas (opcional; sem a chave, o Jarvis procura em `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` e nas pastas do sistema):

| Chave | Padrão | O que é |
|---|---|---|
| `claude_path` | procurado | Claude Code (pesquisa e trabalho longo) |
| `ytdlp_path` | procurado | `yt-dlp` (vídeos de outros sites) |
| `ffprobe_path` | procurado | `ffprobe` (duração do vídeo) |
| `atticus_path` | `~/Applications/Atticus.app/Contents/Resources/atticus.py` | executor de ações no Mac |
| `app_path` | `~/Applications/Jarvis.app` | o app compilado por `app/build.sh` |

O cofre (opcional; veja `examples/vault-minimal/`):

| Chave | Padrão | O que é |
|---|---|---|
| `vault_areas` | Inbox, Projetos, Pessoal, Recursos | pastas onde o Jarvis grava notas: `{"area": {"pasta": "01 - Projetos", "projeto": "projetos", "descricao": "o que vai ali"}}`. `inbox` sempre existe |
| `vault_topics` | — | renomeia seções da "Memória do Jarvis" (ex.: `{"quem": "Quem é a Ana"}`) |

A persona fica em `prompts/persona.pt-BR.md`. Para usar uma versão sua sem mexer nela, crie `prompts/persona.local.md`
(fica fora do git). Os campos `{user}`, `{switches}`, `{today}` e `{time}` são preenchidos sozinhos.

A chave do Gemini não fica no `config.json`. Use o Keychain (`./scripts/set-key.sh`) ou a variável `GEMINI_API_KEY`.

## Limitações conhecidas
- Os textos para o Gemini tratam o usuário no masculino ("ele"). O nome entra sem artigo ("de Ana", "a Ana").
- O modo curso (`estudar_curso`) só funciona com a plataforma TubeClub.
- `executar_no_mac` (ações no Mac que pedem raciocínio, como e-mail e editar arquivos) depende do Atticus, um app à parte.
  Sem ele, a ferramenta não é oferecida ao Gemini e a persona avisa que o Jarvis não faz essas ações. O `mac_rapido`
  (abrir apps, mover arquivos, volume) continua funcionando.

## Seus dados
Ficam ao lado do código, e o git os ignora: `config.json`, `calendario.json`, `notas.json`, `projetos/`,
`busca.db`, `anexos/`, `arquivos/`, `historico/`. A memória e as conversas ficam no `vault`, em `08 - Jarvis/`.

## Testes
```bash
./run.sh --test
```
Rodam numa pasta temporária, com o cofre de `examples/vault-minimal` e o projeto de `tests/fixtures`: não tocam nos
seus dados nem chamam o Gemini ou o Claude. Só o `jarvis.log` recebe algumas linhas.

## Problemas comuns
- **Chave não encontrada:** rode `./scripts/set-key.sh`.
- **Erro 429 ou "quota":** limite do plano gratuito do Gemini.
- **Conexão fecha com 1007 ou 1008:** o Gemini recusou a configuração ou o modelo, ou a sessão ficou ociosa. Veja `jarvis.log`.
- **Tela em branco ou sem som:** confira o Microfone em Ajustes do Sistema > Privacidade.
- **Diagnóstico geral:** `./scripts/doctor.sh`.

## Aviso sobre a tecla F5
O app remapeia a tecla F5 (ditado) com `hidutil` para silenciar o Jarvis e desfaz isso ao sair.
Se o app fechar de forma abrupta, reiniciar o Mac deve restaurar a tecla (o `hidutil` não guarda o mapeamento
entre reinícios; não testado aqui).

## Licença
MIT. Veja `LICENSE`.
