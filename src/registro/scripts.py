"""Scripts do registro: cada ponto de entrada `python -m` do projeto (Etapa 9/D2).

Fonte única para as páginas de `docs/tecnico/` e para o teste guarda: um script
novo sem entrada aqui quebra `tests/test_registro.py`.
"""

from src.registro.modelo import Script

SCRIPTS: tuple[Script, ...] = (
    Script(
        "scripts.aprovar_sinonimos",
        "Aplica as decisões humanas sobre os sinônimos canônicos.",
        "curadoria",
        "argparse",
        adrs=("ADR-019", "ADR-029"),
    ),
    Script(
        "scripts.atualizar_revisao",
        "Atualiza em sequência os artefatos derivados da revisão humana e reinicia o "
        "Datasette.",
        "relatorio",
        "argv",
        uso_argv="python -m scripts.atualizar_revisao [diretorio_revisao]",
        adrs=("ADR-015", "ADR-027", "ADR-029", "ADR-031"),
    ),
    Script(
        "scripts.auditar_arvore",
        "Confere as disciplinas da árvore contra a lista fechada e aponta norma "
        "repetida.",
        "curadoria",
        "argparse",
        adrs=("ADR-030",),
    ),
    Script(
        "scripts.backfill_classificacao_chunks",
        "Completa concurso, nível e tipo de conhecimento em extrações já feitas, sem "
        "LLM.",
        "manutencao",
        "argv",
        uso_argv=(
            "python -m scripts.backfill_classificacao_chunks [edital.pdf [saida.json]]"
        ),
        adrs=("ADR-020", "ADR-025", "ADR-028"),
    ),
    Script(
        "scripts.classificar_questoes",
        "Classifica as questões na árvore mestre pelo LLM, em duas passadas.",
        "pipeline",
        "argparse",
        adrs=("ADR-030",),
    ),
    Script(
        "scripts.curar_arvore",
        "CLI de curadoria da árvore mestre: toda decisão do dono passa por aqui.",
        "curadoria",
        "argparse",
        adrs=("ADR-030",),
    ),
    Script(
        "scripts.curar_classificacao",
        "CLI de curadoria e deliberação humana da classificação das questões.",
        "curadoria",
        "argparse",
        adrs=("ADR-030",),
    ),
    Script(
        "scripts.detectar_dispersao_arvore",
        "Detecta conceitos espalhados em pais diferentes da árvore mestre, por regra.",
        "pipeline",
        "argparse",
        adrs=("ADR-030",),
    ),
    Script(
        "scripts.executar_c2",
        "Executa o lote de concursos no Dagster (C2).",
        "pipeline",
        "argparse",
        adrs=("ADR-041",),
    ),
    Script(
        "scripts.experimento_falhas_llm",
        "Experimento controlado sobre os chunks que falharam na extração real. Custa "
        "tokens.",
        "experimento",
        "argv",
        uso_argv="python -m scripts.experimento_falhas_llm [caminho_auditoria.json]",
    ),
    Script(
        "scripts.exportar_pdf_executivo",
        "Exporta a visão executiva do site de documentação para PDF, para quem está "
        "fora do Cloudflare Access.",
        "relatorio",
        "argparse",
        adrs=("ADR-040",),
    ),
    Script(
        "scripts.extrair_questoes",
        "Consumidor da fila de extração: extrai questões, gabaritos e discursivas, sem "
        "LLM.",
        "pipeline",
        "argparse",
        adrs=("ADR-031",),
    ),
    Script(
        "scripts.gerar_db_datasette",
        "Constrói o banco SQLite servido via Datasette para revisão humana.",
        "relatorio",
        "argv",
        uso_argv="python -m scripts.gerar_db_datasette [diretorio_revisao]",
        adrs=("ADR-020", "ADR-026"),
    ),
    Script(
        "scripts.gerar_docs",
        "Gera as páginas de docs/tecnico/ a partir do registro (Etapa 9/D2).",
        "relatorio",
        "argparse",
    ),
    Script(
        "scripts.gerar_numeros",
        "Gera a página de números da visão executiva a partir do banco e do custo de "
        "LLM no OpenRouter.",
        "relatorio",
        "argparse",
        adrs=("ADR-040", "ADR-041"),
    ),
    Script(
        "scripts.gerar_relatorio_arvore",
        "Gera o relatório HTML da árvore mestre para revisão do dono.",
        "relatorio",
        "argv",
        uso_argv="python -m scripts.gerar_relatorio_arvore [diretorio_revisao]",
        adrs=("ADR-030",),
    ),
    Script(
        "scripts.gerar_relatorio_classificacao",
        "Gera o relatório visual da classificação das questões na árvore mestre.",
        "relatorio",
        "argv",
        uso_argv="python -m scripts.gerar_relatorio_classificacao [diretorio_revisao]",
        adrs=("ADR-030",),
    ),
    Script(
        "scripts.gerar_relatorio_revisao",
        "Gera o relatório HTML por edital para o checkpoint de revisão humana.",
        "relatorio",
        "argv",
        uso_argv="python -m scripts.gerar_relatorio_revisao [diretorio_revisao]",
        adrs=("ADR-020", "ADR-021"),
    ),
    Script(
        "scripts.gerar_relatorio_sinonimos",
        "Relatório de revisão dos sinônimos canônicos, substituído pelo da árvore.",
        "obsoleto",
        "argv",
        uso_argv="python -m scripts.gerar_relatorio_sinonimos [diretorio_revisao]",
        adrs=("ADR-029",),
    ),
    Script(
        "scripts.inventariar_concursos",
        "Inventário de concursos e cadernos do CEBRASPE (2020 até hoje).",
        "pipeline",
        "argparse",
    ),
    Script(
        "scripts.mapear_itens_novos",
        "Mapeia item novo de edital: primeiro pela memória das decisões do dono (sem "
        "LLM, P73), depois pelo LLM sobre lista fechada (disciplina do item mais "
        "candidatos globais, até 3 nós por item composto, P80), com contexto de "
        "subitens. O LLM grava só proposto. Custa tokens.",
        "curadoria",
        "argparse",
        adrs=("ADR-030", "ADR-032"),
    ),
    Script(
        "scripts.migrar_chaves_cadeia",
        "Leva os mapeamentos da chave do subtópico em cadeia para a do texto próprio e "
        "da lista com ';' (M8); relata facetas órfãs (dry-run por padrão).",
        "manutencao",
        "argparse",
        adrs=("ADR-030",),
    ),
    Script(
        "scripts.propor_arvore",
        "Propõe operações na árvore mestre pelo LLM, por matéria, sobre lista fechada.",
        "curadoria",
        "argparse",
        adrs=("ADR-030",),
    ),
    Script(
        "scripts.propor_sinonimos",
        "Propõe sinônimos pelo LLM, sobre lista fechada de IDs. Custa tokens.",
        "curadoria",
        "argparse",
        adrs=("ADR-021", "ADR-029"),
    ),
    Script(
        "scripts.reconciliar_taxonomia",
        "Aplica o reparo local de item ausente, a volta da cadeia ao texto próprio e a forma "
        "de listas, facetas e pontuação (M8) a extrações já salvas, sem LLM.",
        "manutencao",
        "argv",
        uso_argv=(
            "python -m scripts.reconciliar_taxonomia "
            "[--sem-atualizar] [<edital>.json ...]"
        ),
        adrs=("ADR-019", "ADR-025"),
    ),
    Script(
        "scripts.reprocessar_falhas_piloto",
        "Reprocessa chunks com falha e consolida o edital piloto.",
        "manutencao",
        "argparse",
        adrs=("ADR-019", "ADR-021"),
    ),
    Script(
        "scripts.revisar_taxonomia_piloto",
        "Checkpoint de revisão humana: roda o pipeline do edital e salva o JSON para "
        "revisão.",
        "pipeline",
        "argv",
        uso_argv="python -m scripts.revisar_taxonomia_piloto <edital.pdf> [saida.json] [--so-chunking]",
        adrs=("ADR-019", "ADR-020", "ADR-021"),
    ),
    Script(
        "scripts.semear_arvore",
        "Semeia canonico/arvore.json com os grupos aprovados da camada de sinônimos.",
        "manutencao",
        "argv",
        uso_argv="python -m scripts.semear_arvore [--forcar]",
        adrs=("ADR-030",),
    ),
    Script(
        "scripts.validar_taxonomia",
        "Valida se a taxonomia extraída capturou todos os tópicos do edital.",
        "pipeline",
        "argv",
        uso_argv="python -m scripts.validar_taxonomia [diretorio_revisao]",
        adrs=("ADR-020", "ADR-021", "ADR-025"),
    ),
    Script(
        "src.spider",
        "Crawler de concursos do CEBRASPE, com download dos PDFs.",
        "pipeline",
        "argparse",
        adrs=("ADR-037",),
    ),
    Script(
        "src.stats_writer",
        "Grava o star schema de estatísticas no Postgres próprio.",
        "pipeline",
        "argv",
        uso_argv="python -m src.stats_writer [revisao_piloto_dir] [data_dir]",
        adrs=(
            "ADR-020",
            "ADR-026",
            "ADR-027",
            "ADR-028",
            "ADR-029",
            "ADR-030",
            "ADR-031",
        ),
    ),
    Script(
        "src.telegram_bot",
        "Bot do Telegram de suporte técnico ao projeto, com contexto fixo.",
        "manutencao",
        "nenhum",
        adrs=("ADR-026",),
    ),
)
