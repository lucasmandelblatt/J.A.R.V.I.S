"""Jarvis: voice conversation with Gemini Live; tasks on the Mac go to Claude through Atticus.

The page (static/index.html, shown by the Jarvis app or a browser) captures the microphone with echo
cancellation and plays the voice. This server holds the Gemini key, relays audio both ways, runs the
tools, and keeps memory in the Obsidian vault (08 - Jarvis), where Claude Code reads it too.

Run:  .venv/bin/python server.py            (the Jarvis app does this for you)
Test: .venv/bin/python server.py --check    (connects to Gemini and asks for a short spoken reply)
"""
import asyncio
import base64
import datetime
import json
import pathlib
import re
import sys
import tempfile
import time
import traceback
import urllib.parse

import aiohttp
from aiohttp import web

import agenda
import anexos_chat
import busca
import notas
import paths
import mac
import research
import sources
import trabalho
import video
from core import HERE, SWITCHES, UPLOADS, VAULT, active_project, api_events, api_key, clean_env, log, log_talk, log_turn, notify_projects, osascript, read_with_gemini, save_setting, settings, switches
from rotas_agenda import agenda_tool, api_calendar, api_calendar_day, api_calendar_file, api_calendar_upload, api_notes, notes_tool
from estudo import api_course, api_recording, course_tool, record_tool, start_watch
from rotas_projetos import api_collections, api_nb_audio, api_nb_chat, api_nb_copy, api_nb_discover, api_nb_item, api_nb_notes, api_nb_overview, api_nb_studio, api_nb_tags, api_nb_text, api_project, api_project_files, api_project_open, api_project_source, api_project_sources, api_project_video, api_projects, api_source, api_source_video, daily_reader, project_tool, review_clip, source_tool, study_position, study_tool
from vault import AREA_HELP, AREAS, TOPICS, WEEKDAYS
from config import USER

SLOW_TOOLS = {"executar_no_mac", "pesquisar_web", "ler_link", "ler_abas_chrome", "olhar_tela", "rever_trecho"}
SLOW_AFTER = 12   # seconds of silence before Jarvis says he's still on it
KEEPALIVE_EVERY = 30   # seconds between bits of silence sent while the mic is muted (Gemini drops idle sessions at ~2 min)
SILENCE = base64.b64encode(bytes(3200)).decode()   # 100 ms of 16 kHz 16-bit silence
# While one of these runs the reactor turns purple ("executando") with this line under it; the instant tools show nothing.
BUSY = {
    "olhar_tela": lambda a: "Olhando a tela",
    "abas_chrome": lambda a: "Vendo as abas do Chrome",
    "ler_abas_chrome": lambda a: f"Lendo {len(a.get('numeros') or [])} abas do Chrome",
    "pesquisar_web": lambda a: ("Pesquisa profunda: " if a.get("profundidade") == "profunda" else "Pesquisando: ")
                               + str(a.get("pergunta", ""))[:90],
    "ler_link": lambda a: "Lendo " + str(a.get("url", ""))[:90],
    "executar_no_mac": lambda a: "Pedindo ao Claude: " + str(a.get("tarefa", ""))[:90],
    "rever_trecho": lambda a: "Reassistindo o trecho do vídeo",
    "buscar_memoria": lambda a: "Buscando na memória: " + str(a.get("pergunta", ""))[:80],
    "ler_nota": lambda a: "Lendo a nota " + str(a.get("titulo", ""))[:80],
    "assistir_video": lambda a: "Preparando o vídeo",
    "fonte_projeto": lambda a: "Lendo o site para o projeto",
}
GEMINI_REST ="https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

MODEL = "models/gemini-3.8-live"
GEMINI_WS = ("wss://generativelanguage.googleapis.com/ws/"
             "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent")

# Who Jarvis is and how it talks: prompts/persona.local.md if it exists (a personal version, kept out of git), else the
# public prompts/persona.pt-BR.md. {user}, {switches}, {today} and {time} are filled in each time a conversation opens.
PERSONA = next(p for p in (HERE / "prompts/persona.local.md", HERE / "prompts/persona.pt-BR.md") if p.exists()).read_text(encoding="utf-8")

