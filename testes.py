"""Testes de fumaça do Jarvis: rode antes de reiniciar o app depois de mexer no código.

    .venv/bin/python testes.py

Rodam numa pasta temporária: config.json, cofre (copiado de examples/vault-minimal), agenda, notas e projetos (copiado
de tests/fixtures) são de teste. Não tocam nos seus dados e não chamam o Gemini nem o Claude.
"""
import asyncio
import contextlib
import inspect
import json
import os
import subprocess
import pathlib
import sys
import types

import shutil  # noqa: E402
import tempfile  # noqa: E402

os.environ["GEMINI_API_KEY"] = "teste"   # nunca usa a chave real nem o Keychain
AQUI = pathlib.Path(__file__).resolve().parent
TMP = pathlib.Path(tempfile.mkdtemp(prefix="jarvis-testes-"))
shutil.copytree(AQUI / "examples/vault-minimal", TMP / "cofre")
(TMP / "config.json").write_text(json.dumps({"user_name": "Ana", "vault": str(TMP / "cofre")}))
os.environ["JARVIS_CONFIG"] = str(TMP / "config.json")   # antes de importar os módulos: eles leem o config ao carregar
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

import aiohttp  # noqa: E402
import core  # noqa: E402
import research  # noqa: E402
import server  # noqa: E402
import trabalho  # noqa: E402
import agenda  # noqa: E402
import atexit  # noqa: E402
import busca  # noqa: E402
import notas  # noqa: E402
import notebook  # noqa: E402
import projects  # noqa: E402

# Os dados que ficam ao lado do código também vão para a pasta temporária, com o projeto de exemplo.
shutil.copytree(AQUI / "tests/fixtures/projeto-exemplo", TMP / "projetos/projeto-exemplo")
projects.ROOT = busca.PROJETOS = TMP / "projetos"
notebook.COLLECTIONS = TMP / "projetos/colecoes.json"
busca.DB = TMP / "busca.db"
agenda.FILE, notas.FILE = TMP / "calendario.json", TMP / "notas.json"
core.UPLOADS = server.UPLOADS = TMP / "arquivos"
atexit.register(shutil.rmtree, TMP, ignore_errors=True)

PY = sys.executable
ok = 0


def check(cond, what):
    global ok
    if not cond:
        sys.exit(f"FALHOU: {what}")
    ok += 1


def sintaxe():
    """Nenhum .py com SyntaxWarning (ex.: duas strings separadas por \\ seguidas de parênteses viram uma chamada)."""
    arquivos = sorted(str(p) for p in core.HERE.glob("*.py"))
    r = subprocess.run([PY, "-W", "error::SyntaxWarning", "-c",
                        "import sys\nfor f in sys.argv[1:]: compile(open(f, encoding='utf-8').read(), f, 'exec')", *arquivos],
                       capture_output=True, text=True)
    check(r.returncode == 0, "aviso de sintaxe: " + r.stderr[-300:])


def selftests():
    """Os autotestes que já existem dentro dos módulos."""
    for mod in ("busca.py", "sources.py", "notebook.py", "notas.py", "agenda.py"):
        r = subprocess.run([PY, mod], capture_output=True, text=True)
        check(r.returncode == 0, f"autoteste de {mod}: {r.stderr[-300:]}")


def voice_tools():
    """Toda ferramenta que o Gemini conhece tem quem a execute (e vice-versa não sobra nome solto)."""
    code = inspect.getsource(server.Session)
    for f in server.FUNCTIONS:
        check(f'name == "{f["name"]}"' in code, f"ferramenta {f['name']} sem tratamento na Session")
    setup = server.setup_message("Charon")["setup"]
    text = setup["systemInstruction"]["parts"][0]["text"]
    check(1000 < len(text) < 200_000, f"instrução de sistema com {len(text)} caracteres")


