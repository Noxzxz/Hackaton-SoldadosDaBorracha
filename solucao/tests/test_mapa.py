"""Testes da avaliacao do mapa (vigencia/permissao/condicao/excecao) e configs."""
from __future__ import annotations

from src.classificar import _condicoes_cfg, _excecoes_cfg, avaliar_mapa


def test_cesta_basica_tem_candidato_200003():
    aval = avaliar_mapa("07133319")  # feijao
    assert aval.tipo_match == "exato"
    assert "200003" in aval.classes


def test_condicao_agropecuaria_elimina_classes():
    aval = avaliar_mapa("07133319")
    motivos = " ".join(m for _, m in aval.eliminados).upper()
    assert "INSUMOS AGROPECU" in motivos


def test_vedado_nao_entra_nas_classes():
    # Nenhuma classe VEDADA pode aparecer entre os candidatos avaliados
    from src.io_dados import mapa

    m = mapa()
    aval = avaliar_mapa("10063021")  # arroz
    vedados = set(
        m[(m["NCM"] == "10063021") & (m["permissao"] == "VEDADO")]["cClassTrib"]
    )
    assert not (set(aval.classes) & vedados)


def test_ncm_fora_do_mapa():
    a = avaliar_mapa("99999999")
    assert a.tipo_match == "sem_match"
    assert a.classes == []


def test_configs_carregadas():
    assert "condicoes" in _condicoes_cfg() or _condicoes_cfg()
    assert _excecoes_cfg()
    # a condicao de insumo agropecuario e reconhecidamente falsa para o atacadista
    cond = _condicoes_cfg()
    falsas = [k for k, v in cond.items() if isinstance(v, dict) and v.get("satisfaz") is False]
    assert any("INSUMOS" in k.upper() for k in falsas)
