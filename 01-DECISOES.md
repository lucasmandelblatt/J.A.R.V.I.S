# 01-DECISOES: o que o Lucas decidiu no Jarvis

Registro retroativo (16/11/2026) das decisões de produto e de arquitetura. **Aprovado pelo Lucas em 16/11/2026.** Mudança nova entra primeiro aqui, com fala e data, e depois na `00-BIBLIA`.

**Como ler.** Datas e horas em horário de Brasília. A fala literal é do Lucas; a leitura e o efeito são interpretação explícita de quem documentou. "Transcrição de voz" pode trazer erro de reconhecimento. Estados: Confirmada · Parcial · Revertida · Pendente.

**Etiquetas** (as mesmas nos três arquivos): `[D-001]` decisão do Lucas · `[H-01]` hipótese em aberto · `[proposta]` sugestão da IA ainda não validada (ou aceita só pelo uso) · `[levantado: data]` fato conferido no código ou em arquivo · `[relatado: fonte]` fato vindo de relatório ou transcrição, não reconferido.

**Versão pública.** Esta é a versão publicada do registro. As fontes privadas (sessões do Claude Code e transcrições de voz) não estão no repositório. Algumas decisões aparecem resumidas, sem a fala literal; a fala está na versão privada. Os IDs que faltam na sequência (D-023, D-024, D-026) são decisões fora do escopo do Jarvis, mantidas só na versão privada.

## 1. Decisões

### D-001 · 03/11 · Visão do produto
**Registro (resumo; fala literal na versão privada):** um assistente "igual ao do Tony Stark": voz natural, que pausa quando é interrompido em vez de atropelar, com memória longa, capaz de analisar vídeos, conteúdos e textos, realizar tarefas e explicar assuntos.
**Leitura:** seis requisitos: voz natural, interrupção sem atropelo, memória longa, vídeo e conteúdo, tarefas, explicação.
**Efeito:** interrupção configurada em `realtime_input_config` (`server.py`); memória em `vault.py`; vídeo em `video.py`.
**Estado:** Confirmada como escopo. "Memória longa" é parcial (ver L-08).

### D-002 · 03/11 · Sem plataforma externa
**Registro (resumo):** o Lucas pediu, de início, que nada rodasse em plataforma externa como Gemini ou ChatGPT, e que tudo ficasse no Claude Code.
**Estado:** **Revertida em D-003** (mesma noite). Sobrevive em parte: dados e ações ficam no ecossistema Claude e Obsidian (D-004). A voz roda na nuvem do Google.

### D-003 · 03/11 · Voz pelo Gemini Live; execução pelo Claude
**Registro (resumo):** a primeira voz (a do Mac, pelo Atticus) não agradou; o Lucas queria algo "muito mais próximo do ChatGPT", perguntou se dava para integrar a voz do Gemini por API e decidiu testar o Gemini.
**Leitura:** o Lucas trocou a restrição de D-002 pela qualidade da voz.
**Efeito:** `MODEL = "models/gemini-3.8-live"` (`server.py`); chave no Keychain (`scripts/set-key.sh`, `core.py`); dois modelos, o que exige regras de fronteira (D-020). Consequência medida depois: cota gratuita e quedas de sessão.
**Estado:** Confirmada.

### D-004 · 03/11 · App, não localhost, com memória no Obsidian
**Registro (resumo):** abrir o Jarvis como aplicativo, a qualquer momento; lembrar do que foi dito antes; integrar ao Obsidian para que a memória fique tanto no Jarvis quanto no Claude Code.
**Efeito:** `app/Jarvis.swift` (janela `WKWebView`); `vault.py`; a Memória do Jarvis é lida também pelo Claude Code.
**Estado:** Confirmada.

### D-005 · 03/11 22:04 · Tratamento
**Fala (transcrição de voz):** "Você pode me chamar de Lucas, que é o meu nome."
**Efeito:** a persona trata o usuário pelo nome, nunca por "senhor" (na versão pública, o nome vem de `user_name` no `config.json`). **Estado:** Confirmada.