FUNCTIONS = [
    {"name": "olhar_tela",
     "description": f"Tira uma foto da tela de {USER} agora e devolve a leitura do que aparece, focada na pergunta.",
     "parameters": {"type": "OBJECT", "properties": {"pergunta": {
         "type": "STRING", "description": f"O que {USER} quer saber sobre a tela (ex.: explique o erro no terminal)."}},
         "required": ["pergunta"]}},
    {"name": "abas_chrome",
     "description": f"Lista as abas abertas no Google Chrome de {USER} (número, título e endereço). Use antes de ler_abas_chrome.",
     "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "ler_abas_chrome",
     "description": f"Lê o conteúdo de abas do Chrome de {USER} (pelos números de abas_chrome) e responde à pergunta sobre elas.",
     "parameters": {"type": "OBJECT", "properties": {
         "numeros": {"type": "ARRAY", "items": {"type": "INTEGER"}, "description": "Números das abas, como vieram de abas_chrome (até 6)."},
         "pergunta": {"type": "STRING", "description": f"O que {USER} quer saber (ex.: resuma o que preciso para imigrar)."}},
         "required": ["numeros", "pergunta"]}},
    {"name": "pesquisar_no_chrome",
     "description": f"Abre uma pesquisa do Google numa aba nova do Chrome de {USER} (para ele ver na tela).",
     "parameters": {"type": "OBJECT", "properties": {"busca": {"type": "STRING"}}, "required": ["busca"]}},
    {"name": "pesquisar_web",
     "description": "Pesquisa de verdade na internet (várias buscas, lê as fontes, cruza e cita). Devolve a resposta pronta "
                    f"para falar; a versão completa com as fontes aparece na tela de {USER}.",
     "parameters": {"type": "OBJECT", "properties": {
         "pergunta": {"type": "STRING", "description": f"A pergunta completa, com todo o contexto que {USER} deu (lugar, datas, "
                                                       "para quê ele quer saber), em português."},
         "profundidade": {"type": "STRING", "enum": ["rapida", "profunda"],
                          "description": "rapida (~30-60 s) para fatos, preços, previsões, notícias; profunda (~2-5 min) quando "
                                         "ele pedir estudo, análise, pesquisa profunda, comparação ou decisão importante."}},
         "required": ["pergunta", "profundidade"]}},
    {"name": "ler_link",
     "description": "Lê uma página da web ou assiste a um vídeo do YouTube pelo endereço e responde à pergunta sobre ele.",
     "parameters": {"type": "OBJECT", "properties": {
         "url": {"type": "STRING", "description": "Endereço completo da página ou do vídeo."},
         "pergunta": {"type": "STRING", "description": f"O que {USER} quer saber (ex.: resuma e explique de forma simples)."}},
         "required": ["url", "pergunta"]}},
    {"name": "ajustar_permissao",
     "description": f"Liga ou desliga uma permissão do Jarvis quando {USER} pedir.",
     "parameters": {"type": "OBJECT", "properties": {
         "permissao": {"type": "STRING", "enum": ["vision", "internet", "actions"],
                       "description": "vision = visão da tela, internet = pesquisa e links, actions = ações no Mac."},
         "ligada": {"type": "BOOLEAN"}}, "required": ["permissao", "ligada"]}},
    {"name": "mac_rapido",
     "description": f"Ações rápidas e diretas no Mac de {USER}, feitas na hora (menos de 1 segundo), sem o Claude. Use SEMPRE "
                    "esta para: organizar ou limpar a Mesa/Área de Trabalho (move os prints soltos para Imagens > Prints, "
                    "nada é apagado), abrir um app, abrir uma pasta, arquivo ou site, ver o que tem numa pasta, criar pasta, "
                    f"mover arquivo ou pasta, mandar algo para a Lixeira (só com o sim de {USER}), volume, mudo e modo escuro.",
     "parameters": {"type": "OBJECT", "properties": {
         "acao": {"type": "STRING", "enum": mac.ACTIONS},
         "alvo": {"type": "STRING", "description": "App, pasta, arquivo ou endereço. Pastas conhecidas: mesa, downloads, "
                                                   "documentos, imagens; ou o nome do arquivo/pasta; ou um caminho começando com ~/."},
         "destino": {"type": "STRING", "description": "Só para mover: a pasta de destino (mesmo formato do alvo)."},
         "valor": {"type": "INTEGER", "description": "Só para volume: de 0 a 100."},
         "ligar": {"type": "BOOLEAN", "description": "Para mudo e modo_escuro: true liga, false desliga (omita para alternar o modo escuro)."},
         "incluir_imagens": {"type": "BOOLEAN", "description": "Em organizar_mesa: true move também as imagens soltas que não são print."},
         "confirmado": {"type": "BOOLEAN", "description": f"Em lixeira: true só depois que {USER} disser sim."}},
         "required": ["acao"]}},
    {"name": "executar_no_mac",
     "description": f"Executa uma tarefa no Mac de {USER} usando o Claude (via Atticus) e devolve o resultado em texto. "
                    "Mais lento (dezenas de segundos): use só quando mac_rapido não resolver.",
     "parameters": {"type": "OBJECT", "properties": {"tarefa": {
         "type": "STRING", "description": f"O pedido completo e claro, em português, como {USER} pediu."}},
         "required": ["tarefa"]}},
    {"name": "assistir_video",
     "description": "Assiste a um vídeo de verdade (imagem e áudio) e guarda a análise completa como fonte de um projeto.",
     "parameters": {"type": "OBJECT", "properties": {
         "fonte": {"type": "STRING", "description": "O link do vídeo, o caminho de um arquivo do Mac, ou 'chrome' para o vídeo "
                                                    "da aba aberta no Chrome."},
         "projeto": {"type": "STRING", "description": "Nome do projeto onde guardar. Vazio = projeto aberto, ou um projeto "
                                                      "novo com o nome do vídeo."},
         "foco": {"type": "STRING", "description": f"Se {USER} disse o que quer aprender ou procurar no vídeo, escreva aqui."}},
         "required": ["fonte"]}},
    {"name": "estudar_curso",
     "description": "Estuda um curso inteiro que está aberto no Chrome (ex.: TubeClub), aula por aula, como um aluno: "
                    "toca cada aula no player, grava a janela do Chrome, assiste, guarda cada aula no Studio e no Obsidian e "
                    f"reescreve o manual de execução do negócio a cada aula. Segue de onde parou. Use quando {USER} pedir "
                    "para estudar, assistir ou aprender o curso/módulo inteiro.",
     "parameters": {"type": "OBJECT", "properties": {
         "acao": {"type": "STRING", "enum": ["iniciar", "parar", "status"]},
         "projeto": {"type": "STRING", "description": "Projeto onde guardar. Vazio = projeto aberto, ou um novo."},
         "velocidade": {"type": "NUMBER", "description": "Velocidade do vídeo (1 a 2). Padrão 1,5 (em 2x a análise perde detalhes)."},
         "aulas": {"type": "NUMBER", "description": "Quantas aulas estudar desta vez. Vazio = até o fim do curso."}},
         "required": ["acao"]}},
    {"name": "gravar_tela",
     "description": "Assiste a um vídeo que não dá para baixar (aula de curso privado, plataforma com login) gravando a tela "
                    f"e o som do Mac enquanto {USER} dá play. Ao parar, assiste à gravação e a guarda como fonte do projeto "
                    f"e no Obsidian. Use quando assistir_video falhar ou {USER} pedir para gravar/assistir pela tela.",
     "parameters": {"type": "OBJECT", "properties": {
         "acao": {"type": "STRING", "enum": ["iniciar", "parar", "status"]},
         "titulo": {"type": "STRING", "description": "Nome da aula ou do vídeo. Vazio = o título da aba do Chrome."},
         "projeto": {"type": "STRING", "description": "Projeto onde guardar. Vazio = projeto aberto, ou um novo com o título."},
         "foco": {"type": "STRING", "description": f"O que {USER} quer aprender ou procurar no vídeo, se disse."},
         "minutos": {"type": "NUMBER", "description": f"Duração do vídeo em minutos, se {USER} disse: a gravação para "
                                                      "sozinha depois disso (mais um minuto de folga)."}},
         "required": ["acao"]}},
    {"name": "projeto",
     "description": "Abre, cria, lista ou fecha um projeto (sala de estudo com fontes e conversa próprias).",
     "parameters": {"type": "OBJECT", "properties": {
         "acao": {"type": "STRING", "enum": ["abrir", "criar", "listar", "sair"]},
         "nome": {"type": "STRING", "description": "Nome do projeto (para abrir ou criar)."}},
         "required": ["acao"]}},
    {"name": "rever_trecho",
     "description": "Reassiste um trecho de um vídeo do projeto aberto para responder uma pergunta precisa.",
     "parameters": {"type": "OBJECT", "properties": {
         "fonte": {"type": "STRING", "description": "O id da fonte (ex.: 01-...) ou parte do título do vídeo."},
         "pergunta": {"type": "STRING"},
         "inicio": {"type": "STRING", "description": "Minuto de início, como MM:SS ou H:MM:SS. Vazio = vídeo inteiro."},
         "fim": {"type": "STRING", "description": "Minuto final (opcional)."}},
         "required": ["fonte", "pergunta"]}},
    {"name": "video_na_tela",
     "description": f"A tela de estudo: em que vídeo e minuto {USER} está, ou pular o vídeo para um minuto (abre a tela se estiver fechada).",
     "parameters": {"type": "OBJECT", "properties": {
         "acao": {"type": "STRING", "enum": ["onde_estou", "pular"]},
         "minuto": {"type": "STRING", "description": "Para pular: MM:SS ou H:MM:SS."},
         "fonte": {"type": "STRING", "description": "Para pular: id ou parte do título do vídeo. Vazio = o vídeo que está na tela."}},
         "required": ["acao"]}},
    {"name": "lembrar",
     "description": f"Guarda um fato duradouro e curto sobre {USER} na memória (Obsidian), no assunto certo. "
                    "Se já existir um fato parecido, ele é atualizado em vez de repetido.",
     "behavior": "NON_BLOCKING",
     "parameters": {"type": "OBJECT", "properties": {
         "fato": {"type": "STRING", "description": f"Uma frase curta em terceira pessoa (ex.: {USER} prefere reuniões de manhã)."},
         "topico": {"type": "STRING", "enum": list(TOPICS),
                    "description": "quem = quem ele é e objetivos; preferencias; pessoas; projetos = projetos e ideias; "
                                   "rotina = rotina e compromissos; outros."}},
         "required": ["fato", "topico"]}},
    {"name": "anotar",
     "description": "Cria ou atualiza uma nota organizada no cofre do Obsidian para um assunto que merece registro "
                    "(ideia de negócio desenvolvida, plano, decisão, resumo de pesquisa, roteiro). Se a nota já existir, "
                    "acrescenta uma atualização datada.",
     "behavior": "NON_BLOCKING",
     "parameters": {"type": "OBJECT", "properties": {
         "titulo": {"type": "STRING", "description": "Título curto e claro, que sirva de nome da nota (ex.: Ideia — app de brechó)."},
         "conteudo": {"type": "STRING", "description": "O conteúdo em Markdown limpo: um parágrafo de contexto e depois seções "
                                                      "com ## e listas curtas (o que é, para quem, próximos passos, dúvidas em aberto). "
                                                      "Sem emojis. Tarefas como - [ ]."},
         "area": {"type": "STRING", "enum": list(AREAS), "description": AREA_HELP + "."},
         "tipo": {"type": "STRING", "enum": ["plan", "reference", "guide", "log"],
                  "description": "plan = plano/ideia; reference = consulta; guide = passo a passo; log = registro datado."},
         "status": {"type": "STRING", "enum": ["active", "idea"], "description": "idea para ideias ainda não começadas."}},
         "required": ["titulo", "conteudo", "area"]}},
    {"name": "substituir",
     "description": f"Quando {USER} disser que algo mudou daqui para frente (substitui, esquece o que tinha, agora é assim): "
                    "apaga da memória TODOS os fatos sobre o assunto e grava os novos; se houver nota sobre o assunto, ela é "
                    "reescrita por inteiro (sem versões penduradas). Chame primeiro com confirmado=false para ver o que será "
                    f"apagado, leia isso para {USER} e só chame com confirmado=true depois que ele disser sim.",
     "parameters": {"type": "OBJECT", "properties": {
         "assunto": {"type": "STRING", "description": "Palavra-chave do assunto (ex.: o nome de um projeto). Todos os fatos que a citam saem."},
         "fatos_novos": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Os fatos novos, curtos, em terceira pessoa."},
         "topico": {"type": "STRING", "enum": list(TOPICS)},
         "nota_titulo": {"type": "STRING", "description": "Título da nota a reescrever, se houver (use o título exato das notas que você escreveu)."},
         "nota_conteudo": {"type": "STRING", "description": "A nota inteira na versão nova, em Markdown limpo."},
         "area": {"type": "STRING", "enum": list(AREAS)},
         "confirmado": {"type": "BOOLEAN", "description": f"false = só mostrar o que muda; true = aplicar (só depois do sim de {USER})."}},
         "required": ["assunto", "fatos_novos", "topico", "confirmado"]}},
    {"name": "ler_nota",
     "description": "Lê uma nota do cofre do Obsidian pelo título, para retomar um assunto já registrado.",
     "parameters": {"type": "OBJECT", "properties": {"titulo": {"type": "STRING"}}, "required": ["titulo"]}},
    {"name": "buscar_memoria",
     "description": "Busca nas análises das fontes, nos manuais de curso e nas notas do cofre os trechos que respondem a "
                    "uma pergunta. Com um projeto aberto, busca nele; onde='tudo' busca em todos os projetos e no cofre.",
     "parameters": {"type": "OBJECT", "properties": {
         "pergunta": {"type": "STRING", "description": "A pergunta ou as palavras-chave, com os termos importantes."},
         "onde": {"type": "STRING", "enum": ["projeto", "tudo"]}},
         "required": ["pergunta"]}},
    {"name": "fonte_projeto",
     "description": "Acrescenta ao projeto aberto (ou ao projeto citado) um site ou notícia para o Jarvis ler, e opcionalmente "
                    "marca para ler todo dia (ex.: um portal de notícias). Também relê agora uma fonte de site. Vídeos vão por assistir_video.",
     "parameters": {"type": "OBJECT", "properties": {
         "acao": {"type": "STRING", "enum": ["adicionar", "reler"]},
         "url": {"type": "STRING", "description": "Endereço completo do site (adicionar)."},
         "diario": {"type": "BOOLEAN", "description": "true = ler de novo todo dia."},
         "fonte": {"type": "STRING", "description": "Reler: id ou parte do título da fonte."},
         "projeto": {"type": "STRING", "description": "Nome do projeto, se não for o aberto."}},
         "required": ["acao"]}},
    {"name": "agenda",
     "description": f"O calendário de tarefas de {USER} (o mesmo que aparece no app). Ver, adicionar, concluir, reabrir, priorizar, "
                    "editar, mover, remover tarefas, ou abrir/fechar a agenda grande na tela.",
     "parameters": {"type": "OBJECT", "properties": {
         "acao": {"type": "STRING", "enum": ["ver", "adicionar", "concluir", "reabrir", "priorizar", "despriorizar",
                                             "editar", "mover", "remover", "abrir", "fechar"]},
         "data": {"type": "STRING", "description": "AAAA-MM-DD do dia da tarefa (para ver: o primeiro dia)."},
         "ate": {"type": "STRING", "description": "Para ver vários dias: AAAA-MM-DD do último dia."},
         "tarefa": {"type": "STRING", "description": "Adicionar: o texto da tarefa. Outras ações: um pedaço do texto para achá-la."},
         "novo_texto": {"type": "STRING", "description": "Editar: o texto novo."},
         "nota": {"type": "STRING", "description": "Adicionar ou editar: observação/detalhes da tarefa."},
         "prioridade": {"type": "BOOLEAN", "description": "Adicionar: já marcar como prioridade."},
         "nova_data": {"type": "STRING", "description": "Mover: AAAA-MM-DD do dia de destino."}},
         "required": ["acao"]}},
    {"name": "mostrar_texto",
     "description": f"Mostra um texto completo no chat de {USER}, exatamente como você escrever, sem encerrar a conversa. Use "
                    "SEMPRE que entregar algo para ele ler, copiar ou usar: prompt, lista, plano, rascunho, roteiro, e-mail, "
                    "passo a passo, comparação, ou qualquer resposta que não cabe em duas ou três frases faladas.",
     "parameters": {"type": "OBJECT", "properties": {
         "titulo": {"type": "STRING", "description": "Título curto do que é (ex.: Prompt para o Claude Code)."},
         "texto": {"type": "STRING", "description": "O texto inteiro, pronto para usar, em Markdown simples. Nunca resuma, "
                                                    "corte ou deixe 'o resto' para depois."}},
         "required": ["titulo", "texto"]}},
    {"name": "trabalho_longo",
     "description": "Faz de verdade, em segundo plano, um trabalho grande que leva minutos: diagnóstico ou revisão de um "
                    "código (como o do Jarvis), análise longa, plano de estudos ou documento a partir do cofre do Obsidian, "
                    "pesquisa com muitas fontes que vira um texto. É o Claude Code lendo arquivos e a internet (não muda "
                    "nada no Mac). Volta na hora; o andamento aparece na tela e o sistema te avisa quando terminar, com o "
                    f"texto completo já no chat. Use status quando {USER} perguntar se terminou.",
     "parameters": {"type": "OBJECT", "properties": {
         "acao": {"type": "STRING", "enum": ["iniciar", "status", "cancelar"], "description": "Padrão: iniciar."},
         "tarefa": {"type": "STRING", "description": f"Para iniciar: o pedido completo, com todo o contexto que {USER} deu "
                                                     "e o que ele quer receber no fim."},
         "titulo": {"type": "STRING", "description": "Nome curto do trabalho (ex.: Diagnóstico do Jarvis)."}}}},
    {"name": "notas",
     "description": f"O bloco de notas de {USER} no app (estilo Notas do iPhone): criar, acrescentar texto, ler, listar, "
                    "apagar notas, criar pastas, ou abrir/fechar o Notas grande na tela.",
     "parameters": {"type": "OBJECT", "properties": {
         "acao": {"type": "STRING", "enum": ["criar", "acrescentar", "ler", "listar", "apagar", "criar_pasta", "abrir", "fechar"]},
         "pasta": {"type": "STRING", "description": "Nome da pasta (padrão: Notas). Criar e criar_pasta criam a pasta se faltar."},
         "nota": {"type": "STRING", "description": "Um pedaço do título da nota (acrescentar, ler, apagar, abrir)."},
         "texto": {"type": "STRING", "description": "Criar: a nota inteira, primeira linha = título. Acrescentar: o texto a pôr no fim."}},
         "required": ["acao"]}},
]