def honestidade():
    """Falas reais de 12/11 em que o Jarvis disse que trabalhava sem nenhuma ferramenta rodando, e falas normais."""
    mentiras = ["Já estou rodando esse diagnóstico completo da arquitetura em segundo plano para identificar as melhorias.",
                "Compreendido, Lucas. Vou conduzir essa análise cirúrgica em silêncio e, na sequência, preparo o prompt.",
                "Garanto que a análise detalhada da arquitetura continua correndo em segundo plano.",
                "Entendido, Lucas. Vou continuar a análise a fundo e te aviso no chat assim que tudo estiver pronto.",
                "Estou finalizando o diagnóstico da arquitetura para garantir que as melhorias funcionem.",
                "Entendido, Lucas. Finalizei o diagnóstico e já preparei o prompt para o Claude Code.",
                "Com base na nossa análise, estruturei o prompt para o Claude Code com todas as exigências.",
                "Entendido, Lucas. Já incorporei todas as suas observações ao novo prompt estruturado."]
    for frase in mentiras:
        check(server.unbacked_claim(frase, busy=False, tool_recently=False), f"não pegou a afirmação sem ferramenta: {frase}")
    normais = ["Ouvi sim. A Flávia destacou os riscos de cursos vocacionais para quem já tem graduação.",
               "Estou ouvindo perfeitamente, Lucas. Pode falar.", "Pois não, Lucas. Estou acompanhando.",
               "Ainda não terminei, Lucas.", "Não terminei nada, desculpe.", "Você terminou o curso?",
               # respostas honestas que a PERSONA manda dar (achadas na revisão)
               "Não, nenhuma tarefa está em andamento agora.", "Nada está em andamento.",
               "Sozinho eu não consigo fazer isso em segundo plano, mas posso pedir ao Claude.",
               "Eu não tenho como rodar nada em segundo plano.", "Concluí que a melhor opção é o curso de inglês."]
    for frase in normais:
        check(server.unbacked_claim(frase, busy=False, tool_recently=False) is None, f"acusou fala normal: {frase}")
    # com a ferramenta rodando (ou recém-terminada) as mesmas frases são verdade
    check(server.unbacked_claim("Tô pesquisando, te aviso assim que terminar.", busy=True, tool_recently=True) is None,
          "acusou aviso de tarefa que está rodando")
    check(server.unbacked_claim("Pronto, terminei a pesquisa.", busy=False, tool_recently=True) is None,
          "acusou resultado de ferramenta recém-terminada")
    check("HONESTIDADE" in server.PERSONA, "regra de honestidade fora da PERSONA")


@contextlib.contextmanager
def trocar(obj, nome, valor):
    """Troca obj.nome por valor durante o bloco (para não chamar nada de fora)."""
    real = getattr(obj, nome)
    setattr(obj, nome, valor)
    try:
        yield
    finally:
        setattr(obj, nome, real)


def processo_falso(saida, sent):
    """Um create_subprocess_exec que não roda nada: o processo só imprime `saida`. Guarda os argumentos em `sent`."""
    async def fake_exec(*args, **kw):
        sent["args"], sent["kw"] = args, kw
        stdout = asyncio.StreamReader(limit=kw.get("limit", 2 ** 16))   # o mesmo limite de linha do processo de verdade
        stdout.feed_data(saida.encode())
        stdout.feed_eof()
        stderr = asyncio.StreamReader()
        stderr.feed_eof()

        async def wait():
            return 0
        return types.SimpleNamespace(returncode=0, stdout=stdout, stderr=stderr, wait=wait, kill=lambda: None)
    return fake_exec


async def atticus():
    """executar_no_mac: a tarefa vai com o pedido de resultado na hora, um 'iniciei em segundo plano' vira erro,
    e cada passo '▸' do Atticus chega como progresso. (Com o Atticus fingido: o processo é falso, então vale sem ele.)"""
    with trocar(server, "has_executor", lambda: True):
        await _atticus()


async def _atticus():
    sent, passos = {}, []

    async def prog(texto):
        passos.append(texto)
    saida = ("▸ Reading front-window summary\n✓ Iniciei o diagnóstico da arquitetura do Jarvis em segundo plano. "
             "Ele vai cobrir processamento local.\n")
    with trocar(asyncio, "create_subprocess_exec", processo_falso(saida, sent)):
        r = await server.run_task("Faça um diagnóstico do Jarvis", 5, prog)
    check(sent["args"][2].startswith("Faça um diagnóstico do Jarvis") and "resultado final" in sent["args"][2],
          "a tarefa foi ao Atticus sem o pedido de resultado na hora")
    check("error" in r and "Não concluído" in r["error"], f"'segundo plano' do Claude passou como feito: {r}")
    check(passos == ["Claude: Reading front-window summary"], f"passos do Atticus: {passos}")
    with trocar(asyncio, "create_subprocess_exec", processo_falso("▸ Opening Spotify\n✓ Abri o Spotify.\n", sent)):
        r = await server.run_task("abre o spotify", 5)
    check(r == {"result": "Abri o Spotify."}, f"resultado normal do Atticus mudou: {r}")
    # respostas reais do Atticus desde 03/11 que falam em segundo plano: só as três promessas sem trabalho são erro
    promessas = ["Passei a tarefa para um agente em segundo plano. Ele vai achar o projeto do Jarvis.",
                 "Iniciei uma auditoria completa do Jarvis em segundo plano. Ela vai olhar bugs, latência.",
                 "Iniciei o diagnóstico da arquitetura do Jarvis em segundo plano. Ele vai cobrir processamento local."]
    resultados = ["Reiniciei o Claude Code: fechei o app Claude e abri de novo em segundo plano.",
                  "Pronto, o Insomnia está rodando em segundo plano.",
                  "Quando uma tarefa é longa, com muitos passos ou várias fontes, o Atticus a entrega a um agente em segundo plano."]
    for frase in promessas:
        check(server.LATER.search(frase), f"promessa de segundo plano passou: {frase}")
    for frase in resultados:
        check(not server.LATER.search(frase), f"resultado de verdade virou 'não concluído': {frase}")