### D-006 · 03/11 · Ativar por duas palmas
**Registro (resumo):** o Lucas pediu que duas palmas fizessem o Jarvis aparecer na tela.
**Efeito:** `app/Claps.swift`; o app fica ouvindo o microfone (ponto laranja).
**Estado:** Parcial: o Lucas relatou falhas em 03/11 e em 12/11.

### D-007 · 03/11 · Corrigir memória com `substituir`
**Registro (resumo):** o Lucas escolheu o nome do comando, `substituir`, por ser mais fácil de o modelo entender.
**Efeito:** a ferramenta `substituir` só aplica depois de confirmação (`confirmado=false`, depois `true`).
**Estado:** Confirmada.

### D-008 · 03–04/11 · Pesquisa de verdade
**Registro (resumo):** em vez de abrir o Google no navegador e responder por ali, o Jarvis deve saber pesquisar, filtrar e avaliar fontes verdadeiras.
**Efeito:** `research.py`: `claude -p` só com WebSearch e WebFetch, em modo rápida (150 s) e profunda (420 s). A busca do Google dentro do Gemini Live é recusada no plano gratuito.
**Estado:** Confirmada. Tempo: 97,6 s numa pesquisa rápida, antes de corrigir [relatado: relatório da noite de 13/11].

### D-009 · 04/11 13:10 · Pausar a escuta sem abrir o app (F5)
**Fala:** "Quero fazer a segunda opção: pausar o jarvis de ficar me escutando 24/7, mas sem ter a necessidade de entrar no app para fazer isso, se não a função dele ligar com as palmas não vai funcionar."
**Efeito:** `app/MuteKey.swift` (tecla F5 e aviso na tela). Revisado em D-020d.
**Aprendizado (13:34):** "Eu identifiquei que o atticus já tinha um app instalado no meu mac, e no app original essa função que eu te pedi já existe. [...] O app que vc criou também funcionou, mas não é mais necessário." Ver L-02.
**Estado:** Confirmada.

### D-010 · 05/11 00:45 · Organizar a Mesa sem apagar nada
**Fala (transcrição de voz):** "Você consegue organizar tudo isso para mim, colocando todos esses prints e todas essas, sabe, bagunças em uma pasta só?"
**Efeito:** `mac_rapido` (`mac.py`, sem IA). Regra: nada é apagado; Lixeira só depois do sim do Lucas.
**Estado:** Confirmada.

### D-011 · 07/11 e 09/11 · Studio de estudo
**Fala (07/11):** "atualize o front-end do Jarvis para incluir uma nova aba de Estudos no menu e, dentro dela, uma sub-aba chamada Studio. O design deve replicar a interface do Google AI Studio". **(09/11):** pedido de engenharia reversa do NotebookLM: "Analise o site abaixo, analisando todas as paginas que podem ser abertas, todos os recursos, funcionalidades, etc."
**Leitura:** o Studio nasceu no estilo Google AI Studio e foi refeito no estilo NotebookLM depois da análise de 09/11.
**Efeito:** `static/studio.js`, `static/studio.css`, `notebook.py`. O motivo de reconstruir em vez de usar o conector pronto foi registrado em 16/11: integrar tudo numa plataforma só (C-04).
**Estado:** Confirmada.

### D-012 · 09/11 e 10/11 · Assistir a cursos por gravação de tela
**Fala:** "A única ideia que eu tenho no momento é a seguinte: Eu estar logado na conta da plataforma do curso e pedir ao jarvis acessar por meio da gravação de tela autônoma." / (10/11) "eu quero que você me explique como que seria esse modo curso que você sugeriu."
**Leitura:** o caminho adotado é assistir como um aluno, logado na própria conta, sem baixar o vídeo. O plano foi aprovado em 10/11.
**Efeito:** `app/Gravar.swift` (ScreenCaptureKit); `estudo.py`; ferramentas `gravar_tela` e `estudar_curso`.
**Estado:** Confirmada. O curso parou em **27 de 84 aulas** quando o acesso à plataforma foi encerrado.

