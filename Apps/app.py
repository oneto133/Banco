from flask import Flask, render_template, request, redirect, url_for, session
from decimal import Decimal
from datetime import datetime
from email.message import EmailMessage
import csv
import os
import dados
import smtplib
import secrets
import time

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "genio-secret-key")
INACTIVITY_SECONDS = 180

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CSV_DIR = os.path.join(BASE_DIR, "csv")
USER_CSV = os.path.join(CSV_DIR, "usuarios.csv")
CADASTRO_CSV = os.path.join(CSV_DIR, "cadastro.csv")
ENCARGOS_CSV = os.path.join(CSV_DIR, "encargos.csv")

def validar_login(usuario, senha):
    with open(USER_CSV, newline="", encoding="utf-8") as file:
        leitor = csv.DictReader(file)
        for linha in leitor:
            if linha["usuario"] == usuario and linha["senha"] == senha:
                return True
    
    return False

def cadastro_existente(cpf, email):
    if not os.path.exists(CADASTRO_CSV):
        return False
    
    with open(CADASTRO_CSV, newline="", encoding="utf-8") as file:
        leitor = csv.DictReader(file)
        for linha in leitor:
            if linha["cpf"] == cpf or linha["email"] == email:
                return True
            
    return False

def buscar_nome_por_cpf(cpf):
    if not cpf or not os.path.exists(CADASTRO_CSV):
        return None

    with open(CADASTRO_CSV, newline="", encoding="utf-8") as file:
        leitor = csv.DictReader(file)
        for linha in leitor:
            if linha.get("cpf") == cpf:
                return linha.get("nome")

    return None


def buscar_nome_por_cpf_informacoes(cpf):
    if not cpf or not os.path.exists(dados.INFORMACOES_CSV):
        return None

    cpf_norm = dados._normalizar_cpf(cpf)
    if not cpf_norm:
        return None

    try:
        with open(dados.INFORMACOES_CSV, newline="", encoding="utf-8") as file:
            leitor = csv.DictReader(file)
            if not leitor.fieldnames:
                return None
            campos = {name: (name or "").strip().lower() for name in leitor.fieldnames}
            cpf_col = next((orig for orig, low in campos.items() if "cpf" in low), None)
            nome_col = next((orig for orig, low in campos.items() if "nome" in low), None)
            if not cpf_col or not nome_col:
                return None
            for linha in leitor:
                cpf_val = dados._normalizar_cpf(linha.get(cpf_col))
                if cpf_val == cpf_norm:
                    return (linha.get(nome_col) or "").strip() or None
    except Exception:
        return None

    return None


def carregar_encargos():
    if not os.path.exists(ENCARGOS_CSV):
        raise RuntimeError(f"Arquivo de encargos não encontrado: {ENCARGOS_CSV}")

    encargos = {}
    try:
        with open(ENCARGOS_CSV, newline="", encoding="utf-8-sig") as file:
            sample = file.read(2048)
            file.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;")
            except Exception:
                dialect = csv.excel
            reader = csv.DictReader(file, dialect=dialect)
            for row in reader:
                key_raw = None
                val_raw = None
                for k, v in row.items():
                    if k is None:
                        continue
                    key_raw = k if key_raw is None else key_raw
                    if key_raw is not None and v is not None:
                        val_raw = v
                chave = (row.get("chave") or row.get("Chave") or row.get("CHAVE") or "").strip()
                valor = (row.get("valor") or row.get("Valor") or row.get("VALOR") or "").strip()
                if not chave and key_raw and val_raw is not None:
                    chave = str(key_raw).strip()
                    valor = str(val_raw).strip()
                if chave:
                    chave_norm = chave.strip().lower().replace(" ", "_")
                    encargos[chave_norm] = valor
    except Exception as exc:
        raise RuntimeError(f"Falha ao ler encargos.csv: {exc}") from exc

    required = ["juros_mensal", "max_data", "max_parcelas", "max_valor_perc"]
    missing = [key for key in required if not encargos.get(key)]
    if missing:
        raise RuntimeError(f"Campos obrigatórios ausentes em encargos.csv: {', '.join(missing)}")

    # Normaliza valores editáveis no CSV
    juros_txt = str(encargos.get("juros_mensal")).strip().replace("%", "")
    if "," in juros_txt and "." in juros_txt:
        juros_txt = juros_txt.replace(".", "").replace(",", ".")
    else:
        juros_txt = juros_txt.replace(",", ".")
    try:
        encargos["juros_mensal"] = f"{Decimal(juros_txt):.2f}"
    except Exception as exc:
        raise RuntimeError("juros_mensal inválido em encargos.csv") from exc

    max_parcelas_txt = "".join(ch for ch in str(encargos.get("max_parcelas")) if ch.isdigit())
    if not max_parcelas_txt:
        raise RuntimeError("max_parcelas inválido em encargos.csv")
    encargos["max_parcelas"] = max_parcelas_txt

    max_perc_txt = str(encargos.get("max_valor_perc")).strip().replace("%", "")
    if "," in max_perc_txt and "." in max_perc_txt:
        max_perc_txt = max_perc_txt.replace(".", "").replace(",", ".")
    else:
        max_perc_txt = max_perc_txt.replace(",", ".")
    try:
        encargos["max_valor_perc"] = f"{Decimal(max_perc_txt):.2f}"
    except Exception as exc:
        raise RuntimeError("max_valor_perc inválido em encargos.csv") from exc

    max_data_raw = str(encargos.get("max_data")).strip()
    if "/" in max_data_raw:
        try:
            data = datetime.strptime(max_data_raw, "%d/%m/%Y")
            encargos["max_data"] = data.strftime("%Y-%m-%d")
        except Exception as exc:
            raise RuntimeError("max_data inválido em encargos.csv") from exc

    return encargos