def has_executor():
    """executar_no_mac needs Atticus (a separate app). Without it the tool is left out and the persona says so."""
    return paths.atticus().exists()


def tools():
    # Google Search grounding isn't in the free tier (the Live connection is refused), so searches go through Claude.
    funcs = FUNCTIONS if has_executor() else [f for f in FUNCTIONS if f["name"] != "executar_no_mac"]
    return [{"functionDeclarations": funcs}]


MARK = re.compile(r"\[\[mac\|(.*?)(?:\|\|(.*?))?\]\]", re.S)


def persona(mac):
    """PERSONA with its [[mac|with executar_no_mac||without it]] parts resolved."""
    return MARK.sub(lambda m: m[1] if mac else (m[2] or ""), PERSONA)


# ---------- Memory in the Obsidian vault (organized by vault.py) ----------


def setup_message(voice, handle=None):
    now = datetime.datetime.now()
    sw = ", ".join(f"{label} {'LIGADA' if switches()[k] else 'DESLIGADA'}" for k, label in SWITCHES.items())
    instruction = persona(has_executor()).format(user=USER, today=f"{WEEKDAYS[now.weekday()]}, {now:%d/%m/%Y}", time=f"{now:%H:%M}", switches=sw)
    proj = active_project()
    mem = VAULT.context(conversations=proj is None)
    if mem:
        instruction += "\n\n" + mem
    instruction += f"\n\nAgenda de {USER}:\n" + agenda.summary(now.date().isoformat())
    instruction += f"\n\nBloco de notas de {USER} (pasta: títulos):\n" + notas.summary()
    if proj:
        instruction += "\n\n" + proj.context()
    return {"setup": {
        "model": MODEL,
        "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}},
        "systemInstruction": {"parts": [{"text": instruction}]},
        "tools": tools(),
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
        "sessionResumption": {"handle": handle} if handle else {},
        "contextWindowCompression": {"slidingWindow": {}},
        "realtimeInputConfig": realtime_input_config(settings().get("interrupcao", "normal")),
    }}


def realtime_input_config(mode):
    """How the user's voice (and noise) cuts Jarvis off. config.json "interrupcao":
    "normal" (default, as before): low start-of-speech sensitivity, so a TV or people nearby count less as the user speaking;
    "firme": also needs 0.4 s of continuous speech before it counts, so a clap, a cough or a door doesn't cut him off;
    "nunca": no voice or noise interrupts Jarvis; he finishes every answer (only ending the conversation stops him)."""
    detection = {"startOfSpeechSensitivity": "START_SENSITIVITY_LOW"}
    if mode == "firme":
        detection["prefixPaddingMs"] = 400
    config = {"automaticActivityDetection": detection}
    if mode == "nunca":
        config["activityHandling"] = "NO_INTERRUPTION"
    return config


# Atticus's prompt tells Claude to hand long work to a background agent; from the command line no agent starts and only
# the sentence "iniciei em segundo plano" comes back (12/11 20:01: 6 s, no steps). So the task asks for the result now.
ATTICUS_NOTE = (f"\n\n(Pedido feito pelo Jarvis, o assistente de voz de {USER}: faça tudo agora, nesta execução, e responda "
                "com o resultado final completo. Não passe a tarefa para um agente separado: o Jarvis só recebe o que "
                "você responder aqui e não fica sabendo de nada que termine depois.)")
# Only Claude saying that IT handed the work off or will report later; "o app está rodando em segundo plano" is a result.
LATER = re.compile(r"\b(iniciei|comecei|passei|deleguei|deixei)\b[^.]{0,80}\b(segundo plano|background)\b"
                   r"|te aviso (quando|assim que)|vou te avisar|avisarei", re.I)
NOT_DONE = ("Não concluído: o Claude respondeu que continuaria depois (“{}”), mas o Jarvis não recebe nada que termine "
            f"depois. Diga isso a {USER} e ofereça fazer com trabalho_longo, que roda de verdade em segundo plano.")