### D-013 · 10/11 10:43 · Quem comanda o curso
**Fala:** "prefiro pedir para você, o controle e cuidado com vc no comando é muito maior" (resposta a "É melhor eu pedir para vc essa tarefa, para ele, ou é indiferente?").
**Leitura:** o Lucas prefere comandar tarefas longas pelo Claude Code, onde vê e controla, e não pela voz.
**Estado:** Confirmada (preferência de uso).

### D-014 · 11/11 12:21 · Vídeos para a Lixeira; o conhecimento fica em texto
**Fala:** "pode eliminar os vídeos, e seguir com o plano" (depois de perguntar se o Jarvis perderia a memória sobre eles).
**Efeito:** as análises em texto ficaram; os vídeos foram para a Lixeira.
**Estado:** Confirmada.

### D-015 · 11/11 12:13 · Arquitetura de dados, grátis e mais confiável
**Fala:** "Eu penso que talvez seja melhor para o jarvis que ele seja adicionado a um banco de dados externo [...] quero buscar opções viáveis, que sejam gratuitas, para a gente melhor a qualidade do aplicativo como um todo."
**Leitura:** o Lucas propôs "banco externo". A solução adotada foi outra, `[proposta]` aceita: índice **local** SQLite FTS5 (`busca.py`; os arquivos continuam sendo a fonte), git só com código (`.gitignore`), `testes.py`, divisão do `server.py` e Ollama como plano B.
**Evidência:** commits de 11/11 entre 12:18 e 12:44 (repositório privado).
**Estado:** Confirmada, com desvio da proposta original.

### D-016 · 11/11 13:12 · Entender o que foi construído
**Fala:** "Agora faz o caminho reverso, me explica passo por passo o que vc fez e porque. [...] Quero entender o por tras das coisas, por exemplo: como o sistema funciona, para que o banco de dados serve, etc..."
**Leitura:** princípio de trabalho: o Lucas quer poder questionar cada recomendação.

### D-017 · 11/11 · "Notas" é um widget do Jarvis
**Fala (02:52):** "eu quero que você, a partir de agora, adicione na página inicial um widget de notas [...] como se fosse você literalmente copiar a interface do Notas do iPhone e do Mac". **(03:02, voz):** "Sempre que eu te pedir para você escrever dentro do notas, é para você escrever dentro desse novo widget que a gente acabou de criar, o notas."
**Efeito:** `notas.py`; regra na persona: "Notas" é o widget, nunca o Obsidian.
**Aprendizado:** ver L-03. **Estado:** Confirmada.

### D-018 · 12/11 02:20 · Anexos na agenda: arrastar ou clicar
**Fala:** "eu posso arrastar documentos para dentro daquilo e ele faz o upload, ou posso clicar e fazer da maneira como você fez. Eu quero ter a opção de poder fazer das duas formas."
**Efeito:** campo Arquivos nas tarefas do calendário. **Estado:** Confirmada.

### D-019 · 12/11 19:36 · Regra do crítico
**Fala:** "A gente vai executar uma coisa de cada vez, sem alucinações [...] com principal foco em solucionar o problema, não mascarar o problema. [...] Você deve me responder sempre como um crítico [...] Você não vai responder aquilo que eu quero ouvir só para eu achar que está tudo bom."
**Efeito:** regra global do Lucas para o Claude Code; no Jarvis, o bloco da persona sobre a postura de assessor (`prompts/persona.pt-BR.md`).
**Estado:** Confirmada. O efeito na voz real é a hipótese H-03.

### D-020 · 13/11 01:47 · Noite autônoma, em cópia, com aceite do Lucas
**Fala:** "o Jarvis tem um design ótimo, mas falha no que é essencial. Ele diz que fez coisas que não fez, não entrega o que eu peço, fica em silêncio sem mostrar se está trabalhando e morre quando eu aperto o F5." / "Um Jarvis quebrado de manhã é o pior resultado possível; uma correção pela metade, bem explicada, é melhor que uma correção grande que eu não consigo conferir." / Limites: "Nada pode ter efeito fora da cópia"; o merge no `main` "fica para mim".
*Nota de fonte:* o texto foi enviado como prompt montado com ajuda de IA. Trate como decisão aprovada ao enviar, não como fala espontânea.
**Efeito:** branch separada, um commit por assunto, relatório e revisão por subagente. Aceito por merge no `main` em 13/11 às 08:13 (repositório privado). A fala literal de aceite não foi localizada.