async def pesquisa():
    """A pesquisa mostra cada passo do Claude enquanto acontece e devolve o resultado como antes."""
    final = {"titulo": "Dólar", "fala": "O dólar fechou a 5,51.", "resposta": "## Conclusão\nR$ 5,51 [1]",
             "fontes": [{"titulo": "InfoMoney", "url": "https://www.infomoney.com.br/x"}]}
    eventos = [{"type": "system", "subtype": "init"},
               {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch", "input": {"query": "dólar hoje"}}]}},
               {"type": "user", "message": {"content": [{"type": "tool_result", "content": "x" * 200_000}]}},   # linha > 64 KB
               {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebFetch",
                                                              "input": {"url": "https://www.infomoney.com.br/x"}}]}},
               {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
               {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(final)}]
    sent, passos = {}, []

    async def prog(texto):
        passos.append(texto)
    with trocar(asyncio, "create_subprocess_exec", processo_falso("".join(json.dumps(e) + "\n" for e in eventos), sent)):
        r = await research.research("Quanto está o dólar?", "rapida", {}, prog)
    check(r.get("fala") == final["fala"] and r["fontes"] == final["fontes"], f"resultado da pesquisa mudou: {r}")
    check(passos == ["Pesquisando: dólar hoje", "Comparando o que achou: 1 busca, 0 fontes lidas",
                     "Lendo infomoney.com.br (1ª fonte)", "Comparando o que achou: 1 busca, 1 fonte lida"], f"passos: {passos}")
    check(sent["kw"].get("stdin") == asyncio.subprocess.DEVNULL, "o claude da pesquisa esperaria o stdin por 3 s")
    check('{"disableAllHooks": true}' in sent["args"], "a pesquisa rodaria com os hooks pessoais do usuário")


def sessao_falsa():
    """Uma Session com a janela e o Gemini trocados por gravadores; nada sai do processo."""
    para_tela, para_gemini = [], []

    class Janela:
        closed = False

        async def send_json(self, m):
            para_tela.append(m)

    class Gemini:
        closed = False

        async def send_str(self, s):
            para_gemini.append(json.loads(s))

    s = server.Session({"http": None, "key": "teste", "jobs": set(), "rec": {}}, Janela())
    s.gemini = Gemini()
    return s, para_tela, para_gemini


async def texto_na_tela():
    """mostrar_texto põe o texto inteiro, sem cortes, no chat, e a conversa segue (a resposta volta ao Gemini)."""
    s, tela, gemini = sessao_falsa()
    real, server.log_turn = server.log_turn, lambda *a: None   # não escreve no cofre
    try:
        texto = "# Prompt para o Claude Code\n\n1. Leia o server.py\n2. Corrija o mudo\n" + "Detalhe importante.\n" * 400
        await s.on_tool({"name": "mostrar_texto", "id": "1", "args": {"titulo": "Prompt", "texto": texto}})
    finally:
        server.log_turn = real
    docs = [m for m in tela if m["type"] == "document"]
    check(len(docs) == 1 and docs[0]["text"] == texto.strip(), "o texto não chegou inteiro à tela")
    resposta = gemini[-1]["toolResponse"]["functionResponses"][0]
    check(resposta["name"] == "mostrar_texto" and "result" in resposta["response"], f"resposta errada ao Gemini: {resposta}")
    check("mostrar_texto" in server.PERSONA, "a PERSONA não manda usar mostrar_texto")
    check(not [m for m in tela if m["type"] == "busy"], "ferramenta instantânea fez o reator piscar roxo")


