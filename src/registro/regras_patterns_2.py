"""Patterns do projeto, bullets 36 a 71 (fonte desde a D3; o CLAUDE.md cita só o núcleo)."""

from src.registro.modelo import Regra

REGRAS_PATTERNS_2: tuple[Regra, ...] = (
    Regra(
        id="P36",
        tipo="pattern",
        area="prova",
        texto="""A fila `fila_extracao_questoes` usa upsert por `sha256` e o writer nunca
altera `status`, que pertence ao consumidor.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P37",
        tipo="pattern",
        area="prova",
        texto="""Tipo/cargos de caderno vêm de `classificar_prova_por_texto` sobre o texto
do link já normalizado. Aceita `CONHECIMENTOS GERAIS` (CG) como básico, e
texto sem cargo significa "todos os cargos do concurso" (TCU). Edital
administrativo em `Provas/` fica fora da fila, com log.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P38",
        tipo="pattern",
        area="banco",
        texto="""Estatística "oficial" só em view que filtra `status_revisao = 'aprovado'`
(`vw_incidencia_topico`, `vw_edital_cobra_*`); a variante `_todas` é para
inspeção.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P39",
        tipo="pattern",
        area="edital",
        texto="""Restrição de cargo no nome da matéria (`(APENAS/SOMENTE PARA O(S)
CARGO(S) ...)`, `PADRAO_RESTRICAO_CARGO`) sai de `materia_normalizada` e
vira `cargos_restritos: list[int] | None`. Só sai do nome quando tem número
de cargo; sem número (`PARA OS CARGOS DE NÍVEL SUPERIOR`), fica no nome e
loga `[RESTRICAO_SEM_CARGO]`. Espaços repetidos são colapsados. Ver ADR-028.""",
        adrs=("ADR-028",),
        testes=(
            "tests/test_edital_parser.py::TestPadroes::test_padrao_restricao_cargo",
            "tests/test_edital_parser.py::TestBlocosDeConhecimento::test_dividir_avisa_restricao_sem_numero",
        ),
    ),
    Regra(
        id="P40",
        tipo="pattern",
        area="prova",
        texto="""Número de cargo em texto (link de caderno ou restrição de matéria) vem só
de `comparacao_texto.extrair_cargos_do_texto`, usada pelo parser e pelo
writer.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P41",
        nucleo=True,
        tipo="pattern",
        area="revisao",
        texto="""Aprovação da revisão humana é o `status_revisao_humana` do `<edital>.json`
(`APROVADO...`). O writer relê o JSON a cada carga.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P42",
        tipo="pattern",
        area="llm",
        texto="""O backfill confere o alinhamento pelo texto: o texto atual do chunk tem de
ser prefixo do `texto_enviado_llm` salvo (a assinatura final foi removida
depois, ADR-025), além de matéria/cargo.""",
        adrs=("ADR-025",),
        testes=(),
    ),
    Regra(
        id="P43",
        tipo="pattern",
        area="classificacao",
        texto="""Sinônimo (Etapa 5B, ADR-029): regra determinística conservadora
(`canonico.chave_regra`: "noções de" → `nocoes`, artigo inicial, parêntese,
forma única de norma `lei 9784 1999`, plural simples) junta e aprova
sozinha; o resto vai ao LLM por lista fechada de IDs e escopo (matéria →
assunto dentro da matéria → subassunto dentro do assunto) e sai
`proposto`. Proposta nunca muda o mapeamento: até a aprovação, cada nome
fica no grupo aprovado de antes (identidade).""",
        adrs=("ADR-029",),
        testes=(
            "tests/test_canonico.py::TestChaveRegraJunta::test_mesma_chave",
            "tests/test_canonico.py::TestChaveRegraJunta::test_forma_unica_de_norma",
        ),
    ),
    Regra(
        id="P44",
        tipo="pattern",
        area="revisao",
        texto="""Decisão humana de sinônimo (5B, histórico) foi via
`scripts/aprovar_sinonimos.py`. Desde a 5B.1 o `sinonimos.json` está
congelado, e o pipeline não o escreve mais.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P45",
        tipo="pattern",
        area="llm",
        texto="""`scripts/propor_sinonimos.py` custa tokens e **não** roda no pipeline
automático. Blocos já avaliados ficam em `avaliados_llm` e não são
reenviados.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P46",
        tipo="pattern",
        area="llm",
        texto="""Resposta de LLM sobre lista fechada é validada localmente (cada ID em
exatamente um grupo, nada inventado, nada entre blocos) com falha tipada; a
segunda tentativa leva o erro no prompt.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P47",
        tipo="pattern",
        area="banco",
        texto="""Subtópico é linha (`dim_subtopico` + `taxonomia_subitens`), não JSONB.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P48",
        tipo="pattern",
        area="arvore",
        texto="""Árvore mestre (ADR-030): o pai pertence ao **nó**, não ao edital. Item de
edital e questão **apontam** para nós (N:N, qualquer nível), e a
estatística soma subindo a árvore. O nome composto aponta para N nós, e o
item de uma matéria composta aponta para o nó da matéria certa.""",
        adrs=("ADR-030",),
        testes=(),
    ),
    Regra(
        id="P49",
        tipo="pattern",
        area="arvore",
        texto="""O ID de nó é estável. O nó semeado herda o ID do grupo aprovado da 5B.
Fundir marca `fundido` + `fundido_em` e nunca apaga ID; toda leitura
resolve o redirecionamento.""",
        adrs=(),
        testes=(
            "tests/test_curar_arvore.py::test_criar_renomear_mover_fundir_desmapear",
        ),
    ),
    Regra(
        id="P50",
        tipo="pattern",
        area="arvore",
        texto="""`canonico/arvore.json` só é lido e escrito por `src/arvore.py`
(`carregar`/`salvar`, uma linha por registro, ordenado por ID). A chave do
item é a chave natural do banco unida por `|` (`arvore.chave_item`), e o
apontamento é `{no_id, origem, status}`.""",
        adrs=(),
        testes=("tests/test_arvore.py::test_chave_item",),
    ),
    Regra(
        id="P51",
        nucleo=True,
        tipo="pattern",
        area="arvore",
        texto="""Decisão do dono na árvore só via `scripts/curar_arvore.py` (ou as funções
de `src/arvore.py`): `--mapear`, `--desmapear`, `--aprovar`, `--rejeitar`,
`--fundir`, `--mover`, `--criar`, `--renomear`. Operação humana sai
`aprovado`/`ativo`; mapear de novo um apontamento proposto o aprova. Erro de
validação não grava nada.""",
        adrs=(),
        testes=(
            "tests/test_curar_arvore.py::test_criar_renomear_mover_fundir_desmapear",
        ),
    ),
    Regra(
        id="P52",
        tipo="pattern",
        area="arvore",
        texto="""Item novo de edital (pipeline, `atualizar_revisao.atualizar_arvore`):
`canonico.mapear_novos_itens_por_regra` copia os nós de um item aprovado com
a mesma `chave_regra` **no mesmo nó-pai efetivo**; sem candidato, tenta a memória das
decisões do dono (P73). Regra ambígua ou pai sem nó fica pendente no `arvore.html`.
O log traz a contagem por regra de nome, por memória e pendentes. A `chave_regra` ignora os
prefixos "noções de", "fundamentos de" e "conceitos (básicos|gerais) de" (só "noções" liga
`nocoes`) e unifica gestão e gerenciamento; administração não entra, e a sigla entre
parênteses é só o campo `ChaveRegra.sigla`, nunca a chave (KAN-84). O mapeamento
`regra`/`aprovado` só atravessa disciplina com disciplina compatível ou nome específico:
título genérico (`canonico.TITULOS_GENERICOS`) nunca casa sozinho por nome (KAN-82).""",
        adrs=(),
        testes=(
            "tests/test_regra_arvore.py::test_mapeia_dentro_do_mesmo_pai_efetivo",
            "tests/test_regra_arvore.py::test_nao_mapeia_sob_outro_pai",
            "tests/test_regra_arvore.py::test_regra_ambigua_fica_pendente",
            "tests/test_canonico.py::TestChaveRegraPrefixosESinonimos",
        ),
    ),
    Regra(
        id="P53",
        tipo="pattern",
        area="banco",
        texto="""A carga (`stats_writer.aplicar_arvore`) grava **todos** os nós com o status
(as pontes nunca ficam sem FK) e as pontes só com apontamento `aprovado`,
já resolvido. `vw_no_caminho` só expõe a cadeia `ativa` (nó proposto não
conta antes da aprovação) e dá o `no_efetivo` do fundido. `dim_materia.nocoes`
vem de `chave_regra(nome).nocoes`, com ou sem mapeamento.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P54",
        tipo="pattern",
        area="banco",
        texto="""Estatística "edital cobra": ocorrência = `taxonomia_itens.id` distinto,
com o item básico expandido por cargo (`cargos_restritos` respeitado).
"Prova cobra": questão distinta. O mesmo item nunca conta 2× no mesmo nó.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P55",
        tipo="pattern",
        area="prova",
        texto="""Segmentação de cadernos de prova: número do item distinguido por x0 na margem da coluna (cluster/moda); duplicado/fora de ordem é bloqueante; recuo de continuação de item medido na faixa estrita de 12 a 24 pt (~18 pt real); gabaritos definitivos em hash (TCU/Câmara) ligados aos cadernos pelo código impresso no corpo do PDF (ADR-031).""",
        adrs=("ADR-031",),
        testes=(),
    ),
    Regra(
        id="P56",
        tipo="pattern",
        area="prova",
        texto="""Assinatura de grupo por hash na fila (`fila_extracao_questoes.assinatura_grupo`) garante reprocessamento automático quando os gabaritos ligados mudam, em qualquer status; `--reprocessar-erros` cobre órfãos e falhas.""",
        adrs=(),
        testes=(
            "tests/test_extrair_questoes.py::TestConsumidorPostgres::test_caderno_concluido_com_gabarito_alterado_e_reprocessado",
        ),
    ),
    Regra(
        id="P57",
        tipo="pattern",
        area="banco",
        texto="""Advisory lock de sessão (`pg_try_advisory_lock(5_031_001)`) garante consumidor de execução única sem concorrência destrutiva na fila.""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P58",
        tipo="pattern",
        area="prova",
        texto="""Versão do gabarito (`definitivo` × `preliminar`) classificada exclusivamente pelo cabeçalho (ou prefixo do nome de arquivo), com preferência determinística pelo definitivo e alertas informativos (`mais_de_um_gabarito` / `gabarito_preliminar`).""",
        adrs=(),
        testes=(
            "tests/test_extrair_questoes.py::TestConsumidorPostgres::test_dois_gabaritos_preliminar_e_definitivo",
        ),
    ),
    Regra(
        id="P59",
        tipo="pattern",
        area="prova",
        texto="""Caderno discursivo: quesitos extraídos estritamente a partir do comando (`redija`, `elabore`, `aborde`, `discorra`), evitando confusão com datas; tema anafórico rejeitado para `None` com alerta `tema_anaforico`.""",
        adrs=(),
        testes=(
            "tests/test_prova_parser.py::TestCadernoDiscursivo::test_tema_anaforico_gera_alerta",
        ),
    ),
    Regra(
        id="P60",
        tipo="pattern",
        area="prova",
        texto="""Padrão de resposta ligado preferencialmente por chave de título (`_chave_titulo`), garantindo ordem semântica correta mesmo com seções fora de ordem no PDF (chave ausente ou repetida cai na ligação por ordem); alertas `sem_quesitos` e `quesito_sem_valor`.""",
        adrs=(),
        testes=(
            "tests/test_prova_parser.py::TestCadernoDiscursivo::test_chave_titulo",
        ),
    ),
    Regra(
        id="P61",
        tipo="pattern",
        area="prova",
        texto="""Figuras: vinculadas à linha logo acima na mesma coluna com sobreposição horizontal (exceção item → preâmbulo).""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P62",
        tipo="pattern",
        area="prova",
        texto="""JSONs brutos de questões (`questoes/`) mantidos localmente e no `.gitignore` por volumetria, sendo regeneráveis de forma determinística por `scripts/extrair_questoes.py` (ADR-031).""",
        adrs=("ADR-031",),
        testes=(),
    ),
    Regra(
        id="P63",
        tipo="pattern",
        area="banco",
        texto="""Estatística de prova sobe a árvore e conta questão distinta (`count(DISTINCT questao_canonica_id)`): questão em subassunto soma em subassunto, assunto e matéria; questão em assunto soma em assunto e matéria, nunca descendo. Leitura com filtros agregados no site é feita via `fn_prova_cobra(...)` para garantir cálculo de percentual médio sob os filtros e desduplicação correta de questões básicas aplicadas em múltiplos cargos (ADR-032). Percentual entre provas é média em dois níveis: % do nó na prova distinta → média das provas distintas do concurso → média entre concursos, cada edital com peso 1. Prova distinta: cargos com o mesmo conjunto de questões canônicas no escopo, sob os filtros, contam 1× (assinatura `md5` + cargo representante). Nunca soma bruta nem média direta por cargo, que multiplica o básico (ou o específico) compartilhado pelo número de cargos (ADR-039, 8.M.1).""",
        adrs=(
            "ADR-032",
            "ADR-039",
        ),
        testes=(
            "tests/test_estatisticas_views.py::TestEstatisticasViews::test_fn_prova_cobra_conta_distinto_com_filtro_de_varios_cargos",
            "tests/test_estatisticas_views.py::TestEstatisticasViews::test_fn_prova_cobra_pct_do_universo_e_media_por_prova",
        ),
    ),
    Regra(
        id="P64",
        tipo="pattern",
        area="edital",
        texto="""Cobertura descendente edital × prova (`vw_edital_vs_prova`): item de edital em nó X cobre X e todos os descendentes de X. Na prova, o apontamento sobe; na comparação, checa se há ancestral-ou-igual previsto no edital daquele cargo (`cobrado_no_edital`, `no_edital_nunca_cobrado`, `cobrado_fora_do_edital`).""",
        adrs=(),
        testes=(
            "tests/test_estatisticas_views.py::TestEstatisticasViews::test_vw_edital_vs_prova_situacoes_e_cobertura_descendente",
        ),
    ),
    Regra(
        id="P65",
        tipo="pattern",
        area="banco",
        texto="""Peso por matéria em cargo (`vw_peso_materia_cargo`): proporção de cada matéria dentro do total da prova do cargo (básico + específico); matérias identificadas como nome de cargo (`nome_de_cargo = true`) são formatadas como `"Conhecimentos específicos — <cargo>"`.""",
        adrs=(),
        testes=(
            "tests/test_estatisticas_views.py::TestEstatisticasViews::test_vw_peso_materia_cargo",
            "tests/test_estatisticas_views.py::TestEstatisticasViews::test_vw_peso_materia_cargo_rotulo_nome_de_cargo",
        ),
    ),
    Regra(
        id="P66",
        tipo="pattern",
        area="banco",
        texto="""Discursivas analíticas (`vw_discursivas`): isola estritamente os temas e quesitos das 64 discursivas associadas aos nós da árvore mestre, sem interferir nem computar nas contagens das views de questões objetivas.""",
        adrs=(),
        testes=("tests/test_estatisticas_views.py",),
    ),
    Regra(
        id="P67",
        nucleo=True,
        tipo="pattern",
        area="site",
        texto="""O que fica fora do site é decidido só em `inventario/exclusoes.json` (slug, categoria
de `CATEGORIAS_EXCLUSAO`, motivo), lido por `inventario.carregar_exclusoes`. Concurso da
lista não é remapeado, não entra em amostra nem em lote e sai dos alertas. PDF de curso
de formação fica fora por `pdf_vai_para_o_site`. Alerta do inventário vem do texto do
link: antes de tratar como "sem arquivo", conferir a página ao vivo (ADR-037).""",
        adrs=("ADR-037",),
        testes=("tests/test_inventario.py::TestExclusoes::test_carregar_e_aplicar",),
    ),
    Regra(
        id="P68",
        tipo="pattern",
        area="testes",
        texto="""Testes e Ruff por etapas (`Makefile` e marcadores do `pytest.ini`):
- Etapa 1 (`make test-fast` / `pytest -m "unit and not db"`): executa `ruff check .` e testes unitários em memória (~18s, sem I/O nem banco).
- Etapa 2A (`make test-pipeline` / `pytest tests/`): suíte do scraper, parsers, taxonomia e árvore (~1m15s).
- Etapa 2B (`make test-site` / `pytest site/tests/`): suíte da web, rotas, API e simulados (~3m20s). Para pular testes lentos (>3s), usar `make test-site-fast` (`-m "not slow"`).
- Etapa 3 (`make test-all` / `make check`): suíte completa de 840 testes e verificação de formatação.
- Marcadores registrados no `pytest.ini`: `unit`, `db`, `pipeline`, `site`, `slow`.
- Configuração central do Ruff em `pyproject.toml` (targets, ignores e exclusões de `scratch/`, `data/`, etc.).""",
        adrs=(),
        testes=(),
    ),
    Regra(
        id="P69",
        tipo="pattern",
        area="site",
        texto="""Página nova em `docs/` entra no `nav` do `mkdocs.yml`; o `mkdocs build --strict` (no `make check`) recusa página fora do nav, link quebrado e âncora inexistente (ADR-040).""",
        adrs=("ADR-040",),
        testes=(),
    ),
    Regra(
        id="P70",
        nucleo=True,
        tipo="pattern",
        area="processo",
        texto="""Script novo em `scripts/` (ou módulo de `src/` com `__main__`) entra em
`src/registro/scripts.py`, e mudança de argparse, etapa, checagem, regra ou schema pede
`make docs-gerar`: o `tests/test_registro.py` recusa script fora do registro e página
gerada diferente do código (ADR-041). Regra nova entra só em `src/registro/regras_*.py`
(próximo id, área, ADR e teste guarda), cai numa tarefa de `src/registro/tarefas.py` pela
área, e só vai para o §6/§7 do `CLAUDE.md` se for do núcleo (`nucleo=True`, com link).""",
        adrs=("ADR-041",),
        testes=("tests/test_registro.py::test_todo_script_esta_no_registro",),
    ),
    Regra(
        id="P71",
        tipo="pattern",
        area="processo",
        texto="""Lote novo (ou qualquer passo que grava no banco) nunca altera o piloto
(PF_25_ADM, TCU_25_TEFC, IBAMA_25, STM_25, CD_25_NS: 2.800 itens, 129 anuladas,
3.029 apontamentos, chaves da 5D): as checagens K22–K24 rodam antes e depois, e
diferença bloqueia o lote.""",
        testes=(
            "tests/test_reconciliacao_inventario.py::test_regressao_piloto_chaves_5d_inalteradas",
        ),
        nucleo=True,
    ),
    Regra(
        id="P72",
        tipo="pattern",
        area="arvore",
        texto="""O nível matéria da árvore é a disciplina e só aceita os nomes de
`canonico/disciplinas.json`. Título de bloco de edital fora da lista vira **assunto**:
`mapear_novos_itens_por_regra` aponta o item para o único nó de disciplina ou assunto de mesmo
nome, e sem equivalente ele fica pendente para a curadoria. Esse casamento por nome só vale se
o nó é a própria disciplina, está numa disciplina inferida dos itens do bloco já aprovados,
ou o nome tem 2+ palavras relevantes e não é título genérico (`canonico.TITULOS_GENERICOS`);
par vetado pelo dono (por `chave_regra`) nunca é regravado, e fora disso o item fica pendente,
nunca `aprovado` (KAN-82). Proposta de LLM ou de regra
nunca cria disciplina (`propor` recusa `criar` de matéria); disciplina nova só por decisão
do dono. `scripts/auditar_arvore.py` fica verde antes de cada carga.""",
        adrs=("ADR-030",),
        testes=(
            "tests/test_regra_arvore.py::test_titulo_de_bloco_fora_da_lista_vira_assunto",
            "tests/test_regra_arvore.py::test_proposta_automatica_nao_cria_disciplina",
            "tests/test_regra_arvore.py::test_titulo_generico_nao_casa_com_assunto_de_outra_disciplina",
            "tests/test_regra_arvore.py::test_ramo_de_titulo_respeita_veto_de_outra_chave_com_mesma_chave_regra",
        ),
        nucleo=True,
    ),
    Regra(
        id="P73",
        tipo="pattern",
        area="arvore",
        texto="""O mapeamento de item novo aprende com o dono (`src/memoria_mapeamento.py`,
funções puras sobre a árvore) e a memória é parte do **passo determinístico**
(`canonico.mapear_novos_itens_por_regra`, rodado a cada extração, sem LLM). Ordem, nível a
nível (o assunto mapeado agora serve de pai do subassunto): (1) regra de nome; (2) memória:
item de mesma `chave_regra` e mesmo pai efetivo de uma decisão **aprovada**, ou apelido
exato de nó **fundido** (só nó fundido gera apelido, apontando ao destino ativo; nó ativo
nunca) na disciplina do pai, com candidato único, vira `regra`/`aprovado`; ambiguidade
fica pendente; nunca cria nó (P72). Só então o LLM (`mapear_itens_novos`, que antes
reexecuta o passo determinístico) recebe contexto de subitens extraído do `<edital>.json`
(entra no hash do cache), exemplos aprovados do dono e os pares rejeitados. Proposta
`proposto` nunca é fonte da memória (só vira fonte depois que o dono a aprova), par
rejeitado nunca é devolvido nem reproposto, e a memória não muda status existente (A30).""",
        adrs=("ADR-030", "ADR-032"),
        testes=(
            "tests/test_memoria_mapeamento.py::test_proposta_nao_aprovada_nao_e_fonte",
            "tests/test_mapeamento_llm.py::test_par_rejeitado_nao_e_reproposto_e_vai_no_prompt",
            "tests/test_mapeamento_llm.py::test_memoria_resolve_item_repetido_entre_dois_editais",
            "tests/test_regra_arvore.py::test_memoria_no_passo_deterministico",
        ),
    ),
)