Sub-decisões do mesmo prompt:

| ID | Fala literal (prompt de 13/11) | Onde está | Estado |
|---|---|---|---|
| D-020a | "Ele nunca deve afirmar que está fazendo, fez ou terminou algo sem que uma ferramenta tenha rodado nesta conversa." | persona; detector `ONGOING`/`DONE` (`server.py`); `NOT_DONE` transforma "iniciei em segundo plano" em erro | Confirmada, com limite: age por frases |
| D-020b | "entregáveis de texto vão sempre por essa ferramenta, inteiros" | ferramenta `mostrar_texto`; bloco "ENTREGAS DE TEXTO" da persona | Confirmada |
| D-020c | "O objetivo é eu nunca ficar falando sozinho sem saber se ele está trabalhando." | `BUSY` (`server.py`); reator roxo e linha de etapa em `static/index.html` | Confirmada; a interface não tem teste automático |
| D-020d | "Mutar deve só parar de ouvir o microfone. A conversa e as tarefas em andamento continuam" | `keep_alive` e `SILENCE` (`server.py`) | **Hipótese H-01** |
| D-020e | "Nada do raciocínio do modelo [...] pode aparecer no chat ou na fala." | `ThoughtFilter` (`server.py`) | **Parcial**: filtra o texto; o áudio não (ver P-08) |
| D-020f | "ele é um assessor que pensa junto, que, ao receber ideias ou um plano, aponta o que falta, discorda quando tem motivo, traz pontos novos e pesquisa quando o pedido envolve fatos atuais" | persona | **Hipótese H-03** |
| D-020g | "Implemente só se for uma mudança pequena de configuração, atrás de um interruptor fácil de desfazer." (barulho interrompe a fala) | `realtime_input_config`, chave `interrupcao` no `config.json` | Confirmada; efeito real não testado |
| D-020h | "Baixa prioridade: só registre no diagnóstico o que poderia ajudar." ("Jarvis" ouvido como "chaves") | nada implementado | Pendente (P-04) |

### D-021 · 13/11 · Trabalho longo de verdade `[proposta]` aceita pelo uso
**Origem:** o relatório da noite concluiu que o trabalho longo "não tem motor" e propôs uma ferramenta própria que rodasse o Claude Code sem interface. Não há fala literal de aprovação. O uso começou em 13/11 às 15:52, e o commit é de 16:03.
**Efeito:** `trabalho.py`: `claude -p`, sonnet, esforço alto, só Read/Glob/Grep/WebSearch/WebFetch, limite de 25 min, um trabalho por vez. **Estado:** Confirmada (uso e commit).

### D-022 · 15/11 13:50 · Prompt pronto sempre que algo volta ao Claude Code
**Fala (transcrição de voz):** "Sempre que a gente tiver um objetivo que ele vai precisar voltar para o Cloud Code, né, para a gente fazer atualizações no sistema, criar algo, você já vim com essa sugestão de prompt, fica muito legal [...] Era exatamente o que eu queria da sua parte."
**Efeito:** o trabalho longo termina entregando o texto, o plano ou o prompt (`trabalho.py`). **Estado:** Confirmada.

### D-025 · 15/11 15:12 · Anexos no chat sem gravar em disco
**Fala:** "eu queria fazer recorte de tela e mandar no chat do Jarvis, sem que isso fique armazenado, como uma imagem de referência desse projeto inteiro, mas só dentro do chat naquele momento da conversa."
**Efeito:** `anexos_chat.py`: nada vai para disco, projeto ou cofre; até 10 itens; PDF é transcrito em memória por um Gemini comum (PDF em `inlineData` derruba a conexão, medido em 15/11).
**Estado:** Confirmada no código público.