async def roxo():
    """Ferramenta demorada: a tela recebe 'executando' com o texto, cada passo, e o fim, mesmo quando ela falha no meio."""
    s, tela, _ = sessao_falsa()

    async def pesquisa_que_cai(pergunta, profundidade, env, progress=None):
        await progress("Pesquisando: dólar hoje")
        raise RuntimeError("caiu a rede")
    with trocar(server.research, "research", pesquisa_que_cai), trocar(server, "log_turn", lambda *a: None), \
            trocar(server, "log", lambda *a: None), \
            trocar(server, "switches", lambda: {"vision": True, "internet": True, "actions": True}):
        await s.on_tool({"name": "pesquisar_web", "id": "7", "args": {"pergunta": "dólar", "profundidade": "rapida"}})
    busy = [m for m in tela if m["type"] == "busy"]
    check([m["text"] for m in busy] == ["Pesquisando: dólar", "Pesquisando: dólar hoje", None] and busy[-1]["done"],
          f"mensagens de executando: {busy}")
    check(not s.running, "a ferramenta ficou marcada como rodando depois de falhar")


async def mudo():
    """Mutar (F5, botão, palmas) só para o microfone: a sessão segue aberta e, enquanto mudo, o Gemini recebe um pouco de
    silêncio para não fechar por inatividade (1008) no meio de uma tarefa; ao desmutar, o silêncio para."""
    s, tela, gemini = sessao_falsa()
    pedidos = [{"type": "audio_end"}, {"type": "mute", "on": True}]

    class Janela:
        closed = False

        async def send_json(self, m):
            tela.append(m)

        async def __aiter__(self):
            for p in pedidos:
                yield types.SimpleNamespace(type=aiohttp.WSMsgType.TEXT, data=json.dumps(p))
    s.browser = Janela()
    with trocar(server, "KEEPALIVE_EVERY", 0.01):
        await s.browser_loop()
        await asyncio.sleep(0.05)
        silencio = [g for g in gemini if g.get("realtimeInput", {}).get("audio", {}).get("data") == server.SILENCE]
        check(s.muted and not s.closed and silencio, "mudo fechou a sessão ou não manteve o Gemini acordado")
        s.muted = False
        await asyncio.sleep(0.03)
        check(s.keepalive is None, "o silêncio continuou depois de desmutar")


async def raciocinio():
    """O raciocínio do modelo entre asteriscos (12/11 20:19) não chega ao chat nem à transcrição, mesmo cortado em pedaços."""
    s, tela, _ = sessao_falsa()
    pedacos = ["*The user is ques", "tioning the previous response about \"chaves\". I need to ask", " for clarification.*Você menc",
               "ionou \"chaves\", e não ficou claro."]
    for p in pedacos:
        await s.on_gemini({"serverContent": {"outputTranscription": {"text": p}}})
    texto = "".join(m["text"] for m in tela if m["type"] == "model_text")
    check(texto == 'Você mencionou "chaves", e não ficou claro.', f"raciocínio vazou: {texto!r}")
    check(s.model_text == texto, "a transcrição guardada ficou diferente do chat")
    f = server.ThoughtFilter()
    check(f("Custa R$ 5,51 hoje.") == "Custa R$ 5,51 hoje.", "fala normal alterada")
    f("*um asterisco solto")
    f.reset()
    check(f("Próximo turno aparece.") == "Próximo turno aparece.", "asterisco solto escondeu o turno seguinte")


def interrupcao():
    """O interruptor 'interrupcao' do config.json: sem ele, o Gemini recebe exatamente a configuração de antes."""
    antes = {"automaticActivityDetection": {"startOfSpeechSensitivity": "START_SENSITIVITY_LOW"}}
    for modo, esperado in ((None, antes), ("normal", antes),
                           ("firme", {"automaticActivityDetection": {"startOfSpeechSensitivity": "START_SENSITIVITY_LOW",
                                                                     "prefixPaddingMs": 400}}),
                           ("nunca", {**antes, "activityHandling": "NO_INTERRUPTION"})):
        cfg = {k: v for k, v in core.settings().items() if k != "interrupcao"}
        if modo:
            cfg["interrupcao"] = modo
        with trocar(server, "settings", lambda: cfg):
            got = server.setup_message("Charon")["setup"]["realtimeInputConfig"]
        check(got == esperado, f"interrupcao={modo}: {got}")


async def afirmacao_na_sessao():
    """Fim de turno: mentira de 12/11 gera aviso na tela e pedido de correção (uma vez só); 'terminei' minutos depois de
    uma pesquisa que deu certo não é acusado."""
    with trocar(server, "log_talk", lambda *a: None), trocar(server, "log", lambda *a: None):   # nada gravado
        await _afirmacao_na_sessao()


