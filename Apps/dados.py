import os
import shutil
import csv
import openpyxl
import re
import unicodedata
from decimal import Decimal, InvalidOperation

import pandas as pd

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
XLSX_PATH = os.path.join(BASE_DIR, "Caixinha 2026.xlsx")
XLSX_TMP = os.path.join(BASE_DIR, "Caixinha_2026_temp.xlsx")
RELATORIO_XLSX = os.path.join(BASE_DIR, "Relatorio.xlsx")
RELATORIO_TMP = os.path.join(BASE_DIR, "Relatorio_temp.xlsx")
CSV_DIR = os.path.join(BASE_DIR, "csv")
INFORMACOES_CSV = os.path.join(CSV_DIR, "informacoes.csv")
EVOLUCAO_CSV = os.path.join(CSV_DIR, "evolucao_caixinha.csv")
RELATORIO_CSV = os.path.join(CSV_DIR, "relatorio.csv")
EXTRATO_CSV = os.path.join(CSV_DIR, "extrato.csv")
EMPRESTIMOS_ATIVOS_CSV = os.path.join(CSV_DIR, "emprestimos_ativos.csv")
SHEET_NAME = "participantes"
SHEET_BASE = "Base"
SHEET_EXTRATO = "Extrato"


def _normalizar_texto(valor):
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return texto


def _normalizar_cpf(cpf):
    if cpf is None:
        return None
    numeros = re.sub(r"\D", "", str(cpf))
    if not numeros:
        return None
    if len(numeros) < 11:
        numeros = numeros.zfill(11)
    return numeros


def _encontrar_coluna(colunas, possiveis):
    normalizadas = {c: _normalizar_texto(c) for c in colunas}
    for alvo in possiveis:
        for original, normalizada in normalizadas.items():
            if alvo in normalizada:
                return original
    return None


def _resolver_nome_aba(xl):
    alvo = _normalizar_texto(SHEET_NAME)
    for nome in xl.sheet_names:
        if _normalizar_texto(nome) == alvo:
            return nome
    for nome in xl.sheet_names:
        if "particip" in _normalizar_texto(nome):
            return nome
    return xl.sheet_names[0] if xl.sheet_names else None


def _resolver_nome_aba_base(xl):
    alvo = _normalizar_texto(SHEET_BASE)
    for nome in xl.sheet_names:
        if _normalizar_texto(nome) == alvo:
            return nome
    for nome in xl.sheet_names:
        if "base" == _normalizar_texto(nome):
            return nome
    return xl.sheet_names[0] if xl.sheet_names else None


def _resolver_nome_aba_extrato(xl):
    alvo = _normalizar_texto(SHEET_EXTRATO)
    for nome in xl.sheet_names:
        if _normalizar_texto(nome) == alvo:
            return nome
    for nome in xl.sheet_names:
        if "extrat" in _normalizar_texto(nome):
            return nome
    return None


def _resolver_nome_aba_por_termos(xl, termos):
    if not xl or not getattr(xl, "sheet_names", None):
        return None
    termos_norm = [_normalizar_texto(t) for t in termos if t]
    for termo in termos_norm:
        for nome in xl.sheet_names:
            if _normalizar_texto(nome) == termo:
                return nome
    for termo in termos_norm:
        for nome in xl.sheet_names:
            if _normalizar_texto(nome).startswith(termo):
                return nome
    for nome in xl.sheet_names:
        nome_norm = _normalizar_texto(nome)
        if any(termo in nome_norm for termo in termos_norm):
            return nome
    return None


def _carregar_caixinha_excel():
    origem = XLSX_TMP if os.path.exists(XLSX_TMP) else XLSX_PATH
    if not os.path.exists(origem):
        return None
    try:
        return pd.ExcelFile(origem, engine="openpyxl")
    except Exception:
        return None


def _normalizar_id(valor):
    texto = str(valor or "").strip()
    if not texto:
        return None
    numeros = re.sub(r"\D", "", texto)
    return numeros if numeros else texto.lower()


