# Jarvis (voz)

Assistente de voz para Mac. Você conversa em português e o Jarvis responde por voz (Gemini Live).
Ele guarda memória em notas Markdown (compatível com Obsidian), mantém agenda e notas, estuda vídeos e
fontes em "projetos" e, se você quiser, pesquisa na internet e faz trabalhos longos com o Claude Code.

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