def _is_protected_path():
    path = request.path or ""
    if path.startswith("/static"):
        return False
    if path in ["/", "/cadastro", "/confirmar", "/confirmar/reenviar"]:
        return False
    return True


def _send_email(to_address, subject, body, html_body=None):
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port_raw = os.environ.get("SMTP_PORT", "587")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    smtp_use_ssl = os.environ.get("SMTP_USE_SSL", "0").lower() in ["1", "true", "yes", "on"]

    if not smtp_user or not smtp_pass:
        raise RuntimeError("SMTP_USER/SMTP_PASS nao configurados")

    try:
        smtp_port = int(smtp_port_raw)
    except ValueError:
        raise RuntimeError("SMTP_PORT invalido")

    destino = (to_address or "").strip() or smtp_user

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = destino
    msg.set_content(body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        if smtp_use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        with server:
            if not smtp_use_ssl:
                server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as exc:
        raise RuntimeError(f"falha SMTP {smtp_host}:{smtp_port} ({type(exc).__name__})") from exc

    return destino


def _send_test_email(to_address):
    return _send_email(
        to_address,
        "Teste de e-mail",
        "Mensagem de teste enviada pelo sistema."
    )


def _gerar_codigo_verificacao():
    return f"{secrets.randbelow(1000000):06d}"


def _buscar_cadastro_por_cpf_ou_email(cpf, email):
    if not os.path.exists(CADASTRO_CSV):
        return None
    with open(CADASTRO_CSV, newline="", encoding="utf-8") as file:
        leitor = csv.DictReader(file)
        for linha in leitor:
            if (cpf and linha.get("cpf") == cpf) or (email and linha.get("email") == email):
                return linha
    return None


def _atualizar_cadastro_por_cpf_ou_email(cpf, email, updates):
    if not os.path.exists(CADASTRO_CSV):
        return False

    with open(CADASTRO_CSV, newline="", encoding="utf-8") as file:
        leitor = csv.DictReader(file)
        fieldnames = leitor.fieldnames or []
        rows = list(leitor)

    if not fieldnames:
        return False

    for key in updates.keys():
        if key not in fieldnames:
            fieldnames.append(key)

    updated = False
    for row in rows:
        if (cpf and row.get("cpf") == cpf) or (email and row.get("email") == email):
            for key, value in updates.items():
                row[key] = value
            updated = True
            break

    if not updated:
        return False

    with open(CADASTRO_CSV, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return True


def _garantir_campos_cadastro(campos):
    if not os.path.exists(CADASTRO_CSV):
        return campos

    with open(CADASTRO_CSV, newline="", encoding="utf-8") as file:
        leitor = csv.DictReader(file)
        fieldnames = leitor.fieldnames or []
        rows = list(leitor)

    novos = list(fieldnames)
    for campo in campos:
        if campo not in novos:
            novos.append(campo)

    if novos == fieldnames:
        return fieldnames

    with open(CADASTRO_CSV, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=novos)
        writer.writeheader()
        writer.writerows(rows)

    return novos


def _primeiro_nome(texto):
    partes = [p for p in (texto or "").strip().split() if p]
    if not partes:
        return ""
    nome = partes[0]
    return nome[:1].upper() + nome[1:].lower()


@app.before_request
def verificar_sessao():
    if not _is_protected_path():
        return None

    usuario = session.get("usuario")
    last_activity = session.get("last_activity")
    now = int(time.time())

    if not usuario or not last_activity:
        session.clear()
        return redirect(url_for("login", msg="sessao_expirada"))

    if now - int(last_activity) > INACTIVITY_SECONDS:
        session.clear()
        return redirect(url_for("login", msg="sessao_expirada"))

    session["last_activity"] = now
    return None

@app.route("/", methods=["GET", "POST"])
def login():
    msg = request.args.get("msg")
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        if validar_login(usuario, senha):
            session.clear()
            session["usuario"] = usuario
            session["last_activity"] = int(time.time())
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", erro="Usuário inválido")
    
    return render_template("login.html", msg=msg)

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        cpf = request.form["cpf"]
        email = request.form["email"]

        if cadastro_existente(cpf, email):
            return render_template(
                "cadastro.html",
                erro="CPF ou e-mail já cadastrado no sistema."
            )

        codigo = _gerar_codigo_verificacao()
        now = int(time.time())
        expira_em = now + 300

        dados = {
            "nome": request.form["nome"],
            "cpf": cpf,
            "email": email,
            "telefone": request.form["telefone"],
            "cep": request.form["cep"],
            "logradouro": request.form["logradouro"],
            "bairro": request.form["bairro"],
            "cidade": request.form["cidade"],
            "uf": request.form["uf"],
            "numero": request.form["numero"],
            "complemento": request.form["complemento"],
            "status": "Aguardando confirmação",
            "codigo_verificacao": codigo,
            "codigo_enviado_em": str(now),
            "codigo_expira_em": str(expira_em),
            "email_verificado": "nao"
        }

        criar_arquivo = not os.path.exists(CADASTRO_CSV)
        fieldnames = list(dados.keys())
        if not criar_arquivo:
            fieldnames = _garantir_campos_cadastro(fieldnames) or fieldnames

        with open(CADASTRO_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)

            if criar_arquivo:
                writer.writeheader()

            writer.writerow(dados)
 
        try:
            primeiro_nome = _primeiro_nome(dados.get("nome"))
            saudacao = f"Olá, {primeiro_nome}!" if primeiro_nome else "Olá!"
            html = f"""
            <div style="font-family: Arial, sans-serif; padding: 24px; background: linear-gradient(135deg, #b08cff, #3c096c);">
              <div style="max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 14px; padding: 24px; text-align: center;">
                <p style="margin: 0 0 14px 0; color: #2b0038; font-weight: 600;">{saudacao}</p>
                <h2 style="margin: 0 0 12px 0; color: #2b0038;">Código de confirmação</h2>
                <p style="margin: 0 0 22px 0; color: #4b5563;">Use o código abaixo para confirmar seu cadastro:</p>
                <div style="display: inline-block; padding: 18px 26px; font-size: 30px; font-weight: 700; letter-spacing: 6px; background: #f3f4f6; border-radius: 12px; color: #111827;">
                  {codigo}
                </div>
                <p style="margin: 22px 0 0 0; color: #6b7280;">Este código expira em 5 minutos.</p>
                <div style="margin-top: 22px; font-size: 12px; color: #9ca3af;">
                  <span>Esta mensagem é automática. </span>
                  <a href="#" style="color: #6a0dad; text-decoration: underline;">Saiba mais</a>
                </div>
              </div>
            </div>
            """
            _send_email(
                email,
                "Código de confirmação",
                f"{saudacao}\nSeu código de confirmação é: {codigo}\nEle expira em 5 minutos.\n\nEsta mensagem é automática. Saiba mais.",
                html
            )
        except Exception:
            return render_template(
                "cadastro.html",
                erro="Falha ao enviar o código de confirmação. Tente novamente."
            )

        return redirect(url_for(
            "confirmar",
            cpf=cpf,
            email=email
        ))


    return render_template("cadastro.html")


@app.route("/confirmar", methods=["GET", "POST"])
def confirmar():
    if request.method == "POST":
        cpf = (request.form.get("cpf") or "").strip()
        email = (request.form.get("email") or "").strip()
        codigo = (request.form.get("codigo") or "").strip()

        cadastro_row = _buscar_cadastro_por_cpf_ou_email(cpf, email)
        if not cadastro_row:
            return render_template(
                "confirmacao.html",
                erro="Cadastro não encontrado.",
                cpf=cpf,
                email=email
            )

        codigo_salvo = (cadastro_row.get("codigo_verificacao") or "").strip()
        expira_raw = (cadastro_row.get("codigo_expira_em") or "").strip()
        try:
            expira_em = int(expira_raw)
        except ValueError:
            expira_em = 0

        now = int(time.time())
        if now > expira_em:
            return render_template(
                "confirmacao.html",
                erro="Código expirado. Solicite um novo.",
                cpf=cpf,
                email=email
            )

        if not codigo or codigo != codigo_salvo:
            return render_template(
                "confirmacao.html",
                erro="Código inválido.",
                cpf=cpf,
                email=email
            )

        atualizado = _atualizar_cadastro_por_cpf_ou_email(
            cpf,
            email,
            {
                "status": "Pendente de aprovação",
                "email_verificado": "sim",
                "codigo_verificacao": "",
                "codigo_enviado_em": "",
                "codigo_expira_em": ""
            }
        )
        if not atualizado:
            return render_template(
                "confirmacao.html",
                erro="Falha ao atualizar o cadastro.",
                cpf=cpf,
                email=email
            )

        try:
            _send_email(
                email,
                "Cadastro em análise",
                "Seu cadastro foi confirmado e está em análise."
            )
        except Exception:
            pass

        return redirect(url_for("login", msg="cadastro_pendente"))

    cpf = (request.args.get("cpf") or "").strip()
    email = (request.args.get("email") or "").strip()
    return render_template("confirmacao.html", cpf=cpf, email=email)


@app.route("/confirmar/reenviar", methods=["POST"])
def confirmar_reenviar():
    cpf = (request.form.get("cpf") or "").strip()
    email = (request.form.get("email") or "").strip()
    cadastro_row = _buscar_cadastro_por_cpf_ou_email(cpf, email)
    if not cadastro_row:
        return render_template(
            "confirmacao.html",
            erro="Cadastro não encontrado.",
            cpf=cpf,
            email=email
        )

    enviado_raw = (cadastro_row.get("codigo_enviado_em") or "").strip()
    try:
        enviado_em = int(enviado_raw)
    except ValueError:
        enviado_em = 0

    now = int(time.time())
    if now - enviado_em < 60:
        return render_template(
            "confirmacao.html",
            erro="Aguarde 1 minuto para solicitar um novo código.",
            cpf=cpf,
            email=email
        )

    codigo = _gerar_codigo_verificacao()
    expira_em = now + 300
    atualizado = _atualizar_cadastro_por_cpf_ou_email(
        cpf,
        email,
        {
            "codigo_verificacao": codigo,
            "codigo_enviado_em": str(now),
            "codigo_expira_em": str(expira_em)
        }
    )
    if not atualizado:
        return render_template(
            "confirmacao.html",
            erro="Falha ao atualizar o código.",
            cpf=cpf,
            email=email
        )

    try:
        primeiro_nome = _primeiro_nome(cadastro_row.get("nome"))
        saudacao = f"Olá, {primeiro_nome}," if primeiro_nome else "Olá,"
        html = f"""
        <div style="font-family: Arial, sans-serif; padding: 24px; background: linear-gradient(135deg, #b08cff, #3c096c);">
          <div style="max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 14px; padding: 24px; text-align: center;">
            <p style="margin: 0 0 14px 0; color: #2b0038; font-weight: 600;">{saudacao}</p>
            <h2 style="margin: 0 0 12px 0; color: #2b0038;">Novo código de confirmação</h2>
            <p style="margin: 0 0 22px 0; color: #4b5563;">Use o código abaixo para confirmar seu cadastro:</p>
            <div style="display: inline-block; padding: 18px 26px; font-size: 30px; font-weight: 700; letter-spacing: 6px; background: #f3f4f6; border-radius: 12px; color: #111827;">
              {codigo}
            </div>
            <p style="margin: 22px 0 0 0; color: #6b7280;">Este código expira em 5 minutos.</p>
            <div style="margin-top: 22px; font-size: 12px; color: #9ca3af;">
              <span>Esta mensagem é automática. </span>
              <a href="#" style="color: #6a0dad; text-decoration: underline;">Saiba mais</a>
            </div>
          </div>
        </div>
        """
        _send_email(
            email,
            "Novo código de confirmação",
            f"{saudacao}\nSeu novo código é: {codigo}\nEle expira em 5 minutos.\n\nEsta mensagem é automática. Saiba mais.",
            html
        )
    except Exception:
        return render_template(
            "confirmacao.html",
            erro="Falha ao enviar o novo código.",
            cpf=cpf,
            email=email
        )

    return render_template(
        "confirmacao.html",
        sucesso="Novo código enviado.",
        cpf=cpf,
        email=email
    )

@app.route("/dashboard")
def dashboard():
    usuario = session.get("usuario")
    nome = buscar_nome_por_cpf_informacoes(usuario) or buscar_nome_por_cpf(usuario)
    dados.atualizar_informacoes_csv()
    saldos = dados.buscar_saldos_por_cpf(usuario)
    evolucao = dados.buscar_evolucao_caixinha(limite=None)
    dados.gerar_relatorio_csv()
    return render_template("dashboard.html", nome=nome, usuario=usuario, saldos=saldos, evolucao=evolucao)


@app.route("/emprestimo")
def emprestimo():
    usuario = session.get("usuario")
    nome = buscar_nome_por_cpf_informacoes(usuario) or buscar_nome_por_cpf(usuario)
    dados.atualizar_informacoes_csv()
    saldos = dados.buscar_saldos_por_cpf(usuario)

    saldo_aplicado = None
    if saldos and saldos.get("aplicado"):
        saldo_aplicado = dados._parse_decimal(saldos.get("aplicado"))
    if saldo_aplicado is None:
        saldo_aplicado = Decimal("0")

    encargos = carregar_encargos()
    max_perc_txt = encargos.get("max_valor_perc", "20")
    try:
        max_perc_dec = Decimal(str(max_perc_txt))
    except Exception:
        max_perc_dec = Decimal("20")
    saldo_disponivel = saldo_aplicado * (Decimal("1") + (max_perc_dec / Decimal("100")))
    saldo_disponivel_fmt = dados._formatar_real(saldo_disponivel)
    juros_txt = encargos.get("juros_mensal", "4.08")
    try:
        juros_dec = Decimal(str(juros_txt))
        juros_fmt = f"{juros_dec:.2f}".replace(".", ",")
    except Exception:
        juros_fmt = "4,08"
    try:
        max_perc_fmt = f"{Decimal(str(max_perc_txt)):.2f}".replace(".", ",")
    except Exception:
        max_perc_fmt = "20,00"
    max_data_iso = encargos.get("max_data", "2026-11-10")
    try:
        max_data_br = datetime.strptime(max_data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        max_data_br = max_data_iso

    return render_template(
        "emprestimo.html",
        nome=nome,
        usuario=usuario,
        saldo_disponivel=saldo_disponivel_fmt,
        saldo_disponivel_num=str(saldo_disponivel),
        encargos=encargos,
        juros_mensal_fmt=juros_fmt,
        max_data_br=max_data_br,
        max_valor_perc_fmt=max_perc_fmt
    )


@app.route("/relatorio/atualizar")
def atualizar_relatorio():
    if not session.get("usuario"):
        return {"status": "erro"}, 401
    caminho = dados.gerar_relatorio_csv()
    status = "ok" if caminho else "erro"
    return {"status": status}


@app.route("/evolucao/dados")
def evolucao_dados():
    if not session.get("usuario"):
        return [], 401
    limite = request.args.get("limite")
    if limite:
        try:
            limite = int(limite)
        except ValueError:
            limite = None
    else:
        limite = None
    return dados.buscar_evolucao_caixinha(limite=limite)


@app.route("/informacoes/atualizar")
def atualizar_informacoes():
    if not session.get("usuario"):
        return {"status": "erro"}, 401
    df = dados.atualizar_informacoes_csv()
    status = "ok" if df is not None else "erro"
    return {"status": status}


@app.route("/session/ping")
def session_ping():
    if not session.get("usuario"):
        return {"status": "expired"}, 401
    session["last_activity"] = int(time.time())
    return {"status": "ok"}


@app.route("/email/teste", methods=["POST"])
def email_teste():
    if not session.get("usuario"):
        return {"status": "erro", "detail": "nao_autenticado"}, 401

    to_address = None
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        to_address = payload.get("email")
    if to_address is None:
        to_address = request.form.get("email")

    try:
        destino = _send_test_email(to_address)
    except Exception as exc:
        return {"status": "erro", "detail": str(exc)}, 500

    return {"status": "ok", "destino": destino}


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