### D-027 · 16/11 01:35 · Documentar o Jarvis retroativamente
**Fala (transcrição de voz):** "O projeto que eu quero documentar é justamente você, que eu criei na base do vibe coding puro. [...] você montar um diagnóstico e um estudo de como que foi feito o Jarvis." E: "um documento muito bom para eu adicionar no meu portfólio [...]"
**Estado:** Em andamento (estes documentos).

## 2. Pedidos do Lucas ainda não atendidos
| ID | Fala literal | Estado |
|---|---|---|
| D-028 | "eu só quero que você fale, que você me pergunte alguma coisa, que você inicie se eu te chamar por Jarvis, e aí Jarvis, oi Jarvis ou bater as duas palmas" (12/11). O Jarvis respondeu que precisa ficar em escuta ativa; o Lucas: "Pode continuar assim, então." | **Pendente.** Exige um detector local de palavra de ativação |
| D-029 | "você pode se basear no Windguru, tá? É muito importante que você aprenda a ler previsões de vento, de mar, de maré" (04/11) | **Pendente e perdido.** Não está na memória nem no código |
| D-030 | "eu deixo todos os áudios rolando, você escuta e não responde nada, apenas processa" (12/11) | **Parcial.** A persona manda ouvir quando ele pede; não há modo de escuta passiva testado |

## 3. Confirmações de 16/11/2026 (decisões antes sem fala literal)
Estes itens já existiam no código ou na memória, mas sem a fala literal da decisão. O Lucas respondeu em 16/11/2026, por escrito, ao Claude Code. **Fonte de todas:** resposta escrita do Lucas, 16/11/2026. São confirmações de hoje sobre escolhas passadas, não falas da época. A fala está copiada como ele escreveu; só foram corrigidos erros de digitação que não mudam o sentido.

### C-01 · Interface de vidro com widgets (05/11)
**Fala:** "Queria uma interface mais limpa, com design profissional e leve, que fosse facilmente editável, caso eu quisesse adicionar, remover, corrigir e rolar pra cima e para baixo. Como uso mac, me identifico com a UI do mac e trabalho melhor dessa forma. O design limpo e estética minimalista facilita minha interação com o software do jarvis."
**Leitura:** critérios de design: leveza, aparência de app do macOS e edição direta na interface.
**Estado:** Confirmada.

### C-02 · Agenda própria do Jarvis (`calendario.json`)
**Fala:** "Porque eu utilizo o recurso de voz para o jarvis para acrescentar, remover, editar e realocar tarefas no meu calendário, fazendo a conferência diária do que foi feito e o que não foi feito, e o porquê. O sistema de agente autônomo do jarvis me permite ter a praticidade de ter um calendário perfeito, sem que eu precise editá-lo manualmente. E o mais importante, esse calendário dentro da interface do jarvis é o mesmo calendário do google calendar, integrando tudo em uma interface só."
**Leitura:** a agenda é do Jarvis porque é editada por voz, com conferência diária.
**Divergência com o código:** `agenda.py` e `rotas_agenda.py` gravam só em `calendario.json` local; não há sincronização com o Google Calendar no código [levantado: 16/11/2026]. A integração com o Google Calendar é intenção do Lucas, não estado atual. Ver H-10.
**Correção (16/11/2026, reescrita pelo Lucas a partir de sugestão do Claude, depois de conferir o código):** "Escolhi ter a agenda no jarvis porque me facilita muito com a minha organização pessoal e controle dos meus objetivos. Todo dia à noite entro na plataforma, falo com o jarvis e destrinchamos juntos como foi o meu dia, quais tarefas foram cumpridas, quais não foram e como vamos realocar elas ao longo da semana. Tudo é discutido por voz, sem necessidade de alteração manual. O jarvis faz tudo isso com o comando por voz. Eu achava que o calendário interativo do jarvis estava integrado com o google calendar. Realizar essa integração fica como objetivo para uma próxima versão."
**Estado:** Confirmada: agenda própria do Jarvis, editada por voz, com revisão diária à noite. A integração com o Google Calendar é objetivo futuro (H-10, P-14).