# Phrases that claim work. ONGOING is a lie when nothing is running; DONE is a lie when no tool ran recently.
ONGOING = re.compile(r"segundo plano|\bem andamento\b|\bcontinua(m)? (rodando|correndo|em execução|processando)"
                     r"|\b(estou|tô|sigo) (rodando|executando|processando|analisando|conduzindo|finalizando|examinando"
                     r"|trabalhando|preparando|montando|escrevendo|gerando|pesquisando)\b"
                     r"|\b(te aviso|te informo|vou te avisar|te mando)\b[^.]*\b(quando|assim que)\b"
                     r"|\bvou (conduzir|continuar|seguir|fazer|rodar|executar|analisar|examinar|preparar)\b[^.]*\bem silêncio\b", re.I)
DONE = re.compile(r"\b(finalizei|terminei)\b|\bconcluí\b(?! que)|\b(te mandei|te enviei|mandei aqui|enviei aqui)\b"
                  r"|\bjá (fiz|preparei|montei|enviei|mandei|criei|escrevi|gerei|incorporei|incluí|estruturei|rodei|executei"
                  r"|analisei|examinei|pesquisei)\b"
                  r"|\b(preparei|estruturei|montei|criei|gerei|escrevi) (o|a|um|uma|os|as|esse|este) (prompt|texto|plano|lista"
                  r"|rascunho|relatório|roteiro|documento|resumo|diagnóstico|análise)", re.I)
RECENT_WORK = 1800   # seconds: "terminei" within 30 min of real work that succeeded is just reporting it
CORRECTION = ("[sistema] Você acabou de dizer a {user} “{}”, e nenhuma ferramenta está rodando nem rodou para isso. "
              "Se a frase dizia que você fez ou está fazendo algo, ela não é verdade e ele vai ficar esperando: corrija em "
              "uma ou duas frases, dizendo que não fez, e ofereça fazer de verdade (sem executar nada que ele não pediu). "
              "Se a frase era verdadeira, siga a conversa sem comentar este aviso.")


class ThoughtFilter:
    """Drops the model's reasoning that leaks into the spoken transcript between asterisks (12/11 20:19: "*The user is
    questioning the previous response...*Você mencionou..."). Chunks arrive cut anywhere, so it keeps state between them;
    a run of asterisks opens or closes. reset() at the end of every turn, so a stray asterisk can't hide the next one."""

    def __init__(self):
        self.inside = False

    def __call__(self, chunk):
        out = []
        for part in re.split(r"(\*+)", chunk):
            if part.startswith("*"):
                self.inside = not self.inside
            elif not self.inside:
                out.append(part)
        return "".join(out)

    def reset(self):
        self.inside = False


NEGATION = re.compile(r"\b(não|nada|nenhum|nenhuma|nunca|sem)\b", re.I)


def unbacked_claim(said, busy, tool_recently):
    """The sentence in `said` that claims work no tool backs, or None. A negation earlier in the same sentence ("nada está
    em andamento", "não consigo fazer isso em segundo plano") makes it an honest answer, not a claim."""
    for pattern, backed in ((ONGOING, busy), (DONE, busy or tool_recently)):
        if backed:
            continue
        for m in pattern.finditer(said):
            start = max(said.rfind(c, 0, m.start()) for c in ".!?") + 1
            if not NEGATION.search(said[start:m.start()]):
                ends = [i for i in (said.find(c, m.end()) for c in ".!?") if i >= 0]
                return said[start:min(ends) if ends else None].strip()[:200]
    return None


