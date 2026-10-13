VENV := ./venv/bin
PYTHON := $(VENV)/python
PYTEST := $(VENV)/pytest
RUFF := $(VENV)/ruff
MKDOCS := $(VENV)/mkdocs

.PHONY: help lint format-check format test-fast test-unit test-pipeline test-site test-site-fast test-all docs-serve docs-gerar docs-build hooks-instalar check

help:
	@echo "================================================================="
	@echo "   Scraper CEBRASPE — Comandos de Qualidade e Testes por Etapas"
	@echo "================================================================="
	@echo "Lint & Formatação:"
	@echo "  make lint           Executa ruff check em todo o código válido"
	@echo "  make format-check   Verifica consistência de formatação (ruff format)"
	@echo "  make format         Aplica formatação automática com ruff"
	@echo ""
	@echo "Testes por Etapa:"
	@echo "  make test-fast      [Etapa 1: ~18s] Lint + testes unitários sem banco"
	@echo "  make test-unit      Testes unitários sem banco (modo verboso)"
	@echo "  make test-pipeline  [Etapa 2A: ~1m15s] Testes do scraper, parsers e pipeline"
	@echo "  make test-site      [Etapa 2B: ~3m20s] Testes da aplicação web e API"
	@echo "  make test-site-fast Testes do site pulando os mais lentos (>3s)"
	@echo "  make test-all       [Etapa 3: ~4m45s] Suíte completa de 840 testes"
	@echo ""
	@echo "Documentação:"
	@echo "  make docs-serve     Site MkDocs local em http://127.0.0.1:8001 (recarga ao salvar)"
	@echo "  make docs-gerar     Regera docs/tecnico/ (registro) e docs/executivo/numeros.md (banco e OpenRouter)"
	@echo "  make docs-build     Gera o site em build/docs com mkdocs build --strict, mais o PDF executivo"
	@echo "  make hooks-instalar Instala os hooks git que publicam o site de docs após commit/merge"
	@echo ""
	@echo "  make check          Regressão completa de CI (lint + format + docs-build + test-all)"
	@echo "================================================================="

lint:
	$(RUFF) check .

format-check:
	$(RUFF) format --check .

format:
	$(RUFF) format .

test-fast: lint
	$(PYTEST) -m "unit and not db" -q

test-unit:
	$(PYTEST) -m "unit and not db" -v

test-pipeline:
	$(PYTEST) tests/ -q

test-site:
	$(PYTEST) site/tests/ -q

test-site-fast:
	$(PYTEST) site/tests/ -m "not slow" -q

test-all:
	$(PYTEST)

docs-serve:
	$(MKDOCS) serve -a 127.0.0.1:8001

docs-gerar:
	$(PYTHON) -m scripts.gerar_docs
	$(PYTHON) -m scripts.gerar_numeros

# Gera numa pasta temporária e só copia para build/docs se o --strict passar: o
# mkdocs limpa o destino antes de validar, e o nginx serve build/docs. Assim um
# build quebrado não tira o site do ar. rsync (e não mv) porque o bind mount do
# nginx aponta para o diretório build/docs, que precisa continuar o mesmo.
# O PDF da visão executiva (D4) sai do mesmo build, antes do rsync, para nunca
# ficar atrás do site; precisa do Chromium do Playwright e do Mermaid do CDN.
docs-build:
	rm -rf build/docs.novo
	$(MKDOCS) build --strict --site-dir build/docs.novo
	$(PYTHON) -m scripts.exportar_pdf_executivo --site build/docs.novo
	mkdir -p build/docs
	rsync -a --delete build/docs.novo/ build/docs/
	rm -rf build/docs.novo

hooks-instalar:
	bash scripts/hooks/instalar.sh

check: lint format-check docs-build test-all