### C-03 · Projetos com fontes e leitura diária de sites
**Fala:** "Isso resolve o problema direto de alguém que quer se envolver mais em política, mas pelo jornal e notícias diárias não consegue acompanhar ou entender muito bem o que está acontecendo. O jarvis entra exatamente como esse facilitador, uma ferramenta capaz de ler as notícias e me explicar por voz tudo o que aconteceu. No momento em que eu não entender algo, precisar de ajuda, alguma lei ou termo técnico, ele me entrega essa resposta mastigada e explicada, em questão de segundos. Ou seja, o JARVIS também funciona como um "professor" para qualquer assunto. Isso não só com política, ele pode ser um professor autônomo de qualquer idioma estrangeiro que eu queira aprender, um assistente de negócios, identificando oportunidades, ameaças e me explicando termos técnicos de business por exemplo. É um agente multifuncional. Ele aprende constantemente com base nas referências dadas, documentos e preferências do usuário ao longo do tempo."
**Leitura:** o caso de uso real é acompanhar notícias (projeto "Geopolítica e Brasil") com explicação por voz. Idiomas e assistente de negócios são extensões imaginadas, não testadas.
**Precisão técnica:** "aprende constantemente" quer dizer memória em arquivos e fontes por projeto; o modelo não é treinado nem ajustado [levantado: 16/11/2026, `vault.py`, `projects.py`].
**Estado:** Confirmada (notícias). Idiomas e negócios: hipótese H-11.

### C-04 · Studio próprio em vez do conector do NotebookLM
**Fala:** "Construir o próprio Studio veio da vontade de integrar tudo dentro de uma plataforma só. O studio é uma ferramenta criada para o jarvis onde ele tem uma aba que é mais focada e organizada para estudos. Diferente da página inicial que é voltada para projetos mais rápidos, soluções imediatas, dúvidas, integrações no calendário, etc; enquanto o studio é uma extensão do jarvis onde ele funciona como uma plataforma de estudo, que é organizada e dividida pelos projetos (criados na página inicial)."
**Leitura:** o motivo é a integração numa plataforma só, não o controle técnico. Divisão de papéis: página inicial para o imediato; Studio para o estudo, organizado pelos mesmos projetos.
**Estado:** Confirmada. Fecha H-09.

### C-05 · Git só com código; dados pessoais fora
**Fala:** "Sim, para tornar o jarvis uma ferramenta pública, é ideal que as minhas informações pessoais sejam removidas, para que o usuário que for instalar esse repositório não tenha acesso aos meus dados e para que ele possa editar e criar seus próprios projetos dentro da ferramenta, permitindo que seja um modelo que se adapta ao usuário, não o contrário."
**Efeito:** `.gitignore`; dados no `config.json` e no cofre de cada usuário; `config.example.json` e `examples/vault-minimal/` [levantado: 16/11/2026].
**Estado:** Confirmada.

### C-06 · Ollama `qwen3:8b` como plano B
**Fala:** "Sim, ter o Ollama de reserva funciona como um "plano b", caso o limite de uso da voz do gemini estoure ou tenha alguma falha. Costuma durar bastante e não tenho problemas no software quanto a voz do jarvis. O Ollama serve como um reserva, mas por questões de segurança para que o Jarvis não falhe."
**Divergência com o código:** o Ollama é reserva só para tarefas de **texto** (leitura de páginas, PDFs, resumos), quando todos os modelos Gemini REST falham (`gem.py`). A **voz** não tem reserva: se o Gemini Live cair, a conversa por voz para [levantado: 16/11/2026].
**Correção (16/11/2026, reescrita pelo Lucas a partir de sugestão do Claude, depois de conferir o código):** "O Ollama é a reserva das tarefas de texto, não da voz. Mantenho porque assim o Jarvis continua lendo e resumindo mesmo quando o Gemini falha. A voz depende só do Gemini Live, e aceito esse risco por enquanto, porque na prática ela raramente cai."
**Medição [levantado: 16/11/2026, `jarvis.log`]:** o log registra 1.130 fechamentos da sessão do Gemini Live entre 03 e 16/11, 1.031 deles com código 1008, e o servidor reconecta sozinho com o handle de retomada. Quantos desses fechamentos o Lucas percebeu como queda não foi medido. "Raramente cai" é a percepção de uso dele (H-12).
**Estado:** Confirmada: Ollama como plano B de texto; voz sem reserva, risco aceito (P-15).