def carregar_participantes_df():
    if not os.path.exists(XLSX_PATH):
        return None
    try:
        shutil.copy2(XLSX_PATH, XLSX_TMP)
        xl = pd.ExcelFile(XLSX_TMP, engine="openpyxl")
        aba = _resolver_nome_aba(xl)
        if not aba:
            return None
        return pd.read_excel(xl, sheet_name=aba, dtype=str)
    except Exception:
        return None
    finally:
        try:
            if os.path.exists(XLSX_TMP):
                os.remove(XLSX_TMP)
        except Exception:
            pass


def _carregar_extrato_df():
    if not os.path.exists(XLSX_PATH):
        return None

    xl = None
    try:
        shutil.copy2(XLSX_PATH, XLSX_TMP)
        xl = pd.ExcelFile(XLSX_TMP, engine="openpyxl")
        aba = _resolver_nome_aba_extrato(xl)
        if not aba:
            return None
        df = pd.read_excel(xl, sheet_name=aba, dtype=str)
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None
    finally:
        try:
            if xl is not None and hasattr(xl, "close"):
                xl.close()
        except Exception:
            pass
        try:
            if os.path.exists(XLSX_TMP):
                os.remove(XLSX_TMP)
        except Exception:
            pass


def carregar_base_df():
    if not os.path.exists(RELATORIO_XLSX):
        return None
    try:
        shutil.copy2(RELATORIO_XLSX, RELATORIO_TMP)
        xl = pd.ExcelFile(RELATORIO_TMP, engine="openpyxl")
        aba = _resolver_nome_aba_base(xl)
        if not aba:
            return None
        df = pd.read_excel(xl, sheet_name=aba, dtype=str)
        if df is not None and not df.empty:
            return df
        return None
    except Exception:
        return None
    finally:
        try:
            if os.path.exists(RELATORIO_TMP):
                os.remove(RELATORIO_TMP)
        except Exception:
            pass