async def _afirmacao_na_sessao():
    s, tela, gemini = sessao_falsa()
    await s.on_gemini({"serverContent": {"outputTranscription": {"text": "Finalizei o diagnóstico e já preparei o prompt."}}})
    await s.on_gemini({"serverContent": {"turnComplete": True}})
    avisos = [m for m in tela if m["type"] == "warning"]
    pedidos = [g for g in gemini if "[sistema] Você acabou de dizer" in g.get("realtimeInput", {}).get("text", "")]
    check(len(avisos) == 1 and len(pedidos) == 1, f"mentira sem aviso/correção: {avisos} {pedidos}")
    await s.on_gemini({"serverContent": {"outputTranscription": {"text": "Desculpe, Lucas, eu não terminei nada; já finalizei errado."}}})
    await s.on_gemini({"serverContent": {"turnComplete": True}})
    check(len([m for m in tela if m["type"] == "warning"]) == 1, "a fala de correção foi acusada de novo (laço)")
    s2, tela2, _ = sessao_falsa()
    s2.last_work = server.time.time() - 600   # uma pesquisa deu certo há 10 minutos
    await s2.on_gemini({"serverContent": {"outputTranscription": {"text": "Terminei a pesquisa: o visto sai em 25 dias."}}})
    await s2.on_gemini({"serverContent": {"turnComplete": True}})
    check(not [m for m in tela2 if m["type"] == "warning"], "acusou o relato de uma pesquisa real")
    # "tô pesquisando" dito no mesmo turno em que a ferramenta rodou é verdade
    s3, tela3, _ = sessao_falsa()
    with trocar(server, "log_turn", lambda *a: None):
        await s3.on_tool({"name": "mostrar_texto", "id": "9", "args": {"titulo": "x", "texto": "y"}})
    s3.tool_since_user = False   # o usuário falou de novo, mas o turno do Jarvis é o mesmo
    await s3.on_gemini({"serverContent": {"outputTranscription": {"text": "Tô pesquisando aqui, já te falo."}}})
    await s3.on_gemini({"serverContent": {"turnComplete": True}})
    check(not [m for m in tela3 if m["type"] == "warning"], "acusou fala dita no turno da ferramenta")
    # fim de um vídeo assistido em segundo plano: o relato é verdade
    s4, tela4, _ = sessao_falsa()
    await s4.notify("[sistema] Terminei de assistir 'Aula 3'.")
    await s4.on_gemini({"serverContent": {"outputTranscription": {"text": "Terminei de assistir a aula 3."}}})
    await s4.on_gemini({"serverContent": {"turnComplete": True}})
    check(not [m for m in tela4 if m["type"] == "warning"], "acusou o aviso de vídeo assistido")