async def run_task(task, timeout, progress=None):
    """Hands a task to Claude through Atticus's command-line brain and returns its answer.
    `progress(text)` (async) gets each step Atticus prints ("▸ Searching the web…") as it happens."""
    if not has_executor():   # the tool isn't offered then, but a stale conversation could still call it
        return {"error": "Não há executor de tarefas instalado (Atticus). Diga isso, sem fingir que fez."}
    env = clean_env()
    proc = await asyncio.create_subprocess_exec(
        "/usr/bin/python3", str(paths.atticus()), task + ATTICUS_NOTE, env=env, limit=16 * 1024 * 1024,
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    errors, lines_out = asyncio.create_task(proc.stderr.read()), []

    async def pump():
        while line := await proc.stdout.readline():
            line = line.decode(errors="replace")
            lines_out.append(line)
            if progress and line.lstrip().startswith("▸"):
                await progress("Claude: " + line.lstrip()[1:].strip()[:100])
        await proc.wait()
    try:
        await asyncio.wait_for(pump(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": f"A tarefa passou de {timeout} segundos e foi interrompida."}
    raw = "".join(lines_out).strip() or (await errors).decode(errors="replace").strip()
    # Atticus prints progress lines ("▸ Searching the web…") before the answer ("✓ …"); keep only the answer.
    lines = [l for l in raw.splitlines() if not l.lstrip().startswith("▸")]
    text = "\n".join(lines).strip().lstrip("✓✗ ").strip()
    if proc.returncode != 0:
        return {"error": text[-2000:] or "Falhou."}
    if LATER.search(text[:400]):
        return {"error": NOT_DONE.format(text[:300])}
    return {"result": text[-4000:] or "Feito."}


async def screenshot():
    """The main display as a JPEG no wider than 1600 px, or None when macOS refuses (no Screen Recording permission)."""
    shot = pathlib.Path(tempfile.gettempdir()) / "jarvis-tela.jpg"   # screencapture may not write inside ~/Desktop
    proc = await asyncio.create_subprocess_exec("/usr/sbin/screencapture", "-x", "-m", "-t", "jpg", str(shot),
                                                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0 or not shot.exists():
        log(f"tela: screencapture falhou (código {proc.returncode}): {err.decode(errors='replace').strip()[:300]}")
        return None
    resize = await asyncio.create_subprocess_exec("/usr/bin/sips", "-Z", "1600", str(shot),
                                                  stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await resize.wait()
    data = shot.read_bytes()
    shot.unlink(missing_ok=True)
    return data


async def check_screen(app):
    """At start, take one test screenshot so jarvis.log says whether macOS lets Jarvis see the screen."""
    async def check():
        log("tela: permissão OK" if await screenshot() else "tela: macOS BLOQUEOU a foto da tela")
    asyncio.create_task(check())


async def chrome_tabs():
    """[(number, window, tab, title, url)] for every Chrome tab, numbered from 1 across windows."""
    out, err = await osascript('''
        set out to ""
        set sep to ASCII character 9
        tell application "Google Chrome"
            repeat with w from 1 to count of windows
                repeat with t from 1 to count of tabs of window w
                    set out to out & (w as text) & sep & (t as text) & sep & (title of tab t of window w) & sep & (URL of tab t of window w) & linefeed
                end repeat
            end repeat
        end tell
        return out''')
    if err:
        if "-1743" in err or "Not authorized" in err:
            err = (f"O macOS não deixou o Jarvis controlar o Chrome. {USER} precisa permitir em Ajustes do Sistema > "
                   "Privacidade e Segurança > Automação > Jarvis > Google Chrome.")
        return None, err
    tabs = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            tabs.append((len(tabs) + 1, int(parts[0]), int(parts[1]), parts[2], parts[3]))
    return tabs, None


async def chrome_tab_text(window, tab):
    """The page's visible text, or None when Chrome blocks JavaScript from Apple Events (then the URL is fetched instead)."""
    out, err = await osascript(f'tell application "Google Chrome" to execute tab {tab} of window {window} '
                               'javascript "document.body ? document.body.innerText : \'\'"', timeout=15)
    return out[:20000] if out and out.strip() else None


class Session:
    """One conversation window. Reconnects to Gemini with a resumption handle when a connection ends."""

    def __init__(self, app, browser):
        self.app, self.browser, self.http, self.key = app, browser, app["http"], app["key"]
        self.gemini = None
        self.handle = None
        self.user_text, self.model_text = "", ""
        self.closed = False
        self.reconnect_after_turn = False
        self.voice = settings()["voice"]
        self.study = None   # what the study screen shows: {"pid", "sid", "title", "pos", "playing", "at"}
        self.running = {}   # tool call id -> tool name, while it runs
        self.last_work = 0.0   # when a work tool (research, Claude, reading, a text on screen) last succeeded
        self.tool_since_user = False   # a tool ran since the user last spoke or typed
        self.tool_in_turn = False   # a tool ran during Jarvis's current turn (what he said before it is backed)
        self.correcting = False   # the next turn is Jarvis correcting a claim: don't check it again
        self.thoughts = ThoughtFilter()
        self.muted, self.keepalive = False, None   # mic muted in the page (F5, button, claps), and the task keeping Gemini open
        self.outbox, self.resumed = [], False   # results and notices that hit a closed connection; was it resumed
        self.attaching = set()   # attachments being prepared (a PDF is read first), kept so they aren't garbage-collected

    async def to_browser(self, **msg):
        if not self.browser.closed:
            await self.browser.send_json(msg)

    async def to_gemini(self, msg):
        if self.gemini is not None and not self.gemini.closed:
            try:
                await self.gemini.send_str(json.dumps(msg))
                return
            except (ConnectionError, RuntimeError) as e:   # the connection is closing; gemini_loop reopens it
                log(f"send to Gemini dropped: {e!r}")
        # A tool result or a notice ("o trabalho terminou") must not vanish in a reconnection: it goes out when Gemini is back.
        if ("toolResponse" in msg or "clientContent" in msg or "text" in msg.get("realtimeInput", {})) and len(self.outbox) < 20:
            self.outbox.append(msg)

    async def send_outbox(self):
        """After a reconnection. A new (not resumed) session never made the tool call, so the result goes as a notice."""
        pending, self.outbox = self.outbox, []
        for msg in pending:
            if "toolResponse" in msg and not self.resumed:
                r = msg["toolResponse"]["functionResponses"][0]
                msg = {"realtimeInput": {"text": f"[sistema] A conexão caiu enquanto {r['name']} rodava; o resultado chegou "
                                                 f"agora: {json.dumps(r['response'], ensure_ascii=False)[:3000]}"}}
            await self.to_gemini(msg)

    async def connect(self):
        self.resumed = self.handle is not None
        self.gemini = await self.http.ws_connect(GEMINI_WS, headers={"x-goog-api-key": self.key}, max_msg_size=0, heartbeat=30)
        await self.gemini.send_str(json.dumps(setup_message(self.voice, self.handle)))

    def flush(self):
        if self.user_text.strip():
            log_talk(f"{USER}", self.user_text)
        if self.model_text.strip():
            log_talk("Jarvis", self.model_text)
        self.user_text, self.model_text = "", ""

    async def gemini_loop(self):
        refusals = offline = 0
        while not self.closed:
            reason, network = "", False
            try:
                await self.connect()
                while True:
                    m = await self.gemini.receive()
                    if m.type in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                        refusals = offline = 0
                        try:   # one bad message (a vault write failing, say) must not drop the conversation
                            await self.on_gemini(json.loads(m.data if m.type == aiohttp.WSMsgType.TEXT else m.data.decode()))
                        except Exception:
                            log("mensagem do Gemini falhou: " + traceback.format_exc()[-1500:])
                    else:  # CLOSE carries Google's reason in .extra (quota, invalid setup, session expired…)
                        reason = f"{self.gemini.close_code} {m.extra or m.data or ''}".strip()
                        break
            except Exception as e:  # network hiccup: wait a moment and resume the same conversation
                reason = repr(e)
                # No network (wifi dropped, Mac waking up) is not Google refusing: a 4xx answer (bad key, quota) is.
                network = not (isinstance(e, aiohttp.WSServerHandshakeError) and 400 <= e.status < 500)
            if self.closed:
                return
            log(f"Gemini closed: {reason}")
            self.flush()   # what was said before the drop goes to the vault now, not after the next turn
            if network:   # before, 3 tries in ~5 s and the window stayed dead; now it waits for the network to come back
                offline += 1
                await self.to_browser(type="status", text="Sem conexão, tentando de novo…")
                await asyncio.sleep(min(30, 1.5 * 2 ** (offline - 1)))
                continue
            if self.handle and ("not found" in reason or "expired" in reason or reason.startswith("1011")):
                # Google dropped the session (internal error, expiry): resuming can't work, so start a fresh one.
                # The new session rereads memory and today's conversation from the vault, so context carries over.
                self.handle = None
                await self.to_browser(type="status", text="Reconectando…")
                await asyncio.sleep(1)
                continue
            refusals += 1
            if refusals >= 3:
                await self.to_browser(type="error", text=f"O Gemini recusou a conexão: {reason}")
                return
            await self.to_browser(type="status", text="Reconectando…")
            await asyncio.sleep(1.5 * refusals)

    async def on_gemini(self, data):
        if "setupComplete" in data:
            proj = active_project()
            await self.to_browser(type="ready", voice=self.voice, switches=ui_switches(),
                                  project=proj.summary() if proj else None)
            await self.send_outbox()
            if job := self.app.get("trabalho"):   # a window opened mid-job still shows it running
                await self.busy("trabalho", job.get("passo") or "Trabalho longo: " + job["titulo"])
        if "sessionResumptionUpdate" in data:
            u = data["sessionResumptionUpdate"]
            if u.get("resumable") and u.get("newHandle"):
                self.handle = u["newHandle"]
        if "goAway" in data:  # the connection is about to end: open a new one that resumes the conversation
            await self.gemini.close()
        if "toolCall" in data:
            for call in data["toolCall"].get("functionCalls", []):
                asyncio.create_task(self.on_tool(call))
        sc = data.get("serverContent")
        if sc:
            if sc.get("interrupted"):
                self.thoughts.reset()
                self.flush()   # Jarvis's cut-off answer is saved as it stood, not glued to the next one
                await self.to_browser(type="interrupted")
            if "inputTranscription" in sc:
                t = sc["inputTranscription"].get("text", "")
                self.user_text += t
                if t.strip():
                    self.tool_since_user = False
                await self.to_browser(type="user_text", text=t)
            if "outputTranscription" in sc:
                t = self.thoughts(sc["outputTranscription"].get("text", ""))
                if t:
                    self.model_text += t
                    await self.to_browser(type="model_text", text=t)
            for part in (sc.get("modelTurn") or {}).get("parts", []):
                blob = part.get("inlineData")
                if blob and blob.get("mimeType", "").startswith("audio/"):
                    await self.to_browser(type="audio", data=blob["data"])
            if sc.get("turnComplete"):
                self.thoughts.reset()
                said = self.model_text
                self.flush()
                await self.check_claims(said)
                await self.to_browser(type="turn_complete")
                if self.reconnect_after_turn:
                    self.reconnect_after_turn = False
                    await self.gemini.close()

    async def on_tool(self, call):
        name, args, cid = call.get("name"), call.get("args") or {}, call.get("id")
        self.running[cid] = name
        self.tool_since_user = self.tool_in_turn = True
        label = BUSY.get(name)
        progress = lambda text: self.busy(cid, text)   # noqa: E731
        sw = switches()
        # Jarvis works in silence; only a task that runs long gets one short "still on it".
        deep = name == "pesquisar_web" and args.get("profundidade") == "profunda"
        nudge = asyncio.create_task(self.still_working(deep)) if name in SLOW_TOOLS else None
        try:
            if label:
                try:
                    text = label(args)
                except Exception:   # odd arguments: the screen still shows something, and the tool still runs
                    text = name
                await self.busy(cid, text)
            if name in ("olhar_tela", "abas_chrome", "ler_abas_chrome") and not sw["vision"]:
                result = {"error": "A VISÃO está DESLIGADA (ela vale para a tela e para as abas do Chrome). "
                                   f"{USER} pode ligar no interruptor 'Visão' do app."}
            elif name == "pesquisar_no_chrome" and not sw["actions"]:
                result = {"error": f"As ações no Mac estão DESLIGADAS. {USER} pode ligar no interruptor 'Ações' do app."}
            elif name == "abas_chrome":
                tabs, err = await chrome_tabs()
                if err:
                    result = {"error": err}
                else:
                    self.tabs = tabs
                    log_turn("Visão", f"listou {len(tabs)} abas do Chrome")
                    await self.to_browser(type="vision", state="start", text=f"Vendo as {len(tabs)} abas do Chrome")
                    await self.to_browser(type="vision", state="done", ok=True)
                    result = {"result": [f"{n}. {title} — {url}" for n, _, _, title, url in tabs][:80]}
            elif name == "ler_abas_chrome":
                tabs = getattr(self, "tabs", None) or (await chrome_tabs())[0] or []
                chosen = [t for t in tabs if t[0] in set(args.get("numeros") or [])][:6]
                if not chosen:
                    result = {"error": "Nenhuma aba com esses números. Use abas_chrome de novo para ver a lista atual."}
                else:
                    question = args.get("pergunta", "Resuma o conteúdo.")
                    await self.to_browser(type="vision", state="start", text="Lendo: " + "; ".join(t[3][:60] for t in chosen))
                    log_turn("Visão", "leu abas do Chrome: " + "; ".join(t[3] for t in chosen))
                    parts, by_url = [], []
                    for n, w, t, title, url in chosen:
                        text = await chrome_tab_text(w, t)
                        if text:
                            parts.append({"text": f"--- Aba {n}: {title} ({url})\n{text}"})
                        else:
                            by_url.append(url)
                            parts.append({"text": f"--- Aba {n}: {title}. Leia o conteúdo em: {url}"})
                    parts.append({"text": f"Estas são abas que {USER} tem abertas no Chrome. {question}"})
                    result = await read_with_gemini(self.http, self.key, parts, use_web=bool(by_url))
                    await self.to_browser(type="vision", state="done", ok="result" in result)
                    result["scheduling"] = "WHEN_IDLE"
            elif name == "pesquisar_no_chrome":
                q = args.get("busca", "")
                proc = await asyncio.create_subprocess_exec("/usr/bin/open", "-a", "Google Chrome",
                                                            "https://www.google.com/search?q=" + urllib.parse.quote(q))
                await proc.wait()
                log_turn("Ação", f"abriu no Chrome a pesquisa: {q}")
                await self.to_browser(type="task", state="start", text=f"Pesquisando no Chrome: {q}")
                await self.to_browser(type="task", state="done", text="Aberto no Chrome.", ok=True)
                result = {"result": "Pesquisa aberta numa aba nova do Chrome."}
            elif name in ("ler_link", "pesquisar_web") and not sw["internet"]:
                result = {"error": f"A internet está DESLIGADA. {USER} pode ligar no interruptor 'Internet' do app."}
            elif name == "trabalho_longo" and (args.get("acao") or "iniciar") == "iniciar" and not sw["internet"]:
                result = {"error": f"A internet está DESLIGADA. {USER} pode ligar no interruptor 'Internet' do app."}
            elif name == "trabalho_longo":
                result = await trabalho.tool(self.app, args)
            elif name == "executar_no_mac" and not sw["actions"]:
                result = {"error": f"As ações no Mac estão DESLIGADAS. {USER} pode ligar no interruptor 'Ações' do app."}
            elif name == "olhar_tela":
                question = args.get("pergunta", "Descreva o que está na tela.")
                await self.to_browser(type="vision", state="start", text=question)
                image = await screenshot()
                if image is None:
                    result = {"error": f"O macOS bloqueou a foto da tela: falta a permissão. {USER} precisa ligar o Jarvis em Ajustes do "
                                       "Sistema > Privacidade e Segurança > Gravação de Tela e Áudio do Sistema, e depois reabrir o Jarvis. "
                                       "Para o Chrome isso não é necessário: use abas_chrome."}
                else:
                    log_turn("Visão", f"olhou a tela: {question}")
                    result = await read_with_gemini(self.http, self.key, [
                        {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(image).decode()}},
                        {"text": f"Esta é a tela de {USER} agora. {question} Se houver código ou erro, leia com atenção e explique."}])
                await self.to_browser(type="vision", state="done", ok="result" in result)
                result["scheduling"] = "WHEN_IDLE"
            elif name == "ler_link":
                url, question = args.get("url", ""), args.get("pergunta", "Resuma e explique de forma simples.")
                await self.to_browser(type="task", state="start", text=f"Lendo {url}")
                log_turn("Link", url)
                if re.search(r"(youtube\.com|youtu\.be)/", url):
                    parts = [{"fileData": {"fileUri": url}}, {"text": question}]
                    result = await read_with_gemini(self.http, self.key, parts)
                else:
                    try:   # opened from the user's Mac like a browser: news sites block Google's and Claude's fetchers, not this
                        title, text, links = await sources.fetch_page(self.http, url)
                        heads = "\n".join(f"- {l}" for l, _ in links[:80])
                        result = await read_with_gemini(self.http, self.key, [{"text": f"{question}\n\nPágina: {title} ({url}), lida agora.\n"
                                                                                       f"Manchetes:\n{heads}\n\nTexto:\n{text[:40000]}"}])
                    except Exception as e:   # noqa: BLE001 — fall back to Google's own reader
                        log(f"ler_link local falhou ({url}): {e!r}")
                        result = await read_with_gemini(self.http, self.key, [{"text": f"{question}\n\nEndereço: {url}"}], use_web=True)
                await self.to_browser(type="task", state="done", text=(result.get("result") or result.get("error", ""))[:400], ok="result" in result)
                result["scheduling"] = "WHEN_IDLE"
            elif name == "pesquisar_web":
                question, depth = args.get("pergunta", ""), args.get("profundidade", "rapida")
                await self.to_browser(type="task", state="start",
                                      text=("Pesquisa profunda: " if depth == "profunda" else "Pesquisando: ") + question)
                log_turn("Pesquisa", f"({depth}) {question}")
                found = await research.research(question, depth, clean_env(), progress)
                if "error" in found:
                    log_turn("Resultado", found["error"])
                    await self.to_browser(type="task", state="done", text=found["error"], ok=False)
                    result = {"error": found["error"] + f" Diga isso a {USER}; não invente a resposta."}
                else:
                    log_turn("Resultado", found["fala"])
                    note = None
                    if depth == "profunda":
                        path, _ = VAULT.write_note(f"Pesquisa — {found.get('titulo') or question[:60]}",
                                                   research.as_note(question, found), "referencia", "reference")
                        note = str(path.relative_to(VAULT.root))
                    await self.to_browser(type="task", state="done", text=f"Pesquisa concluída em {found['segundos']} s", ok=True)
                    await self.to_browser(type="research", title=found.get("titulo", ""), text=found["resposta"],
                                          sources=found["fontes"], note=note,
                                          link=f"obsidian://open?vault={VAULT.root.name}&file={note}" if note else None)
                    result = {"result": {"responda_assim": found["fala"],
                                         "detalhes_para_perguntas_seguintes": found["resposta"][:3000]}}
            elif name == "ajustar_permissao":
                key, on = args.get("permissao"), bool(args.get("ligada"))
                if key in SWITCHES:
                    await set_switch(self.app, key, on, asked_by=self)
                    result = {"result": f"{SWITCHES[key]} agora está {'ligada' if on else 'desligada'}."}
                else:
                    result = {"error": "Permissão desconhecida."}
            elif name == "assistir_video" and not sw["internet"]:
                result = {"error": f"A internet está DESLIGADA. {USER} pode ligar no interruptor 'Internet' do app."}
            elif name == "assistir_video":
                result = await start_watch(self.app, args.get("fonte", ""), args.get("projeto", ""), args.get("foco", ""))
            elif name == "gravar_tela" and args.get("acao") != "parar" and not sw["internet"]:
                result = {"error": f"A internet está DESLIGADA. {USER} pode ligar no interruptor 'Internet' do app."}
            elif name == "gravar_tela":
                result = await record_tool(self.app, args)
            elif name == "estudar_curso" and args.get("acao") == "iniciar" and not sw["internet"]:
                result = {"error": f"A internet está DESLIGADA. {USER} pode ligar no interruptor 'Internet' do app."}
            elif name == "estudar_curso":
                result = await course_tool(self.app, args)
            elif name == "projeto":
                result = await project_tool(self.app, args, self)
            elif name == "rever_trecho":
                result = await review_clip(self.app, args, self)
                result["scheduling"] = "WHEN_IDLE"
            elif name == "video_na_tela":
                result = await study_tool(self.app, args, self)
            elif name == "mac_rapido" and not sw["actions"]:
                result = {"error": f"As ações no Mac estão DESLIGADAS. {USER} pode ligar no interruptor 'Ações' do app."}
            elif name == "mac_rapido":
                said = await asyncio.to_thread(mac.run, args)
                log_turn("Ação", f"{args.get('acao')} {args.get('alvo', '')}".strip() + f": {said}")
                await self.to_browser(type="task", state="done", text=said, ok=True)
                result = {"result": said}
            elif name == "executar_no_mac":
                task = args.get("tarefa", "")
                self.flush()
                await self.to_browser(type="task", state="start", text=task)
                log_turn("Tarefa", task)
                result = await run_task(task, settings()["task_timeout"], progress)
                said = result.get("result") or result.get("error", "")
                log_turn("Resultado", said)
                await self.to_browser(type="task", state="done", text=said, ok="result" in result)
                result["scheduling"] = "WHEN_IDLE"
            elif name == "lembrar":
                fact = " ".join(args.get("fato", "").split())
                how = VAULT.remember(fact, args.get("topico", "outros"))
                await self.to_browser(type="memory", text=("Atualizado: " if how == "updated" else "") + fact)
                result = {"result": "Guardado." if how == "added" else "Atualizei o fato que já existia.", "scheduling": "SILENT"}
            elif name == "anotar":
                path, how = VAULT.write_note(args.get("titulo", "Sem título"), args.get("conteudo", ""),
                                             args.get("area", "inbox"), args.get("tipo", "plan"), args.get("status", "active"))
                where = str(path.relative_to(VAULT.root))
                log_turn("Nota", f"{'criou' if how == 'created' else 'atualizou'} {where}")
                await self.to_browser(type="note", text=where, how=how,
                                      link=f"obsidian://open?vault={VAULT.root.name}&file={where}")
                result = {"result": f"Nota {'criada' if how == 'created' else 'atualizada'} em {where}.", "scheduling": "SILENT"}
            elif name == "substituir":
                subject, new = args.get("assunto", ""), [f for f in args.get("fatos_novos") or [] if f.strip()]
                title = args.get("nota_titulo", "").strip()
                note = VAULT.find_note(title) if title else None
                if not args.get("confirmado"):
                    old = [f["text"] for f in VAULT.facts_about(subject)]
                    result = {"result": {"vai_apagar": old or "nenhum fato sobre esse assunto",
                                         "vai_gravar": new, "nota": (f"reescrever {note.stem}" if note else
                                                                     (f"criar {title}" if title else "nenhuma"))},
                              "scheduling": "INTERRUPT"}
                else:
                    removed = VAULT.replace_facts(subject, new, args.get("topico", "outros"))
                    log_turn("Substituição", f"{subject}: saiu {len(removed)}, entrou {len(new)}")
                    await self.to_browser(type="memory", text=f"Substituído ({subject}): " + "; ".join(new))
                    done = f"Apaguei {len(removed)} fato(s) antigo(s) e gravei {len(new)} novo(s)."
                    if title and args.get("nota_conteudo"):
                        path, how = VAULT.rewrite_note(title, args["nota_conteudo"], args.get("area", "inbox"), "plan", "active",
                                                       HERE / "historico")
                        where = str(path.relative_to(VAULT.root))
                        await self.to_browser(type="note", text=where, how="updated",
                                              link=f"obsidian://open?vault={VAULT.root.name}&file={where}")
                        done += f" Nota {where} {'reescrita' if how == 'rewritten' else 'criada'}."
                    result = {"result": done, "scheduling": "WHEN_IDLE"}
            elif name == "fonte_projeto":
                result = await source_tool(self.app, args)
            elif name == "agenda":
                result = await agenda_tool(self.app, args)
            elif name == "notas":
                result = await notes_tool(self.app, args)
            elif name == "mostrar_texto":
                title, text = " ".join(args.get("titulo", "").split()), args.get("texto", "").strip()
                if not text:
                    result = {"error": "O texto veio vazio. Chame de novo com o texto inteiro."}
                else:
                    log_turn("Texto na tela", f"{title}: {text}"[:4000])   # the chat reloads its history from here
                    await self.to_browser(type="document", title=title, text=text)
                    result = {"result": f"O texto inteiro já está no chat, na tela de {USER}. Diga isso em uma frase, com o "
                                        "essencial, e não leia o texto em voz alta."}
            elif name == "ler_nota":
                text = VAULT.read_note(args.get("titulo", ""))
                result = {"result": text[-8000:]} if text else {"error": "Não achei uma nota com esse título no cofre."}
            elif name == "buscar_memoria":
                proj = active_project()
                where = None if args.get("onde") == "tudo" or not proj else proj.id
                # In a thread: indexing the vault can take a while and would freeze the audio meanwhile
                found = await asyncio.to_thread(busca.search, args.get("pergunta", ""), where, settings()["vault"])
                result = ({"result": "\n\n".join(f'### {f["titulo"]}\n{f["texto"]}' for f in found)} if found else
                          {"error": "Não achei nada sobre isso" + (" neste projeto; tente onde='tudo'." if where else ".")})
            else:
                result = {"error": f"Ferramenta desconhecida: {name}"}
        except Exception as e:
            log(f"tool {name} failed: {e!r}")
            result = {"error": f"Falhou: {e}"}
        if nudge:
            nudge.cancel()
        if label:
            await self.busy(cid, None)
        self.running.pop(cid, None)
        if (label or name == "mostrar_texto") and "error" not in result:
            self.last_work = time.time()
        await self.to_gemini({"toolResponse": {"functionResponses": [{"id": cid, "name": name, "response": result}]}})

    async def notify(self, text, work=True):
        """A background job (video, course, recording, long work) telling Jarvis it finished: real work done, unless it failed."""
        if work:
            self.last_work = time.time()
        await self.to_gemini({"realtimeInput": {"text": text}})

    async def busy(self, cid, text):
        """What the screen shows under the purple reactor while tool `cid` runs; None when it ends."""
        await self.to_browser(type="busy", id=cid, text=text, done=text is None)

    async def check_claims(self, said):
        """After each spoken turn: if Jarvis claimed work that no tool backs, warn the user on screen and have Jarvis correct it."""
        in_turn, self.tool_in_turn = self.tool_in_turn, False
        if self.correcting:
            self.correcting = False
            return
        busy = bool(self.running) or bool(self.app["jobs"]) or in_turn
        claim = unbacked_claim(said, busy, self.tool_since_user or time.time() - self.last_work < RECENT_WORK)
        if claim:
            log(f"afirmação sem ferramenta: {claim!r}")
            self.correcting = True
            await self.to_browser(type="warning", text=f"O Jarvis disse “{claim}”, mas nenhuma ferramenta rodou para isso. "
                                                      "Pedi para ele conferir.")
            await self.to_gemini({"realtimeInput": {"text": CORRECTION.format(claim, user=USER)}})

    async def keep_alive(self):
        """Gemini closes a session after ~2 min with no input (1008 'client inactivity', every 2 min in jarvis.log), and a
        task still running would then answer into a new connection. While the mic is muted, a little silence keeps it open."""
        try:
            while self.muted and not self.closed:
                await asyncio.sleep(KEEPALIVE_EVERY)
                if self.muted and not self.closed:
                    await self.to_gemini({"realtimeInput": {"audio": {"data": SILENCE, "mimeType": "audio/pcm;rate=16000"}}})
        finally:
            self.keepalive = None

    async def still_working(self, deep=False):
        await asyncio.sleep(SLOW_AFTER)
        hint = ("é uma pesquisa profunda e leva alguns minutos; diga algo curto como 'tô fazendo uma pesquisa completa, "
                "leva uns minutinhos, te aviso' " if deep else "diga só algo bem curto e natural, como 'tô vendo aqui, já te falo', ")
        await self.to_gemini({"realtimeInput": {"text": f"[sistema] A tarefa ainda está rodando: {hint}e aguarde o resultado."}})

    async def browser_loop(self):
        async for m in self.browser:
            if m.type != aiohttp.WSMsgType.TEXT:
                continue
            msg = json.loads(m.data)
            if msg["type"] == "audio":
                await self.to_gemini({"realtimeInput": {"audio": {"data": msg["data"], "mimeType": "audio/pcm;rate=16000"}}})
            elif msg["type"] == "audio_end":
                await self.to_gemini({"realtimeInput": {"audioStreamEnd": True}})
            elif msg["type"] == "event":   # something the app did (e.g. woken by claps), not words the user said
                await self.to_gemini({"realtimeInput": {"text": msg["text"]}})
            elif msg["type"] == "text":
                self.flush()
                self.tool_since_user = False
                log_talk(f"{USER}", msg["text"])
                where = study_position(self)
                text = f"[tela de estudo: {where}] {msg['text']}" if where else msg["text"]
                await self.to_gemini({"realtimeInput": {"text": text}})
            elif msg["type"] == "attach":   # the chat's + button: images, PDFs, texts, for this conversation only
                task = asyncio.create_task(anexos_chat.send(self, msg, study_position(self)))
                self.attaching.add(task)
                task.add_done_callback(self.attaching.discard)
            elif msg["type"] == "mute":   # the page stopped (or resumed) sending the microphone; the conversation goes on
                self.muted = bool(msg.get("on"))
                if self.muted and self.keepalive is None:
                    self.keepalive = asyncio.create_task(self.keep_alive())
            elif msg["type"] == "study":   # the study screen reports which video and minute the user is on
                self.study = None if msg.get("closed") else {**{k: msg.get(k) for k in ("pid", "sid", "title", "pos", "playing")},
                                                             "at": time.time()}


async def ws_handler(request):
    browser = web.WebSocketResponse(max_msg_size=0, heartbeat=30)
    await browser.prepare(request)
    session = Session(request.app, browser)
    request.app["sessions"].add(session)
    gemini_task = asyncio.create_task(session.gemini_loop())
    try:
        await session.browser_loop()
    except Exception as e:
        log(f"window connection failed: {e!r}")
    finally:
        request.app["sessions"].discard(session)
        session.closed = True
        session.flush()
        if session.gemini is not None:
            await session.gemini.close()
        gemini_task.cancel()
    return browser


async def index(_):
    """The page, with the user's name and home city from config.json (the page has no other way to know them before
    its scripts run)."""
    page = (HERE / "static" / "index.html").read_text(encoding="utf-8")
    data = json.dumps({"user": USER, "city": settings()["city"]}, ensure_ascii=False).replace("</", "<\\/")
    page = page.replace("</head>", f"<script>window.JARVIS = {data};</script>\n</head>", 1)
    return web.Response(text=page, content_type="text/html", headers={"Cache-Control": "no-store"})


async def api_history(_):
    return web.json_response({"lines": VAULT.transcript_lines(60)})


async def api_memory(_):
    return web.json_response({"facts": VAULT.facts(), "vault": VAULT.root.name,
                              "file": str(VAULT.facts_file.relative_to(VAULT.root))})


async def api_remember(request):
    fact = " ".join((await request.json()).get("fato", "").split())
    if fact:
        VAULT.remember(fact, (await request.json()).get("topico", "outros"))
    return web.json_response({"facts": VAULT.facts()})


async def api_upload(request):
    """Saves a dropped file and tells the live conversation where it is."""
    reader = await request.multipart()
    UPLOADS.mkdir(exist_ok=True)
    saved = []
    async for part in reader:
        if not part.filename:
            continue
        name = re.sub(r"[/\\:]", "_", part.filename)
        dest = UPLOADS / f"{datetime.datetime.now():%Y%m%d-%H%M%S}-{name}"
        with open(dest, "wb") as f:
            while chunk := await part.read_chunk(1 << 20):
                f.write(chunk)
        saved.append(str(dest))
    note = f"{USER} enviou " + ("o arquivo " if len(saved) == 1 else "os arquivos ") + ", ".join(saved) + \
           ". Se for um vídeo e ele quiser que você assista ou estude, use assistir_video com o caminho. Para outros arquivos, " + \
           ("pergunte o que ele quer fazer, ou, se ele já disse, peça ao Claude pela ferramenta executar_no_mac." if has_executor() else
            "diga o que você consegue fazer com ele.")
    if request.query.get("avisar") == "0":   # the chat's + sends the paths itself, inside the user's message
        log_turn("Arquivo", ", ".join(saved))
        return web.json_response({"saved": saved})
    for s in list(request.app["sessions"]):
        log_turn("Arquivo", ", ".join(saved))
        await s.to_gemini({"realtimeInput": {"text": note}})
    return web.json_response({"saved": saved})


async def set_switch(app, key, on, asked_by=None):
    """Saves a switch, tells every open window, and reconnects live sessions so Gemini gets the new tools and rules.
    The session that asked by voice reconnects after it finishes answering, so its confirmation isn't cut off."""
    if switches()[key] == on:
        return
    save_setting(key, on)
    log_turn("Permissão", f"{SWITCHES[key]} {'ligada' if on else 'desligada'}")
    for s in list(app["sessions"]):
        await s.to_browser(type="settings", switches=ui_switches())
        if s is asked_by:
            s.reconnect_after_turn = True
        elif s.gemini is not None and not s.gemini.closed:
            await s.gemini.close()   # gemini_loop reopens it at once, resuming the same conversation


def ui_switches():
    """Gemini permissions plus the app's own switches (claps), as the page shows them."""
    return {**switches(), "claps": bool(settings().get("claps", True))}


async def api_settings(request):
    if request.method == "POST":
        body = await request.json()
        for k, v in body.items():
            if k in SWITCHES:
                await set_switch(request.app, k, bool(v))
            elif k == "claps":
                save_setting("claps", bool(v))   # read by the app itself (Claps.swift), not by Gemini
    return web.json_response({"switches": ui_switches()})


# ---------- Projects and videos ----------


# ---------- Calendar (agenda.py): the page edits it with PUT, Jarvis with the agenda tool; every change reaches the screen ----------


# ---------- Notes (notas.py): the page PUTs the whole notebook, Jarvis uses the notas tool; every change reaches the screen ----------


# ---------- Watching by recording the screen (app/Gravar.swift inside Jarvis.app): for videos that can't be downloaded ----------


# ---------- Course mode (course.py): study a whole course in Chrome, lesson after lesson, like a student ----------


# ---------- Project sources that aren't videos: sites (optionally daily) and documents (sources.py) ----------


# ---------- Studio (NotebookLM-style projects, notebook.py) ----------


async def summarize_past_days(app):
    """Gives each finished day a short summary, so a new conversation reads a few lines per day instead of whole transcripts."""
    for path in VAULT.days_needing_summary():
        talk = "\n".join(f"{x['time']} {x['who']}: {x['text']}" for x in VAULT.spoken_lines(path))[-30000:]
        r = await read_with_gemini(app["http"], app["key"], [{"text":
            f"Resuma esta conversa entre {USER} e o assistente Jarvis em 3 a 6 linhas curtas, começando cada uma com '- '. "
            "Registre só o que importa lembrar depois: assuntos tratados, decisões, pedidos, ideias e o que ficou pendente. "
            "Para cada tarefa pedida (linhas Tarefa e Resultado), diga se foi feita ou NÃO foi feita: o Jarvis lê isto no "
            "dia seguinte e não pode achar que fez o que não fez. "
            "Ignore cumprimentos e testes.\n\n" + talk}])
        if "result" in r:
            VAULT.set_summary(path, r["result"])
            log(f"resumo de {path.stem} gravado")
        else:
            log(f"resumo de {path.stem} falhou: {r['error']}")
            break


async def make_app():
    VAULT.ensure()
    app = web.Application(client_max_size=1024 ** 3, middlewares=[notify_projects])
    app["key"] = api_key()
    app["http"] = aiohttp.ClientSession()
    app["sessions"] = set()
    app["events"] = set()   # one queue per open page (api_events)
    app["jobs"] = set()
    app["trabalho"] = {}   # the long job running now (trabalho.py); empty when none
    app["rec"] = {}   # the screen recording in progress, under "now"
    app["watcher"] = video.Watcher(app["http"], app["key"], log=log)
    app.router.add_get("/", index)
    app.router.add_get("/ws", ws_handler)
    app.router.add_get("/api/history", api_history)
    app.router.add_get("/api/memory", api_memory)
    app.router.add_post("/api/remember", api_remember)
    app.router.add_post("/api/upload", api_upload)
    app.router.add_post("/api/snip", anexos_chat.api_snip)
    app.router.add_route("*", "/api/settings", api_settings)
    app.router.add_route("*", "/api/projects", api_projects)
    app.router.add_post("/api/projects/close", api_project_open)
    app.router.add_route("*", "/api/projects/{pid}", api_project)
    app.router.add_post("/api/projects/{pid}/open", api_project_open)
    app.router.add_post("/api/projects/{pid}/videos", api_project_video)
    app.router.add_get("/api/projects/{pid}/sources/{sid}", api_source)
    app.router.add_route("*", "/api/projects/{pid}/sources/{sid}/edit", api_project_source)
    app.router.add_post("/api/projects/{pid}/sources", api_project_sources)
    app.router.add_post("/api/projects/{pid}/files", api_project_files)
    app.router.add_get("/api/projects/{pid}/sources/{sid}/video", api_source_video)
    app.router.add_route("*", "/api/gravacao", api_recording)
    app.router.add_post("/api/projects/{pid}/gravacao", api_recording)
    app.router.add_route("*", "/api/projects/{pid}/curso", api_course)
    for path, handler in (("/api/projects/{pid}/chat", api_nb_chat), ("/api/projects/{pid}/resumo", api_nb_overview),
                          ("/api/projects/{pid}/etiquetas", api_nb_tags), ("/api/projects/{pid}/texto", api_nb_text),
                          ("/api/projects/{pid}/copiar", api_nb_copy), ("/api/projects/{pid}/descobrir", api_nb_discover),
                          ("/api/projects/{pid}/notas", api_nb_notes), ("/api/projects/{pid}/notas/{nid}", api_nb_notes),
                          ("/api/projects/{pid}/studio", api_nb_studio), ("/api/projects/{pid}/studio/{aid}", api_nb_item),
                          ("/api/projects/{pid}/studio/{aid}/audio/{n}", api_nb_audio),
                          ("/api/colecoes", api_collections), ("/api/colecoes/{cid}", api_collections)):
        app.router.add_route("*", path, handler)
    app.router.add_get("/api/calendar", api_calendar)
    app.router.add_route("*", "/api/notes", api_notes)
    app.router.add_get("/api/eventos", api_events)
    app.router.add_put("/api/calendar/{date}", api_calendar_day)
    app.router.add_post("/api/calendar/files", api_calendar_upload)
    app.router.add_get("/api/calendar/files/{file}", api_calendar_file)
    app.router.add_static("/static", HERE / "static")

    async def close_http(a):
        await a["http"].close()
    app.on_cleanup.append(close_http)

    async def end_events(a):
        for q in list(a["events"]):
            q.put_nowait(None)
    app.on_shutdown.append(end_events)

    async def start_summaries(a):
        asyncio.create_task(summarize_past_days(a))
        a["daily"] = asyncio.create_task(daily_reader(a))
    app.on_startup.append(start_summaries)
    app.on_startup.append(check_screen)
    return app


async def check():
    """Connects once, asks for a short spoken greeting, and reports what came back."""
    key = api_key()
    async with aiohttp.ClientSession() as http:
        ws = await http.ws_connect(GEMINI_WS, headers={"x-goog-api-key": key}, max_msg_size=0)
        await ws.send_str(json.dumps(setup_message(settings()["voice"])))
        audio_bytes, said, started = 0, "", None
        while True:
            m = await ws.receive()
            if m.type not in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                print(f"fechou: {ws.close_code} {m.extra or ''}")
                break
            data = json.loads(m.data if m.type == aiohttp.WSMsgType.TEXT else m.data.decode())
            if "setupComplete" in data:
                started = asyncio.get_running_loop().time()
                await ws.send_str(json.dumps({"realtimeInput": {"text": "Em uma frase: o que você lembra sobre mim?"}}))
            sc = data.get("serverContent") or {}
            for part in (sc.get("modelTurn") or {}).get("parts", []):
                if part.get("inlineData"):
                    audio_bytes += len(base64.b64decode(part["inlineData"]["data"]))
            said += (sc.get("outputTranscription") or {}).get("text", "")
            if sc.get("turnComplete"):
                break
        took = asyncio.get_running_loop().time() - started if started else 0
        print(f"audio={audio_bytes / 48000:.1f}s  tempo={took:.1f}s  fala={said.strip()!r}")
        await ws.close()


if __name__ == "__main__":
    if "--check" in sys.argv:
        asyncio.run(check())
    else:
        port = settings()["port"]
        print(f"Jarvis em http://127.0.0.1:{port}", flush=True)
        web.run_app(make_app(), host="127.0.0.1", port=port, print=None)