### C-07 · Cota gratuita do Gemini
**Fala:** "Continuar gratuito, pois pelo o que eu utilizo dele (que é muito) esse formato funciona e não vejo a necessidade de uma assinatura paga para isso. O jarvis dá conta do modelo gratuito com folga."
**Medição [levantado: 16/11/2026, `jarvis.log`, só linhas com data]:** erros 429 (cota) por dia: 05/11: 30 · 10/11: 93 (modo curso) · 11/11: 13 · 13/11: 4 · 14 a 16/11: 0. Erros 503 (serviço indisponível do Google, que pagar não resolve): 05/11: 10 · 10/11: 53 · demais dias: 1 a 4.
**Correção (16/11/2026, reescrita pelo Lucas a partir de sugestão do Claude, depois de conferir o código):** "Para utilização do dia a dia, o plano gratuito dá conta. O limite estourou em dias de uso pesado, como no modo curso em 10/11. Continuo no gratuito e reavalio pagar se os erros de cota voltarem a atrapalhar o uso normal, por exemplo mais de dois dias por semana."
**Estado:** Confirmada: continuar no gratuito. Gatilho para reavaliar: erros de cota atrapalhando o uso normal em mais de dois dias por semana.

### C-08 · Certificado local fixo de assinatura
**Fala:** "Sim."
**Estado:** Confirmada.

### C-09 · Atualização automática do Atticus desligada
**Fala:** "Sim. Atualizando à mão evita bugs no sistema do jarvis e é mais prático, permitindo mais fluidez e agilidade entre as duas ferramentas."
**Estado:** Confirmada.

### C-10 · Só o Caveman no Claude Code
**Fala:** "Depois de testes com os dois repositórios, o caveman é mais eficiente, mais simples e traz um resultado superior ao RTK. Por isso, tendo dois repositórios ativos com a mesma funcionalidade (economia de tokens) não faz sentido. Por esse motivo, sugeri ao claude code utilizar somente o caveman, para evitar confusões entre os repositórios e retrabalho."
**Leitura:** decisão do ambiente de desenvolvimento, não do Jarvis em si. A memória registra também outro motivo: o filtro de saída do RTK atrapalhava achar erros [relatado: memória do projeto, 13/11].
**Estado:** Confirmada.

### C-11 · Escrita atômica, fila de saída e reconexão
**Fala:** "Sim"
**Estado:** Confirmada como padrão do projeto.

### C-12 · Sessão de 07/11 que pedia "integre a API Live do Gemini"
**Fala:** "Não lembro. Provavelmente foi uma solicitação que eu me enganei e não dei sequência. Provavelmente foi quando estava criando o studio no jarvis."
**Estado:** Encerrada sem decisão. Explicação provável, não confirmada.

## 4. Reversões
| Decisão original | Revertida por | Quando |
|---|---|---|
| D-002 sem plataforma externa | D-003 voz pelo Gemini Live | 03/11 |
| Voz do Mac pelo Atticus | D-003 | 03/11 |
| App próprio de on/off do Atticus (criado 04/11) | o app original já tinha o botão (D-009) | 04/11 13:34 |
| D-015 "banco de dados externo" | índice SQLite local `[proposta]` | 11/11 |
| H-09 "Studio dá mais controle" | o motivo real é integração numa plataforma só (C-04) | 16/11 |

