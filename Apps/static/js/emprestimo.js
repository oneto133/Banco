const loanToggle = document.getElementById("loanToggle");
const loanPanel = document.getElementById("loanPanel");
const loanAmount = document.getElementById("loanAmount");
const loanInstallments = document.getElementById("loanInstallments");
const loanInterest = document.getElementById("loanInterest");
const loanTotal = document.getElementById("loanTotal");
const loanPerInstallment = document.getElementById("loanPerInstallment");
const loanEndDate = document.getElementById("loanEndDate");
const loanError = document.getElementById("loanError");
const loanMaxDate = document.getElementById("loanMaxDate");
const loanMonthlyRate = document.getElementById("loanMonthlyRate");
const loanProceed = document.getElementById("loanProceed");
const termsCheck = document.getElementById("termsCheck");
const loanStatement = document.getElementById("loanStatement");
const statementOverlay = document.getElementById("statementOverlay");
const statementClose = document.getElementById("statementClose");
const statementPrint = document.getElementById("statementPrint");
const pixKey = document.getElementById("pixKey");
const pixCpf = document.getElementById("pixCpf");
const pixName = document.getElementById("pixName");
const stAmount = document.getElementById("stAmount");
const stInstallments = document.getElementById("stInstallments");
const stRate = document.getElementById("stRate");
const stInterest = document.getElementById("stInterest");
const stTotal = document.getElementById("stTotal");
const stReceiver = document.getElementById("stReceiver");
const stReceiverCpf = document.getElementById("stReceiverCpf");
const stPixKey = document.getElementById("stPixKey");

const formatCurrency = (value) => {
    if (Number.isNaN(value)) return "R$ 0,00";
    return value.toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL"
    });
};

const parseNumber = (value) => {
    if (!value) return 0;
    const text = value.toString().trim();
    if (!text) return 0;
    let normalized = text.replace(/\s+/g, "");
    if (normalized.includes(",") && normalized.includes(".")) {
        normalized = normalized.replace(/\./g, "").replace(",", ".");
    } else if (normalized.includes(",")) {
        normalized = normalized.replace(",", ".");
    }
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
};

const parseISODate = (value) => {
    if (!value) return null;
    const text = value.toString().trim();
    if (!text) return null;
    if (text.includes("/")) {
        const [d, m, y] = text.split("/").map(Number);
        if (!y || !m || !d) return null;
        return new Date(y, m - 1, d);
    }
    const [y, m, d] = text.split("-").map(Number);
    if (!y || !m || !d) return null;
    return new Date(y, m - 1, d);
};

const isValidCpf = (value) => {
    if (!value) return false;
    const digits = value.toString().replace(/\D/g, "");
    if (digits.length !== 11) return false;
    if (/^(\d)\1{10}$/.test(digits)) return false;
    const calc = (base, factor) => {
        let sum = 0;
        for (let i = 0; i < base.length; i++) {
            sum += Number(base[i]) * (factor - i);
        }
        const mod = (sum * 10) % 11;
        return mod === 10 ? 0 : mod;
    };
    const d1 = calc(digits.slice(0, 9), 10);
    const d2 = calc(digits.slice(0, 9) + d1, 11);
    return digits.endsWith(`${d1}${d2}`);
};

const formatBRDate = (date) => {
    if (!date) return "--/--/----";
    return date.toLocaleDateString("pt-BR");
};

const addMonths = (date, months) => {
    const result = new Date(date.getTime());
    const day = result.getDate();
    result.setDate(1);
    result.setMonth(result.getMonth() + months);
    const lastDay = new Date(result.getFullYear(), result.getMonth() + 1, 0).getDate();
    result.setDate(Math.min(day, lastDay));
    return result;
};

const config = (() => {
    if (!loanPanel) return null;
    const limit = parseNumber(loanPanel.dataset.limit);
    const jurosMensal = parseNumber(loanPanel.dataset.juros);
    const maxParcelas = parseInt(loanPanel.dataset.maxParcelas || "24", 10);
    const maxData = parseISODate(loanPanel.dataset.maxData);
    return { limit, jurosMensal, maxParcelas, maxData };
})();

const updateSummary = () => {
    if (!config) return;
    const valor = parseNumber(loanAmount?.value);
    const parcelas = parseInt(loanInstallments?.value || "0", 10);
    const jurosMensal = config.jurosMensal;

    let error = "";

    if (valor > config.limit) {
        error = "O valor desejado ultrapassa o limite máximo disponível.";
    }
    if (parcelas > config.maxParcelas) {
        error = `O número de parcelas não pode ultrapassar ${config.maxParcelas}.`;
    }

    let endDate = null;
    if (parcelas > 0) {
        endDate = addMonths(new Date(), parcelas);
        if (config.maxData && endDate > config.maxData) {
            error = "A data final das parcelas ultrapassa o limite permitido.";
        }
    }

    const jurosTotal = parcelas > 0 ? jurosMensal * parcelas : 0;
    const total = parcelas > 0 ? valor * (1 + (jurosMensal / 100) * parcelas) : 0;
    const perInstallment = parcelas > 0 ? total / parcelas : 0;

    if (loanInterest) loanInterest.textContent = `${jurosTotal.toFixed(2).replace(".", ",")}%`;
    if (loanTotal) loanTotal.textContent = formatCurrency(total);
    if (loanPerInstallment) loanPerInstallment.textContent = formatCurrency(perInstallment);
    if (loanEndDate) loanEndDate.textContent = formatBRDate(endDate);
    if (loanError) loanError.textContent = error;
};