async def trabalho_longo():
    """trabalho_longo volta na hora, mostra cada passo do Claude no reator, e no fim põe o texto no chat, grava a nota e
    avisa o Jarvis; falha e cancelamento dizem que não foi feito; o Claude só lê (sem Bash, Edit nem Write)."""
    s, tela, gemini = sessao_falsa()
    app = {"sessions": {s}, "jobs": set(), "trabalho": {}}
    s.app = app
    notas = []
    cofre = types.SimpleNamespace(root=pathlib.Path("/cofre"),
                                  write_note=lambda *a, **k: (notas.append(a), (pathlib.Path("/cofre/07/x.md"), "created"))[1])
    final = "FALA: O Jarvis perde a sessão a cada dois minutos.\n\n## Conclusão\nTrês gargalos.\n- server.py:665"
    eventos = [{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read",
                                                               "input": {"file_path": "/Users/x/Desktop/jarvis-voz/server.py"}}]}},
               {"type": "user", "message": {"content": [{"type": "tool_result", "content": "y" * 100_000}]}},
               {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch",
                                                               "input": {"query": "gemini live 1008"}}]}},
               {"type": "result", "subtype": "success", "is_error": False, "result": final}]
    sent = {}
    pedido = {"tarefa": "Faça um diagnóstico do código do Jarvis", "titulo": "Diagnóstico do Jarvis"}
    with trocar(asyncio, "create_subprocess_exec", processo_falso("".join(json.dumps(e) + "\n" for e in eventos), sent)), \
            trocar(trabalho, "VAULT", cofre), trocar(trabalho, "log_turn", lambda *a: None):
        r = await trabalho.tool(app, pedido)
        check("result" in r and app["trabalho"].get("titulo") == "Diagnóstico do Jarvis", f"não começou: {r}")
        check("error" in await trabalho.tool(app, pedido), "dois trabalhos longos ao mesmo tempo")
        check("Rodando" in (await trabalho.tool(app, {"acao": "status"}))["result"], "status não viu o trabalho rodando")
        await app["trabalho"]["task"]
    passos = [m["text"] for m in tela if m["type"] == "busy" and m["id"] == "trabalho" and m["text"]]
    check(passos == ["Trabalho longo: Diagnóstico do Jarvis", "Lendo server.py", "Pesquisando: gemini live 1008"], f"passos: {passos}")
    check(tela[-2:-1] and [m for m in tela if m["type"] == "busy"][-1]["done"], "o reator ficaria roxo depois do fim")
    docs = [m for m in tela if m["type"] == "document"]
    check(len(docs) == 1 and docs[0]["text"] == "## Conclusão\nTrês gargalos.\n- server.py:665", f"texto no chat: {docs}")
    aviso = gemini[-1]["realtimeInput"]["text"]
    check("perde a sessão a cada dois minutos" in aviso and "07/x.md" in aviso, f"aviso ao Jarvis: {aviso}")
    check(len(notas) == 1 and s.last_work > 0 and not app["trabalho"], "sem nota, sem trabalho registrado, ou estado preso")
    ferramentas = sent["args"][sent["args"].index("--tools") + 1]
    check(not {"Bash", "Edit", "Write"} & set(ferramentas.split(",")), f"o Claude poderia mudar coisas: {ferramentas}")
    a = list(sent["args"])
    aprovadas = a[a.index("--allowedTools") + 1:a.index("--add-dir")]
    check(aprovadas == ["WebSearch", "WebFetch"] and a[a.index("--add-dir") + 1] == core.settings()["vault"]
          and sent["kw"]["cwd"] == str(core.HERE), f"leitura liberada fora do código e do cofre: {a}")
    check(sent["kw"].get("stdin") == asyncio.subprocess.DEVNULL and '{"disableAllHooks": true}' in sent["args"],
          "stdin aberto ou hooks pessoais ligados")
    check("Nenhum" in (await trabalho.tool(app, {"acao": "status"}))["result"], "status depois do fim")

    # Falha: o Jarvis ouve que NÃO foi concluído, e isso não conta como trabalho feito.
    s.last_work, gemini[:] = 0.0, []
    erro = [{"type": "result", "subtype": "error_max_turns", "is_error": True, "result": ""}]
    with trocar(asyncio, "create_subprocess_exec", processo_falso(json.dumps(erro[0]) + "\n", {})), \
            trocar(trabalho, "VAULT", cofre), trocar(trabalho, "log_turn", lambda *a: None):
        await trabalho.tool(app, pedido)
        await app["trabalho"]["task"]
    check("NÃO foi concluído" in gemini[-1]["realtimeInput"]["text"] and s.last_work == 0.0, "falha contada como feita")

    # Cancelar: o processo morre, o reator apaga, e o estado limpa.
    mortos = []

    async def preso(*args, **kw):
        out, err = asyncio.StreamReader(), asyncio.StreamReader()

        async def wait():
            return -9
        return types.SimpleNamespace(returncode=None, stdout=out, stderr=err, wait=wait, kill=lambda: mortos.append(1))
    with trocar(asyncio, "create_subprocess_exec", preso), trocar(trabalho, "log_turn", lambda *a: None):
        await trabalho.tool(app, pedido)
        t = app["trabalho"]["task"]
        await asyncio.sleep(0.05)
        check("Cancelei" in (await trabalho.tool(app, {"acao": "cancelar"}))["result"], "não cancelou")
        with contextlib.suppress(asyncio.CancelledError):
            await t
    check(mortos and not app["trabalho"] and [m for m in tela if m["type"] == "busy"][-1]["done"], "cancelar deixou algo preso")
    check(trabalho.split("só texto") == ("só texto", "só texto"), "resposta sem FALA")
    check("trabalho_longo" in server.PERSONA and "trabalho_longo" in server.NOT_DONE, "a PERSONA não manda usar trabalho_longo")


async def reconexao():
    """Sem rede, a sessão continua tentando (antes desistia em ~5 s e a janela ficava morta), e um resultado que chega com a
    conexão fechada não some: vai quando o Gemini volta (como aviso, se a sessão for nova)."""
    s, tela, gemini = sessao_falsa()
    tentativas, dormir = [], asyncio.sleep

    async def sem_rede():
        tentativas.append(1)
        if len(tentativas) >= 6:
            s.closed = True
        raise OSError("Network is unreachable")

    async def rapido(t):
        await dormir(0)
    s.connect = sem_rede
    with trocar(asyncio, "sleep", rapido), trocar(server, "log", lambda *a: None):
        await s.gemini_loop()
    check(len(tentativas) == 6 and not [m for m in tela if m["type"] == "error"], f"desistiu sem rede: {len(tentativas)} tentativas")
    check(any("Sem conexão" in m.get("text", "") for m in tela), "a tela não disse que está sem conexão")

    s.closed, gemini[:] = False, []
    s.gemini.closed = True
    resposta = {"toolResponse": {"functionResponses": [{"id": "9", "name": "executar_no_mac", "response": {"result": "Feito."}}]}}
    await s.to_gemini(resposta)
    await s.to_gemini({"realtimeInput": {"audio": {"data": server.SILENCE}}})   # áudio velho não é guardado
    check(not gemini and len(s.outbox) == 1, "o resultado foi perdido ou o áudio foi guardado")
    s.gemini.closed, s.resumed = False, False
    await s.send_outbox()
    check(len(gemini) == 1 and "Feito." in gemini[0]["realtimeInput"]["text"] and not s.outbox, f"depois de reconectar: {gemini}")
    s.gemini.closed = True
    await s.to_gemini(resposta)
    s.gemini.closed, s.resumed = False, True
    await s.send_outbox()
    check(gemini[-1] == resposta, "sessão retomada deveria receber a resposta da ferramenta como é")


