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
SHEET_NAME = "participantes"
SHEET_BASE = "Base"


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