## 5. Hipóteses abertas
| ID | Hipótese | Como e quando confirmar |
|---|---|---|
| H-01 | 100 ms de silêncio a cada 30 s mantêm a sessão aberta com o Gemini mudo | Mutar por 3 min e rodar `grep "Gemini closed" jarvis.log \| tail`: não deve haver "1008" nesse intervalo |
| H-02 | O Claude obedece à nota "faça agora" do Atticus em vez de prometer | Pedir um diagnóstico por `executar_no_mac`; esperado: resultado, ou erro "Não concluído" |
| H-03 | A postura de assessor funciona na voz real | Em 5 ideias, contar em quantas ele aponta o ponto fraco sem "entendido" |
| H-04 | O plano gratuito basta para o uso normal (C-07) | Contar erros 429 por dia no `jarvis.log` toda semana; reavaliar pagar se passarem de dois dias por semana atrapalhando o uso normal |
| H-05 | 1,5x é a velocidade mais rápida do modo curso sem perda | Comparar 1x, 1,5x e 2x na mesma aula (só 1x e 2x foram comparados) |
| H-06 | Instruções menores melhoram as respostas | A/B com `run.sh --check` e uma semana de uso |
| H-07 | O Jarvis economiza horas reais de trabalho | Criar `METRICAS.md` com medições do `jarvis.log` e das transcrições |
| H-08 | O detector de afirmações cobre as mentiras reais | Rodar o detector sobre as transcrições de 03 a 16/11 e contar falsos negativos |
| H-10 | A agenda do Jarvis pode ser a mesma do Google Calendar (C-02) | Hoje não há sincronização no código; exige integração nova e teste: criar uma tarefa por voz e vê-la no Google Calendar |
| H-12 | A voz raramente cai do ponto de vista do usuário, apesar dos fechamentos de sessão no log (C-06) | Cruzar os "Gemini closed" do `jarvis.log` com as transcrições: contar quantos interromperam uma conversa |
| H-11 | O Jarvis serve como professor de idiomas e assistente de negócios (C-03) | Usar um projeto de idioma e um de negócios por uma semana e registrar o resultado |

## 6. Aprendizados (com evidência)
- **L-01.** Modelos afirmam trabalho que não fizeram. A causa estava no prompt do Atticus ("agente em segundo plano" não existe pela linha de comando), não numa "alucinação" genérica. Corrigir a causa, não o sintoma. [relatado: relatório da noite de 13/11] · [levantado: 16/11/2026, `NOT_DONE` em `server.py`]
- **L-02.** Verificar o que já existe antes de construir. Em 04/11 foi criado um app de on/off do Atticus que já existia. (D-009)
- **L-03.** Palavras ambíguas geram erro silencioso: "Notas" foi parar no Obsidian em vez do widget. A regra entrou na persona. (D-017)
- **L-04.** O macOS exige reiniciar o app depois de conceder Gravação de Tela, e assinatura estável para a permissão não cair a cada compilação. [levantado: 16/11/2026, `app/build.sh`]
- **L-05.** No Gemini Live, imagem junto do texto em `clientContent` funciona; PDF em `inlineData` derruba a conexão (1007). [levantado: 16/11/2026, `anexos_chat.py`]
- **L-06.** O Chrome só toca vídeo com som depois de um clique real, e não inicia vídeo em página escondida; o Mac dorme com a tampa fechada. [relatado: plano do modo curso]
- **L-07.** Depender do acesso a um serviço de terceiros é frágil: o curso parou em 27 de 84 aulas. O conhecimento extraído ficou em texto. (D-012, D-014)
- **L-08.** A conversa do dia volta inteira à sessão seguinte, inclusive as falas inventadas do Jarvis, que viram exemplo do que fazer. [relatado: relatório da noite de 13/11] (H-06)
- **L-09.** O que o assistente diz sobre si mesmo não é evidência. Em 16/11 o Jarvis listou "Docker, LLMs locais" como stack. O código mostra que a voz é na nuvem. [levantado: 16/11/2026]
- **L-10.** O reconhecimento de voz erra o nome do assistente ("chaves", "Javes"), e o Jarvis chegou a responder "chaves de API?". [levantado: 16/11/2026, transcrições de 11/11 e 13/11]