async def routes():
    app = await server.make_app()
    app.on_startup.clear()   # sem leitura diária, resumos nem checagem de tela durante o teste
    async with TestClient(TestServer(app)) as c:
        for url in ("/", "/api/projects", "/api/calendar", "/api/notes", "/api/gravacao", "/api/memory", "/api/history"):
            r = await c.get(url)
            check(r.status == 200, f"GET {url} -> {r.status}")
        page = await (await c.get("/")).text()
        check(f'window.JARVIS = {{"user": {json.dumps(core.USER, ensure_ascii=False)}' in page, "a página não recebeu o nome do config")
        check(page.index("window.JARVIS") < page.index("const USER_NAME"), "o nome chega depois do script que o usa")
        pids = [p["id"] for p in (await (await c.get("/api/projects")).json())["projetos"]]
        check(pids == ["projeto-exemplo"], f"devia listar só o projeto de exemplo: {pids}")
        for pid in pids:
            for url in (f"/api/projects/{pid}", f"/api/projects/{pid}/studio", f"/api/projects/{pid}/notas"):
                r = await c.get(url)
                check(r.status == 200, f"GET {url} -> {r.status}")
        # canal de avisos: uma tela conectada recebe o que o servidor anuncia
        r = await c.get("/api/eventos")
        await asyncio.sleep(0.1)
        await core.broadcast(app, type="calendar", action="sync", date="2026-01-01", by="teste")
        line = b""
        while not line.startswith(b"data:"):
            line = await asyncio.wait_for(r.content.readline(), 3)
        check(json.loads(line[5:])["by"] == "teste", "aviso não chegou pelo /api/eventos")
        r.close()


def cofre_atomico():
    """Gravações no cofre: sem arquivo pela metade, sem .tmp sobrando, e '## Fatos' dentro de um fato não reescreve a memória."""
    import tempfile
    import vault
    with tempfile.TemporaryDirectory() as d:
        v = vault.Vault(d)
        v.ensure()
        v.remember("A Ana escreveu ## Fatos numa nota de teste", "outros")
        v.remember("Prefere café sem açúcar", "preferencias")
        antes = v.facts_file.read_text(encoding="utf-8")
        v.ensure()   # roda a migração antiga de novo
        check(v.facts_file.read_text(encoding="utf-8") == antes, "'## Fatos' dentro de um fato reescreveu a memória")
        check(len(v.facts()) == 2, f"fatos perdidos: {v.facts()}")
        velho = v.facts_file.read_text(encoding="utf-8").split("\n## ", 1)[0] + "\n## Fatos\n- fato antigo\n"
        v.facts_file.write_text(velho, encoding="utf-8")
        v.ensure()   # o formato antigo de verdade ainda migra
        check([f["text"] for f in v.facts()] == ["fato antigo"], f"migração do formato antigo quebrou: {v.facts()}")
        check(not list(pathlib.Path(d).rglob("*.tmp")), "sobrou arquivo .tmp no cofre")

        def falha(self, *a, **k):
            raise OSError("disco cheio")
        orig = pathlib.Path.write_text
        pathlib.Path.write_text = falha
        try:
            v.remember("Fato que não chega a gravar", "outros")
        except OSError:
            pass
        finally:
            pathlib.Path.write_text = orig
        check([f["text"] for f in v.facts()] == ["fato antigo"], "uma gravação que falhou apagou a memória")


