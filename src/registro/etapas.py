"""Etapas do pipeline de lote: do backup até o site (Etapa 9/D2).

P0 a P6 vêm de `docs/runbook-lote.md` (§3 e §4). P7 a P11 vêm do `task.md`
(8.C/C1b, Etapas 5D e 5F) e do `CLAUDE.md` §5.
"""

from src.registro.modelo import Etapa

_LLM_TAXONOMIA = (
    "OpenRouter, modelo z-ai/glm-5.3-flash, chave OPENROUTER_KEY_TAXONOMIA_EDITAL "
    "(trace cebraspe-4-taxonomia-edital)"
)
_LLM_CLASSIFICACAO = (
    "OpenRouter, modelo z-ai/glm-5.3-flash, "
    "chave OPENROUTER_KEY_CLASSIFICACAO_QUESTOES "
    "(trace cebraspe-5d-classificacao-questoes)"
)

ETAPAS: tuple[Etapa, ...] = (
    Etapa(
        id="P0",
        nome="Backup do banco",
        comandos=(
            "docker exec scraper-cebraspe-db pg_dump -U cebraspe -d cebraspe -Fc "
            "> scratch/backup_<data>_<sessao>.dump",
        ),
        scripts=(),
        entradas=("banco cebraspe (scraper-cebraspe-db)",),
        saidas=("scratch/backup_<data>_<sessao>.dump",),
        notas=(
            "Runbook §4.1. Conferir com pg_restore -l (95 TABLE DATA no lote de "
            "calibração); zero ou erro = não seguir."
        ),
    ),
    Etapa(
        id="P1",
        nome="Download dos PDFs do concurso",
        comandos=("venv/bin/python -m src.spider --slug <SLUG>",),
        scripts=("src.spider",),
        entradas=(
            "site do CEBRASPE (concurso encerrado)",
            "inventario/concursos.jsonl (contagens esperadas)",
        ),
        saidas=(
            "data/<ano>/CEBRASPE/<ORGAO>/Editais/*.pdf",
            "data/<ano>/CEBRASPE/<ORGAO>/Provas/*.pdf",
            "data/<ano>/CEBRASPE/<ORGAO>/Gabaritos/*.pdf",
            "data/<ano>/CEBRASPE/<ORGAO>/.manifest.json",
            "data/<ano>/CEBRASPE/<ORGAO>/provas_texto_link.json",
        ),
        depois_de=("P0",),
        adrs=("ADR-037",),
        notas="Runbook §4.2. Um comando por concurso. Todo PDF começa com %PDF-.",
    ),
    Etapa(
        id="P2",
        nome="Chunking do edital (sem LLM)",
        comandos=(
            "venv/bin/python - <edital_extracao.pdf>  "
            "# trecho do runbook §4.3, sem comando próprio no projeto",
        ),
        scripts=(),
        entradas=("data/<ano>/CEBRASPE/<ORGAO>/Editais/<edital_extracao>.pdf",),
        saidas=("saída na tela (sem gravação)",),
        depois_de=("P1",),
        notas=(
            "Gate de custo zero: chunk de 1 a 40 caracteres, nível None ou matéria que "
            "é nome de cargo barram o P3. Pendência da C2: comando próprio."
        ),
    ),
    Etapa(
        id="P3",
        nome="Taxonomia do edital pelo LLM (checkpoint de revisão)",
        comandos=(
            "venv/bin/python -m scripts.revisar_taxonomia_piloto "
            "data/<ano>/CEBRASPE/<ORGAO>/Editais/<edital_extracao>.pdf",
        ),
        scripts=("scripts.revisar_taxonomia_piloto",),
        entradas=("data/<ano>/CEBRASPE/<ORGAO>/Editais/<edital_extracao>.pdf",),
        saidas=(
            "revisao_piloto/<edital>.json",
            "revisao_piloto/<edital>.auditoria.json",
            "revisao_piloto/<edital>.validacao.json",
            "artefatos de revisão (relatórios e Datasette, via atualizar_revisao)",
        ),
        depois_de=("P2",),
        llm=_LLM_TAXONOMIA,
        portao_humano=(
            "Dono aprova cada edital no Datasette (relatorio/index.html), gravando "
            "status_revisao_humana = 'APROVADO...' no JSON. O agente nunca aprova "
            "(ADR-028). Antes disso o concurso fica pendente."
        ),
        adrs=("ADR-025", "ADR-028"),
        notas=(
            "Runbook §4.4. Falhas > 0 = reprocessar_falhas_piloto; alerta > 0 = ler o "
            ".validacao.json. Ao final chama atualizar_revisao, que também faz a carga "
            "do banco (P4) e a regra da árvore."
        ),
    ),
    Etapa(
        id="P4",
        nome="Carga das questões no banco",
        comandos=(
            "venv/bin/python -m src.stats_writer",
            "venv/bin/python -m scripts.extrair_questoes",
            "venv/bin/python -m scripts.extrair_questoes --reprocessar-erros",
        ),
        scripts=("src.stats_writer", "scripts.extrair_questoes"),
        entradas=(
            "revisao_piloto/<edital>.json",
            "data/<ano>/CEBRASPE/<ORGAO>/Provas/*.pdf",
            "data/<ano>/CEBRASPE/<ORGAO>/Gabaritos/*.pdf",
            "tabela fila_extracao_questoes",
        ),
        saidas=(
            "tabela provas",
            "tabela provas_cargos",
            "tabela textos_base",
            "tabela questoes",
            "tabela discursivas",
            "questoes/<caderno>.json",
            "questoes/<caderno>.auditoria.json",
        ),
        depois_de=("P3",),
        notas=(
            "Runbook §4.4 (P4 sai do P3). Lock pg_try_advisory_lock(5031001): se "
            "outro processo roda, sai sem fazer nada."
        ),
    ),
    Etapa(
        id="P4b",
        nome="Reprocessamento das questões (só se o parser mudar)",
        comandos=("venv/bin/python -m scripts.extrair_questoes --reprocessar",),
        scripts=("scripts.extrair_questoes",),
        entradas=(
            "data/<ano>/CEBRASPE/<ORGAO>/Provas/*.pdf",
            "tabela fila_extracao_questoes",
        ),
        saidas=(
            "tabela questoes",
            "tabela discursivas",
            "questoes/<caderno>.json",
        ),
        depois_de=("P4",),
        notas=(
            "Runbook §3 e §4.2 (P4b). Snapshot antes e depois: o piloto tem que ficar "
            "idêntico, com só a mudança esperada."
        ),
    ),
    Etapa(
        id="P5",
        nome="Conferência do lote (consultas a-e e PDF)",
        comandos=("docker exec scraper-cebraspe-db psql -U cebraspe -d cebraspe",),
        scripts=(),
        entradas=(
            "tabela provas",
            "tabela questoes",
            "tabela discursivas",
            "tabela fila_extracao_questoes",
            "view vw_questoes",
        ),
        saidas=("nenhuma (só leitura)",),
        depois_de=("P4",),
        adrs=("ADR-031",),
        portao_humano=(
            "Consultas a-e conferidas e 3 questões iguais ao PDF. Invariante do piloto "
            "inalterado: 2800 itens, 129 anuladas, 3029 apontamentos."
        ),
        notas=(
            "Runbook §4.5. Sem LLM. Consulta d (seções por caderno) e a de alternativa "
            "terminando em caixa alta pegam o defeito de cabeçalho de matéria."
        ),
    ),
    Etapa(
        id="P6",
        nome="Dispersão de conceitos na árvore",
        comandos=(
            "venv/bin/python -m scripts.detectar_dispersao_arvore --dry-run",
            "venv/bin/python -m scripts.detectar_dispersao_arvore --propor",
        ),
        scripts=("scripts.detectar_dispersao_arvore",),
        entradas=("canonico/arvore.json",),
        saidas=(
            "propostas pendentes em canonico/arvore.json",
            "docs/relatorios/dispersao_arvore_<data>.md (--dry-run padrão)",
        ),
        depois_de=("P5",),
        adrs=("ADR-030",),
        portao_humano=(
            "Dono aprova ou rejeita cada grupo de propostas do detector "
            "(curar_arvore --aprovar-proposta / --rejeitar-proposta), nunca em bloco. "
            "Norma em dois lugares vira proposta, não fusão do agente."
        ),
        notas=(
            "Runbook §4.6 (KAN-64). Custo zero. O detector erra às vezes, então cada "
            "grupo é uma decisão."
        ),
    ),
    Etapa(
        id="P7",
        nome="Curadoria da árvore mestre (portão humano)",
        comandos=(
            "venv/bin/python -m scripts.mapear_itens_novos --dry-run [--concurso <SLUG>]",
            "venv/bin/python -m scripts.mapear_itens_novos [--concurso <SLUG>]",
            "venv/bin/python -m scripts.propor_arvore --dry-run",
            "venv/bin/python -m scripts.propor_arvore",
            "venv/bin/python -m scripts.curar_arvore --html",
            "venv/bin/python -m scripts.curar_arvore --aprovar-proposta <ids>",
            "venv/bin/python -m scripts.curar_arvore --rejeitar-proposta <ids>",
        ),
        scripts=(
            "scripts.mapear_itens_novos",
            "scripts.propor_arvore",
            "scripts.curar_arvore",
        ),
        entradas=("canonico/arvore.json",),
        saidas=("canonico/arvore.json", "revisao_piloto/relatorio/arvore.html"),
        depois_de=("P6",),
        llm=(
            "OpenRouter, modelo z-ai/glm-5.3-flash, chave OPENROUTER_KEY_CURADORIA_ARVORE "
            "(trace cebraspe-5b2-curadoria-arvore; propor_arvore) e, no mapeamento de item "
            "novo, OPENROUTER_KEY_MAPEAMENTO_ITENS (cai na da curadoria; trace "
            "mapear_itens_novos). Ambos com REASONING_PADRAO"
        ),
        adrs=("ADR-030",),
        portao_humano=(
            "Pendências da árvore resolvidas pelo dono: itens de edital sem nó, "
            "mapeamentos e nós propostos. Só depois disso a classificação roda."
        ),
        notas=(
            "task.md, Etapa 8.C, C1b (KAN-57): 'árvore (pausa: curadoria)'. "
            "Aprovação sempre humana. O mapeamento de item novo de edital "
            "(mapear_itens_novos, runbook §4.6b) é o 1º passo: depois da extração do "
            "edital (P3) e da regra `mapear_novos_itens_por_regra`, antes da revisão do "
            "dono. O modelo escolhe só entre nós ativos da disciplina do item, grava "
            "`proposto/llm`, nunca cria nó nem disciplina (P72) nem aprova (A30). Rode o "
            "--dry-run e as checagens K22–K24 (P71) antes e depois."
        ),
    ),
    Etapa(
        id="P8",
        nome="Classificação das questões na árvore (LLM)",
        comandos=(
            "venv/bin/python -m scripts.classificar_questoes --dry-run",
            "venv/bin/python -m scripts.classificar_questoes [--caderno CODIGO] "
            "[--limite N]",
        ),
        scripts=("scripts.classificar_questoes",),
        entradas=(
            "tabela questoes",
            "tabela discursivas",
            "canonico/arvore.json",
            "canonico/classificacao_questoes.json",
        ),
        saidas=(
            "canonico/classificacao_questoes.json",
            "tabela questao_no (carga pelo stats_writer)",
            "tabela discursiva_no (carga pelo stats_writer)",
        ),
        depois_de=("P7",),
        llm=_LLM_CLASSIFICACAO,
        adrs=("ADR-032",),
        notas=(
            "task.md, Etapa 5D (sessão B) e C1b. Até 2 nós por questão; confiança "
            "alta, média ou baixa. Reexecução preserva classificações aprovadas."
        ),
    ),
    Etapa(
        id="P9",
        nome="Curadoria da classificação (portão humano)",
        comandos=(
            "venv/bin/python -m scripts.curar_classificacao --aprovar 'CHAVE:NO'",
            "venv/bin/python -m scripts.curar_classificacao --mapear 'CHAVE:NO1[,NO2]'",
        ),
        scripts=("scripts.curar_classificacao",),
        entradas=(
            "canonico/classificacao_questoes.json",
            "relatorio/classificacao.html",
        ),
        saidas=("canonico/classificacao_questoes.json",),
        depois_de=("P8",),
        adrs=("ADR-030", "ADR-032"),
        portao_humano=(
            "Dono decide a classificação de confiança média e baixa, e as questões "
            "sem nó. Pronto com 0 pendências (5D)."
        ),
        notas=(
            "task.md, Etapa 5D (sessão C). Toda aprovação ou rejeição é comando "
            "explícito do dono."
        ),
    ),
    Etapa(
        id="P10",
        nome="Relatórios e Datasette de revisão",
        comandos=("venv/bin/python -m scripts.atualizar_revisao",),
        scripts=("scripts.atualizar_revisao",),
        entradas=(
            "revisao_piloto/<edital>.json",
            "revisao_piloto/<edital>.auditoria.json",
            "canonico/arvore.json",
            "canonico/classificacao_questoes.json",
        ),
        saidas=(
            "revisao_piloto/relatorio/*.html",
            "revisao_piloto/revisao.db",
        ),
        depois_de=("P9",),
        adrs=("ADR-015", "ADR-019"),
        notas=(
            "Mesmo comando que roda no fim do P3. Reinicia o container Datasette. "
            "Servido com SSO do Cloudflare (ADR-015)."
        ),
    ),
    Etapa(
        id="P11",
        nome="Site público de questões",
        comandos=("uvicorn app.main:app  # a partir do diretório site/",),
        scripts=(),
        entradas=(
            "view vw_questoes",
            "schema app (respostas do site)",
        ),
        saidas=("site público (/questoes, /q/<concurso>/<caderno>/<numero>)",),
        depois_de=("P10",),
        adrs=("ADR-033",),
        notas=(
            "task.md, Etapas 5F e 5H; conferência no Chromium headless (C1b). Fora de "
            "scripts/: o código fica em site/."
        ),
    ),
)
