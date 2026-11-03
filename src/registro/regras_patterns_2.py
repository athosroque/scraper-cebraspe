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
decisões do dono (P73); sem candidato, assunto ou subassunto com pai mapeado vai para o
**filho único** (KAN-97): entre os filhos ativos (não propostos) dos nós do pai, juntos,
exatamente 1 tem a mesma `chave_regra` e nível compatível (assunto: assunto ou subassunto;
subassunto: subassunto); dois filhos iguais, mesmo sob pais diferentes do conjunto, são
ambíguos. Entra como `regra`/`aprovado` e conta em `por_filho`; título genérico e par
vetado pelo dono nunca casam, e o item de matéria (sem pai) não passa por aqui. Sem
candidato ainda, o subtópico herda o nó do tópico-pai quando ele é
folha (KAN-85): o pai tem exatamente 1 nó aprovado, ativo, de nível subassunto e sem
filho ativo, o nome não é título genérico e o par (chave de regra, nó) não foi vetado
pelo dono; entra como `regra`/`aprovado` e conta em `por_heranca`. Regra ambígua ou pai
sem nó fica pendente no `arvore.html`. **Pai provisório (KAN-86)**: assunto ou subassunto
cujo título de bloco não tem nó usa como pai a disciplina que o **cargo** do chunk nomeia
(`canonico.disciplina_do_cargo`: todas as palavras relevantes da disciplina de
`canonico/disciplinas.json` estão no nome do cargo, e exatamente 1 casa), só em chunk
`especifico` de cargo; chunk básico, cargo sem disciplina, 2 disciplinas ou cargos que
inferem disciplinas diferentes não inferem nada, e o bloco recua se já tem item aprovado em
outra disciplina. O título continua sem mapeamento. O que o pai provisório resolve (regra de
nome, decisão aprovada da memória, ou o único nó ativo de mesma `chave_regra` e nível
compatível na **subárvore** da disciplina) entra como `regra`/`aprovado` com as travas de
`canonico.no_do_pai_provisorio`: candidato único, par não vetado pelo dono, nome fora de
`TITULOS_GENERICOS`; o apelido de nó fundido não vale aqui, porque sem o pai real o nome solto
perde o contexto da fusão. `ResultadoRegra` traz `comparados`, `com_pai_provisorio` e
`por_pai_provisorio`. Depois do filho único e da herança (e do pai provisório), o último ramo
é o **casamento global por nome** (KAN-87, P77), que conta em `por_global`.
O log traz a contagem por regra de nome, por memória, por filho único, por herança de folha e pendentes. A `chave_regra` ignora os
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
            "tests/test_regra_arvore.py::test_filho_unico_resolve_os_casos_do_sefa",
            "tests/test_regra_arvore.py::test_filho_resolve_pela_disciplina_inferida_sem_gravar_o_titulo",
            "tests/test_regra_arvore.py::test_cargo_de_ti_infere_ti",
            "tests/test_regra_arvore.py::test_chunk_basico_ou_sem_cargo_nao_infere",
            "tests/test_regra_arvore.py::test_banrisul_ganha_mais_de_100_itens_comparados",
            "tests/test_regra_arvore.py::test_contratos_de_ti_casam_em_direito_administrativo",
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
ou o nome tem 2+ palavras relevantes e não é título genérico (`canonico.TITULOS_GENERICOS`, a lista
única de todos os ramos: inclui "Aplicações", "Definição", "Tipos", "Procedimento" e "Instalação,
configuração e administração", e vale também para rótulo feito só de `PALAVRAS_GENERICAS`, como
"Conceitos básicos e aplicações", KAN-87);
par vetado pelo dono (por `chave_regra`) nunca é regravado, e fora disso o item fica pendente,
nunca `aprovado` (KAN-82). Proposta de LLM ou de regra
nunca cria disciplina (`propor` recusa `criar` de matéria); disciplina nova só por decisão
do dono. O ramo do filho único (KAN-97, P52) é só de assunto e subassunto, que têm pai: o
título de bloco (matéria) continua neste ramo de nome e nunca passa por lá. A disciplina
inferida pelo **cargo** (P52, KAN-86) é só pai provisório dos filhos: nunca é gravada para o
título, que continua sem mapeamento, e jamais cria disciplina.
`scripts/auditar_arvore.py` fica verde antes de cada carga.""",
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
fica pendente; (3) filho único (KAN-97), só assunto e subassunto com pai mapeado: o item vai
para o único filho ativo de mesma `chave_regra` e nível compatível entre os filhos dos nós do
pai (`por_filho`, `regra`/`aprovado`), salvo ambiguidade, título genérico ou par vetado;
(3b) sem nó no título de bloco, o filho usa a disciplina inferida pelo cargo como pai
provisório (P52, KAN-86), com candidato único na subárvore, sem veto e fora dos títulos
genéricos, e sem apelido de nó fundido; (4) herança de folha, só para subtópico: aponta para o nó único do
tópico-pai se ele é subassunto ativo sem filhos, salvo título genérico ou par vetado
(KAN-85, `regra`/`aprovado`); (5) casamento global por nome (KAN-87, P77); nunca cria nó (P72). Só então o LLM (`mapear_itens_novos`, que antes
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
    Regra(
        id="P74",
        tipo="pattern",
        area="arvore",
        texto="""O relatório de revisão e a tabela `mapeamento_itens` do `revisao.db` leem a árvore já