const allFieldsFilled = () => {
    const valor = parseNumber(loanAmount?.value);
    const parcelas = parseInt(loanInstallments?.value || "0", 10);
    const pixKeyVal = (pixKey?.value || "").trim();
    const pixCpfVal = (pixCpf?.value || "").trim();
    const pixNameVal = (pixName?.value || "").trim();
    return (
        valor > 0 &&
        parcelas > 0 &&
        pixKeyVal.length > 0 &&
        pixCpfVal.length > 0 &&
        isValidCpf(pixCpfVal) &&
        pixNameVal.length > 0 &&
        termsCheck?.checked
    );
};

const updateProceedState = () => {
    if (!loanProceed) return;
    loanProceed.disabled = !allFieldsFilled();
};

const fillStatement = () => {
    if (!loanStatement) return;
    const valor = parseNumber(loanAmount?.value);
    const parcelas = parseInt(loanInstallments?.value || "0", 10);
    const jurosMensal = config ? config.jurosMensal : 0;
    const jurosTotal = parcelas > 0 ? jurosMensal * parcelas : 0;
    const total = parcelas > 0 ? valor * (1 + (jurosMensal / 100) * parcelas) : 0;

    if (stAmount) stAmount.textContent = formatCurrency(valor);
    if (stInstallments) stInstallments.textContent = parcelas.toString();
    if (stRate) stRate.textContent = `${jurosMensal.toFixed(2).replace(".", ",")}%`;
    if (stInterest) stInterest.textContent = `${jurosTotal.toFixed(2).replace(".", ",")}%`;
    if (stTotal) stTotal.textContent = formatCurrency(total);
    if (stReceiver) stReceiver.textContent = (pixName?.value || "").trim() || "-";
    if (stReceiverCpf) stReceiverCpf.textContent = (pixCpf?.value || "").trim() || "-";
    if (stPixKey) stPixKey.textContent = (pixKey?.value || "").trim() || "-";
};

if (loanToggle && loanPanel) {
    loanToggle.addEventListener("click", () => {
        loanPanel.classList.toggle("is-hidden");
        if (!loanPanel.classList.contains("is-hidden")) {
            loanAmount?.focus();
        }
    });
}

if (config) {
    if (loanInstallments) {
        loanInstallments.max = String(config.maxParcelas);
        loanInstallments.value = loanInstallments.value || "1";
    }
    if (loanMonthlyRate) {
        loanMonthlyRate.textContent = `${config.jurosMensal.toFixed(2).replace(".", ",")}%`;
    }
    if (loanMaxDate) {
        loanMaxDate.textContent = formatBRDate(config.maxData);
    }
}

[loanAmount, loanInstallments].forEach((el) => {
    if (!el) return;
    el.addEventListener("input", updateSummary);
    el.addEventListener("input", updateProceedState);
});

if (pixKey) pixKey.addEventListener("input", updateProceedState);
if (pixCpf) pixCpf.addEventListener("input", updateProceedState);
if (pixName) pixName.addEventListener("input", updateProceedState);
if (termsCheck) termsCheck.addEventListener("change", updateProceedState);

if (loanProceed) {
    loanProceed.addEventListener("click", () => {
        if (!allFieldsFilled()) {
            if (loanError) {
                const cpfVal = (pixCpf?.value || "").trim();
                if (cpfVal && !isValidCpf(cpfVal)) {
                    loanError.textContent = "CPF do recebedor inválido.";
                } else {
                    loanError.textContent = "Preencha todos os campos e aceite os termos para prosseguir.";
                }
            }
            return;
        }
        fillStatement();
        loanStatement?.classList.remove("is-hidden");
        statementOverlay?.classList.remove("is-hidden");
    });
}

const closeStatement = () => {
    loanStatement?.classList.add("is-hidden");
    statementOverlay?.classList.add("is-hidden");
};

if (statementClose) {
    statementClose.addEventListener("click", closeStatement);
}

if (statementOverlay) {
    statementOverlay.addEventListener("click", closeStatement);
}

if (statementPrint) {
    statementPrint.addEventListener("click", () => {
        window.print();
    });
}

updateSummary();
updateProceedState();