def gerar_relatorio_csv():
    if not os.path.exists(RELATORIO_XLSX):
        return None
    os.makedirs(CSV_DIR, exist_ok=True)
    try:
        shutil.copy2(RELATORIO_XLSX, RELATORIO_TMP)
        xl = pd.ExcelFile(RELATORIO_TMP, engine="openpyxl")
        aba = _resolver_nome_aba_base(xl)
        if not aba:
            return None
        df_raw = pd.read_excel(xl, sheet_name=aba, header=None, dtype=str)
        if df_raw is None or df_raw.empty:
            return None

        start_idx = 3  # linha 4 (0-based)
        df_slice = df_raw.iloc[start_idx:].copy()
        df_slice = df_slice.dropna(axis=1, how="all")

        with open(RELATORIO_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for _, row in df_slice.iterrows():
                writer.writerow([None if pd.isna(v) else v for v in row.tolist()])

        return RELATORIO_CSV
    except Exception:
        return None
    finally:
        try:
            if os.path.exists(RELATORIO_TMP):
                os.remove(RELATORIO_TMP)
        except Exception:
            pass


def _carregar_base_com_header_dinamico():
    if not os.path.exists(RELATORIO_XLSX):
        return None
    try:
        shutil.copy2(RELATORIO_XLSX, RELATORIO_TMP)
        xl = pd.ExcelFile(RELATORIO_TMP, engine="openpyxl")
        aba = _resolver_nome_aba_base(xl)
        if not aba:
            return None
        bruto = pd.read_excel(xl, sheet_name=aba, header=None, dtype=str)
        if bruto is None or bruto.empty:
            return None
        header_idx = None
        for i in range(len(bruto)):
            row_vals = bruto.iloc[i].astype(str).tolist()
            row_norm = [_normalizar_texto(v) for v in row_vals]
            if any("caixinha 2026" in v for v in row_norm):
                header_idx = i
                break
        if header_idx is None:
            return None
        headers = bruto.iloc[header_idx].tolist()
        df = bruto.iloc[header_idx + 1:].copy()
        df.columns = headers
        return df
    except Exception:
        return None
    finally:
        try:
            if os.path.exists(RELATORIO_TMP):
                os.remove(RELATORIO_TMP)
        except Exception:
            pass


def atualizar_informacoes_csv():
    df = carregar_participantes_df()
    if df is None:
        return None
    os.makedirs(CSV_DIR, exist_ok=True)
    df.to_csv(INFORMACOES_CSV, index=False, encoding="utf-8")
    return df


EVOLUCAO_START_ROW = 190
EVOLUCAO_VAL_COL = 4
EVOLUCAO_DATE_COL = 20
EVOLUCAO_START_DATE = "2026-02-02"


def _gerar_evolucao_por_posicao(df_raw):
    if df_raw is None or df_raw.empty:
        return None
    start_idx = max(EVOLUCAO_START_ROW - 1, 0)
    df_slice = df_raw.iloc[start_idx:].copy()
    df_out = pd.DataFrame()
    df_out["idx"] = df_slice.index.astype(int) + 1
    df_out["data"] = ""
    try:
        df_out["data"] = df_slice.iloc[:, EVOLUCAO_DATE_COL].astype(str)
    except Exception:
        df_out["data"] = ""
    try:
        df_out["valor"] = df_slice.iloc[:, EVOLUCAO_VAL_COL].astype(str)
    except Exception:
        return None
    try:
        data_parse = pd.to_datetime(df_out["data"], errors="coerce", dayfirst=True)
        data_limite = pd.to_datetime(EVOLUCAO_START_DATE)
        df_out = df_out[data_parse >= data_limite]
    except Exception:
        pass
    df_out = df_out[df_out["valor"].astype(str).str.lower().ne("nan")]
    return df_out


def atualizar_evolucao_csv():
    # Lê a planilha Base como matriz crua e extrai por posição (E e U)
    df_raw = None
    try:
        if os.path.exists(RELATORIO_XLSX):
            shutil.copy2(RELATORIO_XLSX, RELATORIO_TMP)
            xl = pd.ExcelFile(RELATORIO_TMP, engine="openpyxl")
            aba = _resolver_nome_aba_base(xl)
            if aba:
                df_raw = pd.read_excel(xl, sheet_name=aba, header=None, dtype=str)
    except Exception:
        df_raw = None
    finally:
        try:
            if os.path.exists(RELATORIO_TMP):
                os.remove(RELATORIO_TMP)
        except Exception:
            pass

    df_out = _gerar_evolucao_por_posicao(df_raw)
    if df_out is None or df_out.empty:
        return None

    os.makedirs(CSV_DIR, exist_ok=True)
    try:
        if os.path.exists(EVOLUCAO_CSV):
            os.remove(EVOLUCAO_CSV)
    except Exception:
        pass
    df_out.to_csv(EVOLUCAO_CSV, index=False, encoding="utf-8")

    return df_out


def _formatar_real(valor):
    try:
        quantia = Decimal(valor)
    except (InvalidOperation, TypeError):
        return None
    texto = f"{quantia:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def _parse_saldo(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float, Decimal)):
        return _formatar_real(valor)
    texto = str(valor).strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").strip()
    texto = texto.replace(".", "").replace(",", ".")
    return _formatar_real(texto)

def _parse_decimal(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    texto = str(valor).strip()
    if not texto:
        return None
    texto = texto.replace("R$", "").strip()
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "")
            texto = texto.replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(".", "")
        texto = texto.replace(",", ".")
    else:
        texto = texto.replace(",", "")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _buscar_emprestimos_ativos():
    xl = _carregar_caixinha_excel()
    if xl is None:
        return []

    try:
        aba_parcelas = _resolver_nome_aba_por_termos(xl, ["parcelas", "parcela"])
        aba_emprestimos = _resolver_nome_aba_por_termos(xl, ["emprestimos", "emprestimo"])
        aba_participantes = _resolver_nome_aba_por_termos(xl, ["particip"])
        if not aba_parcelas or not aba_emprestimos or not aba_participantes:
            return []

        parcelas = pd.read_excel(xl, sheet_name=aba_parcelas, dtype=str)
        emprestimos = pd.read_excel(xl, sheet_name=aba_emprestimos, dtype=str)
        participantes = pd.read_excel(xl, sheet_name=aba_participantes, dtype=str)
        if parcelas is None or parcelas.empty:
            return []
        if emprestimos is None or emprestimos.empty:
            return []
        if participantes is None or participantes.empty:
            return []

        col_status_parc = _encontrar_coluna(parcelas.columns, ["status"])
        col_id_emprest_parc = _encontrar_coluna(parcelas.columns, ["id_emprest", "id emprest"])
        col_parcela = _encontrar_coluna(parcelas.columns, ["parcela"])
        col_vencimento = _encontrar_coluna(parcelas.columns, ["venc"])
        col_saldo_parcela = _encontrar_coluna(parcelas.columns, ["saldo"])
        col_valor_parcela = _encontrar_coluna(parcelas.columns, ["valor"])

        col_id_emprest = _encontrar_coluna(emprestimos.columns, ["id"])
        col_id_part = _encontrar_coluna(emprestimos.columns, ["id_participante", "id participante"])
        col_valor_final = _encontrar_coluna(emprestimos.columns, ["valor final", "valor_total", "valor total"])
        col_valor = _encontrar_coluna(emprestimos.columns, ["valor"])

        col_part_id = _encontrar_coluna(participantes.columns, ["id"])
        col_part_cpf = _encontrar_coluna(participantes.columns, ["cpf"])

        if (
            not col_status_parc
            or not col_id_emprest_parc
            or not col_id_emprest
            or not col_id_part
            or not col_part_id
            or not col_part_cpf
        ):
            return []

        parcelas["_status_norm"] = parcelas[col_status_parc].fillna("").astype(str).str.strip().str.lower()
        parcelas_abertas = parcelas[parcelas["_status_norm"] == "em aberto"].copy()
        if parcelas_abertas.empty:
            return []

        parcelas_abertas["_id_emprest_norm"] = parcelas_abertas[col_id_emprest_parc].apply(_normalizar_id)
        emprestimos["_id_emprest_norm"] = emprestimos[col_id_emprest].apply(_normalizar_id)
        emprestimos["_id_part_norm"] = emprestimos[col_id_part].apply(_normalizar_id)
        participantes["_id_part_norm"] = participantes[col_part_id].apply(_normalizar_id)
        participantes["_cpf_norm"] = participantes[col_part_cpf].apply(_normalizar_cpf)

        mapa_participante_cpf = participantes.set_index("_id_part_norm")["_cpf_norm"].to_dict()
        mapa_emprestimos = emprestimos.set_index("_id_emprest_norm").to_dict(orient="index")

        ativos = []
        for id_emprest_norm, grupo in parcelas_abertas.groupby("_id_emprest_norm"):
            if not id_emprest_norm:
                continue
            emprestimo = mapa_emprestimos.get(id_emprest_norm)
            if not emprestimo:
                continue

            id_participante = emprestimo.get("_id_part_norm")
            cpf = mapa_participante_cpf.get(id_participante)
            if not cpf:
                continue

            saldo_devedor = Decimal("0")
            detalhes = []
            for _, linha in grupo.iterrows():
                valor_parcela = _parse_decimal(linha.get(col_saldo_parcela)) if col_saldo_parcela else None
                if valor_parcela is None and col_valor_parcela:
                    valor_parcela = _parse_decimal(linha.get(col_valor_parcela))
                if valor_parcela is None:
                    valor_parcela = Decimal("0")
                saldo_devedor += valor_parcela

                vencimento_fmt = ""
                dt = pd.to_datetime(linha.get(col_vencimento), errors="coerce") if col_vencimento else None
                if dt is not None and not pd.isna(dt):
                    vencimento_fmt = dt.strftime("%d/%m/%Y")
                elif col_vencimento:
                    vencimento_fmt = str(linha.get(col_vencimento) or "").strip()

                detalhes.append(
                    {
                        "parcela": str(linha.get(col_parcela) or "").strip(),
                        "vencimento": vencimento_fmt,
                        "valor": _formatar_real(valor_parcela) or "R$ 0,00",
                    }
                )

            valor_total = _parse_decimal(emprestimo.get(col_valor_final)) if col_valor_final else None
            if valor_total is None and col_valor:
                valor_total = _parse_decimal(emprestimo.get(col_valor))
            if valor_total is None:
                valor_total = saldo_devedor

            id_emprestimo_original = str(emprestimo.get(col_id_emprest) or id_emprest_norm).strip()
            ativos.append(
                {
                    "cpf": cpf,
                    "id_participante": str(id_participante or "").strip(),
                    "id_emprestimo": id_emprestimo_original,
                    "valor_total_num": valor_total,
                    "valor_total": _formatar_real(valor_total) or "R$ 0,00",
                    "saldo_devedor_num": saldo_devedor,
                    "saldo_devedor": _formatar_real(saldo_devedor) or "R$ 0,00",
                    "parcelas_abertas": len(detalhes),
                    "parcelas_detalhes": sorted(
                        detalhes,
                        key=lambda item: (
                            pd.to_datetime(item.get("vencimento"), errors="coerce", dayfirst=True)
                            if item.get("vencimento")
                            else pd.Timestamp.max
                        ),
                    ),
                }
            )

        ativos = sorted(ativos, key=lambda item: _normalizar_id(item.get("id_emprestimo")))
        return ativos
    except Exception:
        return []
    finally:
        try:
            if hasattr(xl, "close"):
                xl.close()
        except Exception:
            pass


def atualizar_emprestimos_ativos_csv(ativos=None):
    if ativos is None:
        ativos = _buscar_emprestimos_ativos()
    os.makedirs(CSV_DIR, exist_ok=True)
    linhas = []
    for item in ativos:
        for detalhe in item.get("parcelas_detalhes", []):
            linhas.append(
                {
                    "cpf": item.get("cpf", ""),
                    "id_participante": item.get("id_participante", ""),
                    "id_emprestimo": item.get("id_emprestimo", ""),
                    "valor_total_emprestimo": item.get("valor_total", ""),
                    "saldo_devedor": item.get("saldo_devedor", ""),
                    "parcela": detalhe.get("parcela", ""),
                    "vencimento": detalhe.get("vencimento", ""),
                    "valor_parcela": detalhe.get("valor", ""),
                    "status_parcela": "em aberto",
                }
            )
    try:
        pd.DataFrame(linhas).to_csv(EMPRESTIMOS_ATIVOS_CSV, index=False, encoding="utf-8")
    except Exception:
        return None
    return linhas


def buscar_emprestimos_ativos_por_cpf(cpf):
    cpf_norm = _normalizar_cpf(cpf)
    if not cpf_norm:
        return {"saldo_devedor_num": Decimal("0"), "saldo_devedor": "R$ 0,00", "emprestimos": []}

    ativos = _buscar_emprestimos_ativos()
    atualizar_emprestimos_ativos_csv(ativos=ativos)
    emprestimos_usuario = [item for item in ativos if item.get("cpf") == cpf_norm]
    saldo_total = sum((item.get("saldo_devedor_num", Decimal("0")) for item in emprestimos_usuario), Decimal("0"))
    return {
        "saldo_devedor_num": saldo_total,
        "saldo_devedor": _formatar_real(saldo_total) or "R$ 0,00",
        "emprestimos": emprestimos_usuario,
    }


def buscar_saldos_por_cpf(cpf):
    cpf_normalizado = _normalizar_cpf(cpf)
    if not cpf_normalizado:
        return None

    df = None
    if os.path.exists(INFORMACOES_CSV):
        df = pd.read_csv(INFORMACOES_CSV, dtype=str, encoding="utf-8")

    if df is None or df.empty:
        df = atualizar_informacoes_csv()

    if df is None or df.empty:
        return None

    coluna_cpf = _encontrar_coluna(df.columns, ["cpf"])
    coluna_atual = _encontrar_coluna(df.columns, ["atual", "saldo atual", "saldo_atual", "saldo"])
    coluna_aplicado = _encontrar_coluna(df.columns, ["aplicado"])

    if not coluna_cpf or not coluna_atual:
        df = atualizar_informacoes_csv()
        if df is None or df.empty:
            return None
        coluna_cpf = _encontrar_coluna(df.columns, ["cpf"])
        coluna_atual = _encontrar_coluna(df.columns, ["atual", "saldo atual", "saldo_atual", "saldo"])
        coluna_aplicado = _encontrar_coluna(df.columns, ["aplicado"])
        if not coluna_cpf or not coluna_atual:
            return None

    df["_cpf_norm"] = df[coluna_cpf].apply(_normalizar_cpf)
    linha = df.loc[df["_cpf_norm"] == cpf_normalizado]
    if linha.empty:
        return None

    linha0 = linha.iloc[0]
    saldo_atual = _parse_decimal(linha0[coluna_atual]) if coluna_atual else None
    saldo_aplicado = _parse_decimal(linha0[coluna_aplicado]) if coluna_aplicado else None

    if saldo_atual is None:
        return None

    variacao = None
    if saldo_aplicado is not None:
        variacao = saldo_atual - saldo_aplicado

    return {
        "atual": _formatar_real(saldo_atual),
        "aplicado": _formatar_real(saldo_aplicado) if saldo_aplicado is not None else None,
        "variacao": _formatar_real(variacao) if variacao is not None else None,
        "variacao_num": float(variacao) if variacao is not None else 0,
    }


def buscar_saldos_totais():
    df = None
    if os.path.exists(INFORMACOES_CSV):
        try:
            df = pd.read_csv(INFORMACOES_CSV, dtype=str, encoding="utf-8")
        except Exception:
            df = None

    if df is None or df.empty:
        df = atualizar_informacoes_csv()

    if df is None or df.empty:
        return None

    coluna_atual = _encontrar_coluna(df.columns, ["atual", "saldo atual", "saldo_atual", "saldo"])
    coluna_aplicado = _encontrar_coluna(df.columns, ["aplicado"])
    if not coluna_atual or not coluna_aplicado:
        return None

    total_aplicado = Decimal("0")
    total_atual = Decimal("0")

    for valor in df[coluna_aplicado]:
        numero = _parse_decimal(valor)
        if numero is not None:
            total_aplicado += numero

    for valor in df[coluna_atual]:
        numero = _parse_decimal(valor)
        if numero is not None:
            total_atual += numero

    variacao = total_atual - total_aplicado

    return {
        "aplicado": _formatar_real(total_aplicado),
        "atual": _formatar_real(total_atual),
        "variacao": _formatar_real(variacao),
        "variacao_num": float(variacao),
    }


def buscar_extrato_por_cpf(cpf):
    cpf_normalizado = _normalizar_cpf(cpf)
    if not cpf_normalizado:
        return []

    participantes = carregar_participantes_df()
    if participantes is None or participantes.empty:
        return []

    coluna_cpf = _encontrar_coluna(participantes.columns, ["cpf"])
    coluna_id = _encontrar_coluna(participantes.columns, ["id"])
    if not coluna_cpf or not coluna_id:
        return []

    participantes["_cpf_norm"] = participantes[coluna_cpf].apply(_normalizar_cpf)
    participantes["_id_norm"] = participantes[coluna_id].apply(_normalizar_id)
    linha = participantes.loc[participantes["_cpf_norm"] == cpf_normalizado]
    if linha.empty:
        return []

    id_participante = linha.iloc[0].get("_id_norm")
    if not id_participante:
        return []

    extrato = _carregar_extrato_df()
    if extrato is None or extrato.empty:
        return []

    coluna_id_extrato = _encontrar_coluna(extrato.columns, ["id"])
    coluna_categoria = _encontrar_coluna(extrato.columns, ["categoria"])
    coluna_tipo = _encontrar_coluna(extrato.columns, ["tipo"])
    coluna_data = _encontrar_coluna(extrato.columns, ["data"])
    coluna_valor = _encontrar_coluna(extrato.columns, ["valor"])
    coluna_transacao = (
        _encontrar_coluna(extrato.columns, ["transacao", "transação", "n transacao", "nº transacao", "numero da transacao", "numero transacao"])
        or (extrato.columns[-1] if len(extrato.columns) else None)
    )

    if not coluna_id_extrato or not coluna_data or not coluna_valor or not coluna_transacao:
        return []

    extrato["_id_norm"] = extrato[coluna_id_extrato].apply(_normalizar_id)
    filtrado = extrato.loc[extrato["_id_norm"] == id_participante].copy()
    if filtrado.empty:
        return []

    saida = pd.DataFrame()
    saida["data"] = filtrado[coluna_data].fillna("").astype(str).str.strip()
    saida["categoria"] = filtrado[coluna_categoria].fillna("").astype(str).str.strip() if coluna_categoria else ""
    saida["tipo"] = filtrado[coluna_tipo].fillna("").astype(str).str.strip() if coluna_tipo else ""
    saida["transacao"] = filtrado[coluna_transacao].fillna("").astype(str).str.strip()
    saida["valor_bruto"] = filtrado[coluna_valor].fillna("").astype(str).str.strip()

    datas = pd.to_datetime(saida["data"], errors="coerce")
    saida["_data_sort"] = datas
    saida = saida.sort_values(by="_data_sort", ascending=False).drop(columns=["_data_sort"])

    valores_fmt = []
    classes = []
    for _, row in saida.iterrows():
        valor = row.get("valor_bruto")
        tipo = _normalizar_texto(row.get("tipo"))
        numero = _parse_decimal(valor)
        if numero is None:
            valores_fmt.append(str(valor or ""))
            classes.append("valor-neutro")
            continue

        sinal = ""
        classe = "valor-neutro"
        if "entrada" in tipo:
            sinal = "+"
            classe = "valor-entrada"
        elif "saida" in tipo or "saída" in tipo:
            sinal = "-"
            classe = "valor-saida"

        valores_fmt.append(f"{sinal} {_formatar_real(numero)}".strip())
        classes.append(classe)

    saida["valor"] = valores_fmt
    saida["valor_classe"] = classes
    saida = saida.drop(columns=["valor_bruto"])

    datas_fmt = []
    for valor in saida["data"]:
        dt = pd.to_datetime(valor, errors="coerce")
        if pd.isna(dt):
            datas_fmt.append(valor)
        else:
            datas_fmt.append(dt.strftime("%d/%m/%Y"))
    saida["data"] = datas_fmt

    os.makedirs(CSV_DIR, exist_ok=True)
    saida.to_csv(EXTRATO_CSV, index=False, encoding="utf-8")

    try:
        df_csv = pd.read_csv(EXTRATO_CSV, dtype=str, encoding="utf-8")
    except Exception:
        return []

    if df_csv is None or df_csv.empty:
        return []

    df_csv = df_csv.fillna("")
    return df_csv.to_dict(orient="records")


def buscar_evolucao_caixinha(limite=60):
    # Prioriza relatorio.csv (com cabeçalho)
    if os.path.exists(RELATORIO_CSV):
        try:
            df = pd.read_csv(RELATORIO_CSV, dtype=str, encoding="utf-8")
        except Exception:
            df = None
        if df is not None and not df.empty:
            coluna_valor = _encontrar_coluna(df.columns, ["caixinha 2026", "caixinha2026", "caixinha"])
            coluna_data = _encontrar_coluna(df.columns, ["data"])
            if coluna_valor:
                dados = []
                if isinstance(limite, int):
                    df = df.tail(limite)
                for _, row in df.iterrows():
                    valor_num = _parse_decimal(row.get(coluna_valor))
                    if valor_num is None:
                        continue
                    dados.append({
                        "data": str(row.get(coluna_data, "")).strip() if coluna_data else "",
                        "valor": float(valor_num),
                    })
                return dados

    # Fallback: tenta evolucao_caixinha.csv
    df = atualizar_evolucao_csv()
    if df is None or df.empty:
        if os.path.exists(EVOLUCAO_CSV):
            try:
                df = pd.read_csv(EVOLUCAO_CSV, dtype=str, encoding="utf-8")
            except Exception:
                df = None
    if df is None or df.empty:
        return []

    if "valor" not in df.columns:
        return []

    if isinstance(limite, int):
        df = df.tail(limite)
    dados = []
    for _, row in df.iterrows():
        valor_num = _parse_decimal(row.get("valor"))
        if valor_num is None:
            continue
        dados.append({
            "data": str(row.get("data", "")).strip(),
            "valor": float(valor_num)
        })
    return dados