passada pelo passo determinístico (`canonico.arvore_apos_passo`) e não têm critério de
equivalência próprio: só reportam como resolvido o que `mapear_novos_itens` mapeia (nome,
memória, filho único, herança de folha, pai provisório pelo cargo ou casamento global), e os pendentes do relatório são exatamente os do passo. `atualizar_revisao` roda `atualizar_arvore`
antes de `gerar_relatorios` e `gerar_db` (KAN-81). Seções, sugestão e agrupamento por cima disso são
só apresentação (P79).""",
        adrs=("ADR-030",),
        testes=(
            "tests/test_mapeamento_revisao.py::test_pendentes_do_relatorio_igual_aos_do_passo_nos_editais_reais",
        ),
    ),
    Regra(
        id="P75",
        tipo="pattern",
        area="edital",
        texto="""O subtópico reinjetado de um subitem de 3º nível em diante grava o **texto próprio** como
nome (`Topico.subtopicos`) e os ancestrais de 2º nível para baixo em `Topico.caminho_origem`
(`{"Design thinking": ["Metodologias ágeis..."]}`), nunca a cadeia "Pai - Filho" (KAN-93).
`caminho_origem` é só contexto: fica fora de `chave_item`, do banco e do casamento; o
relatório e o Datasette o mostram. É opcional e omitido do JSON quando vazio, então o
JSON antigo carrega sem mudança. Nome que já é irmão no tópico não colide em silêncio: a
reinjeção grava a cadeia (única) sem `caminho_origem`, e a migração deixa o nome em cadeia.
`migrar_cadeias_para_texto_proprio` só converte o que é, palavra por palavra, a cadeia de um
subitem numerado do texto-fonte (um " - " do próprio nome nunca casa) e roda dentro de
`scripts.reconciliar_taxonomia`. Depois de reconciliar, `scripts.migrar_chaves_cadeia`
(dry-run por padrão) leva os mapeamentos da chave antiga à nova por `src/arvore.py`; conflito
de nós nunca é decidido pelo script.""",
        adrs=("ADR-025", "ADR-030"),
        testes=(
            "tests/test_taxonomia_extractor.py::TestCadeiaVirandoTextoProprio",
            "tests/test_migrar_chaves_cadeia.py",
        ),
    ),
    Regra(
        id="P76",
        tipo="pattern",
        area="edital",
        texto="""A forma das listas é consertada por `normalizar_listas_e_facetas` (KAN-94, M8), sem LLM,
