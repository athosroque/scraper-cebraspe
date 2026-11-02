"""`scripts.reconciliar_taxonomia` aplica a forma da M8 sem tocar no resto (KAN-94)."""

import json

from scripts import reconciliar_taxonomia as rec


def _escrever(tmp_path, topicos):
    resultado = {
        "edital": "x.pdf",
        "status_revisao_humana": "APROVADO — teste",
        "resultados": [
            {
                "chunk_index": 0,
                "materia_chunk": "Redes",
                "taxonomia_extraida": {"materia": "Redes", "topicos": topicos},
            }
        ],
    }
    json_path = tmp_path / "x.json"
    json_path.write_text(json.dumps(resultado), encoding="utf-8")
    (tmp_path / "x.auditoria.json").write_text(
        json.dumps(
            {
                "chunks": [
                    {
                        "chunk_index": 0,
                        "texto_enviado_llm": "Cloud computing; virtualização.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return json_path


def test_divide_a_lista_preserva_a_revisao_e_cria_backup(tmp_path):
    json_path = _escrever(tmp_path, [{"nome": "Cloud computing; virtualização."}])
    alterados = rec.reconciliar(json_path)
    assert alterados[0][0].startswith("lista:")
    gravado = json.loads(json_path.read_text(encoding="utf-8"))
    topico = gravado["resultados"][0]["taxonomia_extraida"]["topicos"][0]
    assert topico == {
        "nome": "Cloud computing",
        "subtopicos": ["virtualização"],
        "nome_origem": "Cloud computing; virtualização.",
    }
    assert gravado["status_revisao_humana"] == "APROVADO — teste"
    assert (tmp_path / "x.json.pre_reconciliacao.bak").exists()


def test_segunda_rodada_nao_muda_nada(tmp_path):
    json_path = _escrever(tmp_path, [{"nome": "Cloud computing; virtualização."}])
    rec.reconciliar(json_path)
    depois = json_path.read_bytes()
    assert rec.reconciliar(json_path) == {}
    assert json_path.read_bytes() == depois