def caminhos():
    """paths.py: o config.json manda; sem ele, o programa é procurado no PATH do Jarvis; o "~" do cofre é expandido."""
    import config
    import paths
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        cfg = pathlib.Path(d) / "config.json"
        cfg.write_text(json.dumps({"vault": "~/CofreTeste", "claude_path": "~/bin/claude-teste", "app_path": "/Applications/Outro.app"}))
        with trocar(config, "CONFIG", cfg):
            check(paths.vault() == pathlib.Path.home() / "CofreTeste", f"o ~ do cofre não foi expandido: {paths.vault()}")
            check(paths.claude() == str(pathlib.Path.home() / "bin/claude-teste"), f"claude_path ignorado: {paths.claude()}")
            check(paths.recorder() == pathlib.Path("/Applications/Outro.app/Contents/MacOS/jarvis-gravar"), f"app_path ignorado: {paths.recorder()}")
        with trocar(config, "CONFIG", pathlib.Path(d) / "nao-existe.json"), trocar(paths.shutil, "which", lambda n, path=None: None):
            check(paths.ytdlp() == "yt-dlp", f"sem yt-dlp devia sobrar o nome puro: {paths.ytdlp()}")
            check(core.settings()["vault"] == str(pathlib.Path.home() / "Jarvis"), "padrão do cofre mudou")
    check(paths.code() == core.HERE, "pasta do código errada")


def identidade():
    """Nome, persona e cofre vêm do config; a persona pública não tem os exemplos pessoais."""
    import vault
    publica = (core.HERE / "prompts/persona.pt-BR.md").read_text(encoding="utf-8")
    for termo in ("iFood", "Austrália", "Brisbane", "reclamou", "InfoMoney", "Lucas"):
        check(termo not in publica, f"a persona pública ainda tem '{termo}'")
    texto = server.PERSONA.format(user="Ana", switches="x", today="y", time="z")
    check("Ana" in texto and "{" not in texto, "a persona não preencheu o nome ou sobrou campo")
    check(core.USER in server.FUNCTIONS[0]["description"] or any(core.USER in f["description"] for f in server.FUNCTIONS),
          "o nome não entrou nas descrições das ferramentas")
    check("inbox" in vault.AREAS and all(len(v) == 2 for v in vault.AREAS.values()), f"áreas do cofre erradas: {vault.AREAS}")
    check(all(k in server.AREA_HELP for k in vault.AREAS), "a descrição das áreas não cobre todas")
    check(set(vault.TOPICS) == {"quem", "preferencias", "pessoas", "projetos", "rotina", "outros"}, "tópicos mudaram de chave")


def sem_atticus():
    """Sem o Atticus, executar_no_mac some das ferramentas e da persona; com ele, a persona fica como era."""
    com, sem = server.persona(True), server.persona(False)
    check("[[" not in com and "]]" not in com and "[[" not in sem and "]]" not in sem, "sobrou marcador [[mac|...]] na persona")
    check("executar_no_mac" in com and "executar_no_mac" not in sem, "a persona sem Atticus ainda cita executar_no_mac")
    check("mac_rapido" in sem, "a persona sem Atticus perdeu o mac_rapido")
    sem.format(user="Ana", switches="x", today="y", time="z")   # nenhum campo novo quebrou o format
    with trocar(server, "has_executor", lambda: False):
        nomes = [f["name"] for f in server.tools()[0]["functionDeclarations"]]
        check("executar_no_mac" not in nomes and "mac_rapido" in nomes, f"ferramentas sem Atticus erradas: {nomes}")
        r = asyncio.run(server.run_task("teste", 5))
        check("Atticus" in r.get("error", ""), f"run_task sem Atticus devia avisar: {r}")
        msg = server.setup_message("Charon")
        # só a parte fixa: o resto (memória, conversas do dia) é dado real do cofre e pode citar qualquer coisa
        fixa = msg["setup"]["systemInstruction"]["parts"][0]["text"].split("\n\nHoje é")[0]
        check("executar_no_mac" not in fixa, "a persona mandada ao Gemini sem Atticus ainda cita executar_no_mac")
        check("executar_no_mac" not in json.dumps(msg["setup"]["tools"], ensure_ascii=False), "as ferramentas mandadas ao Gemini ainda têm executar_no_mac")
    with trocar(server, "has_executor", lambda: True):
        nomes = [f["name"] for f in server.tools()[0]["functionDeclarations"]]
        check("executar_no_mac" in nomes, "com Atticus, executar_no_mac sumiu")


sintaxe()
selftests()
voice_tools()
honestidade()
asyncio.run(atticus())
asyncio.run(pesquisa())
asyncio.run(texto_na_tela())
asyncio.run(roxo())
asyncio.run(mudo())
asyncio.run(raciocinio())
interrupcao()
asyncio.run(afirmacao_na_sessao())
asyncio.run(trabalho_longo())
asyncio.run(reconexao())
cofre_atomico()
caminhos()
identidade()
sem_atticus()
asyncio.run(routes())
print(f"tudo certo: {ok} verificações")