dentro do pós-LLM do extrator e de `scripts.reconciliar_taxonomia`: (1) tópico com ";" fora de
parênteses e **sem subtópicos** vira subtópicos, um por elemento, sem ponto final; se o 1º
elemento é "Cabeça: resto" a cabeça vira o nome do tópico; senão o **1º elemento vira o nome** e
os demais subtópicos (a chave muda, e o nome antigo vai em `Topico.nome_origem`), salvo quando todos
os elementos abrem com a mesma palavra ("Lei nº…; Lei nº…") ou o 1º passa de `TAMANHO_FRASE_LONGA`,
casos em que o nome fica inteiro e todos viram subtópicos; elemento que abre com "e"/"ou"/"com" ou
sem palavra de 3+ letras ("70 a 75"), elementos repetidos ou cabeça que colide com outro tópico do
chunk impedem a divisão (";" final e pedaço vazio são descartados antes de validar); vírgula e
"e" nunca dividem; (2) facetas voltam ao pai (`Topico.subtopicos_absorvidos`) só em dois casos:
todos os subtópicos são uma palavra minúscula que está no nome do pai ("Modelagem de dados:
físico, lógico e conceitual"), ou o pai tem sigla entre parênteses e pelo menos 3 subtópicos
são `FACETAS_GENERICAS` (BSC); **nunca** por contar palavras: "jQuery", "keycloak", "estados" e
"Backup" são assuntos, e subitem numerado da fonte também nunca é absorvido; (3) o ponto final sai
(a chave já ignora pontuação). O validador só avisa (informativo): `topico_lista_nao_dividida`,
`subtopico_faceta_solta` e `topico_frase_longa` (> `TAMANHO_FRASE_LONGA`). Depois de reconciliar,
`scripts.migrar_chaves_cadeia` leva a chave do tópico que mudou e remove só a herança
`regra` redundante da faceta; o que for humano ou de nó diferente fica e é relatado como órfão.""",
        adrs=("ADR-025", "ADR-030"),
        testes=(
            "tests/test_taxonomia_extractor.py::TestFormaDeListasEFacetas",
            "tests/test_validar_taxonomia.py::TestAlertasDeForma",
            "tests/test_migrar_chaves_cadeia.py",
            "tests/test_reconciliar_taxonomia.py",
        ),
    ),
    Regra(
        id="P77",
        tipo="pattern",
        area="arvore",
        texto="""**Casamento global por nome** (KAN-87, M6, `canonico.no_global_por_nome`): último ramo do passo
determinístico (P52, P73), depois do filho único, da herança de folha e do pai provisório, e
antes de marcar pendente. Só para assunto e subassunto com pai mapeado (ou disciplina inferida
pelo cargo). O item de nome idêntico (`chave_regra`) a um nó ativo de nível compatível em **qualquer**
parte da árvore vai para ele como `regra`/`aprovado` (`por_global`; `chaves_global_fora_disciplina`
guarda os que atravessaram disciplina). Segue D3: um conceito, um nó, então o subitem jurídico de
um bloco de TI vai para o nó que já existe em Direito Administrativo. Travas: (1) o candidato é
único (dois nós iguais, inclusive norma repetida, deixam o item pendente); (2) **exceção de TI**:
se há nó equivalente na disciplina do pai (ou inferida pelo cargo), ele vale e os de fora são
ignorados, e dois equivalentes ali são ambíguos; (3) para atravessar disciplina o nome precisa
de 3+ palavras relevantes (`PALAVRAS_MIN_ENTRE_DISCIPLINAS`) ou ser **norma** (lei, decreto,
"Lei nº X/ano", `nos_da_mesma_norma`, KAN-64: a norma vive em um nó só); nome curto só casa
dentro da disciplina; (4) título genérico nunca casa (`TITULOS_GENERICOS`, lista única de M2, M4,
M5, M14 e M6); (5) par vetado pelo dono não casa; (6) apelido de nó fundido entra como candidato,
exceto com pai provisório (P52); (7) nunca cria nó nem disciplina (D5, P72). Item composto ("A e B")
não é dividido aqui: se a `chave_regra` do nome inteiro não é a de um nó, o item fica para o LLM ou
o dono, que podem apontar até dois nós (a árvore é N:N). Lote novo roda K22 a K24 antes e depois (P71).""",
        adrs=("ADR-030",),
        testes=(
            "tests/test_regra_arvore.py::test_contratos_de_ti_casam_em_direito_administrativo",
            "tests/test_regra_arvore.py::test_lgpd_casa_global_por_norma",
            "tests/test_regra_arvore.py::test_nome_curto_nao_atravessa_disciplina",
            "tests/test_regra_arvore.py::test_generico_nunca_casa_global",
            "tests/test_regra_arvore.py::test_candidato_duplicado_nao_casa",
            "tests/test_regra_arvore.py::test_excecao_ti_prefere_o_equivalente_da_disciplina_do_pai",
            "tests/test_regra_arvore.py::test_veto_do_dono_barra_o_global",
            "tests/test_regra_arvore.py::test_economia_nao_casa_com_atualidades",
        ),
    ),
    Regra(
        id="P79",
        tipo="pattern",
        area="arvore",
        texto="""A revisão do mapeamento é guiada por seções e sugestão, e **só apresenta** (KAN-89, M10):
`mapeamento_revisao.montar_revisao` agrupa os pendentes do passo (P74) em decisão de bloco (título sem
nó, com quantos itens destrava), com sugestão (score ≥ `LIMIAR_SUGESTAO`), realmente novo, travado pelo
pai (pai sem nó e sem disciplina inferida pelo cargo, M4) e herda do tópico (subitem sob nó-folha).
A sugestão é o top-3 por similaridade de palavras (IDF, sem LLM), restrito à subárvore do pai ou da
disciplina provisória; nó de outra disciplina só entra com o mesmo `chave_regra` ou sendo a mesma norma
(`nos_da_mesma_norma`); título genérico não recebe sugestão. Mesmo item em blocos ou cargos
diferentes vira um grupo (uma linha, lista de cargos). Cada sugestão traz a linha
`curar_arvore --mapear` para o dono copiar: o relatório e o `revisao.db` nunca aprovam nem
gravam (A27, A30), e a sugestão não decide equivalência, que continua só do passo. O Datasette
ganha as colunas `bloco`, `secao`, `sugestao_*`, `score`, `cargos`, `grupo`, `representante`,
`curar_arvore`, as visões `revisao_*` e `revisao_piloto/datasette/metadata.json` (consultas salvas,
fora do glob `*.json` dos editais).""",
        adrs=("ADR-030",),
        testes=(
            "tests/test_revisao_guiada.py::test_apresentacao_nao_muda_categoria_nem_pendentes_nem_arvore",
            "tests/test_revisao_guiada.py::test_nome_parecido_de_outra_disciplina_nao_atravessa",
            "tests/test_revisao_guiada.py::test_mesmo_item_em_dois_blocos_vira_um_grupo_com_os_dois_cargos",
            "tests/test_revisao_guiada.py::test_gerar_db_acrescenta_colunas_visoes_e_metadata",
        ),
    ),
)
