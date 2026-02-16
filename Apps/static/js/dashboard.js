const profileButton = document.getElementById("profileButton");
const sidePanel = document.getElementById("sidePanel");
const overlay = document.getElementById("overlay");
const closeButton = document.getElementById("closeButton");

const openPanel = () => {
    sidePanel.classList.add("open");
    overlay.classList.add("show");
    sidePanel.setAttribute("aria-hidden", "false");
};

const closePanel = () => {
    sidePanel.classList.remove("open");
    overlay.classList.remove("show");
    sidePanel.setAttribute("aria-hidden", "true");
};

if (profileButton && closeButton && overlay) {
    profileButton.addEventListener("click", openPanel);
    closeButton.addEventListener("click", closePanel);
    overlay.addEventListener("click", closePanel);
}

const dataScript = document.getElementById("evolucaoData");
let evolucaoData = [];
let refreshEvolucaoChart = null;

if (dataScript) {
    try {
        evolucaoData = JSON.parse(dataScript.textContent || "[]");
    } catch (err) {
        evolucaoData = [];
    }
}

const canvas = document.getElementById("evolucaoChart");
const chartWrap = document.getElementById("chartWrap");
const chartCollapse = document.getElementById("chartCollapse");
const chartTooltip = document.getElementById("chartTooltip");
const filterOk = document.getElementById("filterOk");
const filterBtn = document.getElementById("filterBtn");
const filterPanel = document.getElementById("filterPanel");
const filterClose = document.getElementById("filterClose");
const monthsOptions = document.getElementById("monthsOptions");
const monthsGroup = document.getElementById("monthsGroup");
const weeksGroup = document.getElementById("weeksGroup");
const filterClear = document.getElementById("filterClear");
const maToggle = document.getElementById("maToggle");
const maPeriodInput = document.getElementById("maPeriod");
const quickButtons = document.querySelectorAll(".quick-filter");
let chartVisible = false;
let hoverIndex = null;
let chartState = null;
let quickRange = null;

const setChartVisible = (visible) => {
    if (!chartWrap || !chartCollapse) {
        return;
    }
    chartVisible = visible;
    chartWrap.classList.toggle("is-hidden", !visible);
    chartCollapse.classList.toggle("is-open", visible);
};

if (chartCollapse) {
    chartCollapse.addEventListener("click", () => {
        setChartVisible(!chartVisible);
    });
}

setChartVisible(false);

const setFilterVisible = (visible) => {
    if (!filterPanel) return;
    filterPanel.classList.toggle("is-hidden", !visible);
};

if (filterBtn) {
    filterBtn.addEventListener("click", () => {
        setFilterVisible(filterPanel?.classList.contains("is-hidden"));
    });
}

if (filterClose) {
    filterClose.addEventListener("click", () => {
        setFilterVisible(false);
    });
}

document.addEventListener("click", (event) => {
    if (!filterPanel || filterPanel.classList.contains("is-hidden")) return;
    if (filterPanel.contains(event.target)) return;
    if (filterBtn && filterBtn.contains(event.target)) return;
    setFilterVisible(false);
});

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        setFilterVisible(false);
    }
});
if (canvas) {
    const ctx = canvas.getContext("2d");
    const padding = 24;
    const yAxisWidth = 70;
    const plotLeft = padding + yAxisWidth;
    const plotRight = padding;
    const plotTop = padding;
    const plotBottom = padding;
    const resizeCanvas = () => {
        const target = chartWrap ? chartWrap.clientWidth : canvas.clientWidth;
        canvas.width = Math.max(320, Math.floor(target || canvas.width));
        canvas.height = 220;
    };

    const getSeries = () => {
        const values = Array.isArray(evolucaoData)
            ? evolucaoData.map(item => Number(item.valor)).filter(v => !Number.isNaN(v))
            : [];
        const labels = Array.isArray(evolucaoData)
            ? evolucaoData.map(item => (item.data || "").toString().trim())
            : [];
        return { values, labels };
    };
    let filteredIndexes = null;
    const formatCurrency = (value) => `R$ ${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const quickRangeDays = {
        "1d": 1,
        "1w": 7,
        "1m": 30,
        "1y": 365
    };

    const computeQuickIndexes = (values, labels, rangeKey) => {
        const days = quickRangeDays[rangeKey];
        if (!days) return null;
        const dates = labels.map(label => parsePtDate(label));
        const validDates = dates.filter(Boolean);
        if (validDates.length === 0) {
            const count = Math.min(values.length, days);
            return values.map((_, i) => i).slice(-count);
        }
        const maxDate = new Date(Math.max(...validDates.map(d => d.getTime())));
        const start = new Date(maxDate);
        start.setDate(start.getDate() - (days - 1));
        const limit = Math.min(values.length, labels.length);
        const indexes = [];
        for (let i = 0; i < limit; i++) {
            const d = dates[i];
            if (d && d >= start) {
                indexes.push(i);
            }
        }
        return indexes;
    };

    const computeSMA = (arr, period) => {
        if (period < 2) return arr;
        const result = [];
        for (let i = 0; i < arr.length; i++) {
            const start = Math.max(0, i - period + 1);
            const slice = arr.slice(start, i + 1);
            const sum = slice.reduce((acc, v) => acc + v, 0);
            result.push(sum / slice.length);
        }
        return result;
    };

    const drawChart = (mode) => {
        resizeCanvas();
        const width = canvas.width - plotLeft - plotRight;
        const height = canvas.height - plotTop - plotBottom;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const { values, labels } = getSeries();
        const useIndexes = Array.isArray(filteredIndexes) ? filteredIndexes : values.map((_, i) => i);
        const seriesValues = useIndexes.map(i => values[i]).filter(v => typeof v === "number");
        const seriesLabels = useIndexes.map(i => labels[i] || "");
        const maEnabled = maToggle ? maToggle.checked : false;
        const maPeriod = maPeriodInput ? Math.max(2, parseInt(maPeriodInput.value || "2", 10)) : 2;
        const maValues = maEnabled ? computeSMA(seriesValues, maPeriod) : null;

        if (seriesValues.length <= 1) {
            ctx.font = "14px Arial";
            ctx.fillStyle = "#555";
            ctx.fillText("Sem dados suficientes para o gráfico.", padding, canvas.height / 2);
            return;
        }

        const minVal = Math.min(...seriesValues);
        const maxVal = Math.max(...seriesValues);
        const rawRange = maxVal - minVal || 1;
        const range = rawRange * 1.7;
        const minPlot = minVal - rawRange * 0.7;
        chartState = {
            mode,
            seriesValues,
            seriesLabels,
            minPlot,
            range,
            width,
            height,
            plotLeft,
            plotTop
        };

        // Eixo Y com valores centralizados entre as linhas
        const ticks = 4;
        const step = range / ticks;
        ctx.strokeStyle = "rgba(0, 0, 0, 0.08)";
        ctx.lineWidth = 1;
        ctx.font = "12px Arial";
        ctx.fillStyle = "#555";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        ctx.textAlign = "right";
        ctx.textBaseline = "middle";

        for (let i = 0; i <= ticks; i++) {
            const t = i / ticks;
            const y = plotTop + height - t * height;
            ctx.beginPath();
            ctx.moveTo(plotLeft, y);
            ctx.lineTo(plotLeft + width, y);
            ctx.stroke();
        }

        for (let i = 0; i < ticks; i++) {
            const t = (i + 0.5) / ticks;
            const y = plotTop + height - t * height;
            const val = minPlot + (i + 0.5) * step;
            const label = `R$ ${val.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            ctx.fillText(label, plotLeft - 8, y);
        }

        // Eixo X com poucas datas
        if (seriesLabels.length > 1) {
            const maxLabels = 6;
            const stepLabel = Math.max(1, Math.floor(seriesLabels.length / maxLabels));
            ctx.fillStyle = "#555";
            ctx.font = "11px Arial";
            ctx.textAlign = "center";
            ctx.textBaseline = "top";

            for (let i = 0; i < seriesLabels.length; i += stepLabel) {
                const x = plotLeft + (width * i) / (seriesLabels.length - 1);
                const y = plotTop + height + 6;
                const text = seriesLabels[i];
                if (text) {
                    ctx.fillText(text, x, y);
                }
            }
        }

        if (mode === "bar") {
            const barWidth = width / seriesValues.length;
            ctx.fillStyle = "rgba(17, 94, 89, 0.45)";
            ctx.strokeStyle = "rgba(17, 94, 89, 0.9)";
            seriesValues.forEach((val, index) => {
                const x = plotLeft + index * barWidth + barWidth * 0.15;
                const h = ((val - minPlot) / range) * height;
                const y = plotTop + height - h;
                const w = barWidth * 0.7;
                ctx.fillRect(x, y, w, h);
            });
            if (hoverIndex !== null && hoverIndex >= 0 && hoverIndex < seriesValues.length) {
                const idx = hoverIndex;
                const x = plotLeft + (idx + 0.5) * barWidth;
                const val = seriesValues[idx];
                const y = plotTop + height - ((val - minPlot) / range) * height;
                ctx.save();
                ctx.strokeStyle = "rgba(11, 107, 58, 0.35)";
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(x, plotTop);
                ctx.lineTo(x, plotTop + height);
                ctx.stroke();
                ctx.fillStyle = "#ffffff";
                ctx.strokeStyle = "#0b6b3a";
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.arc(x, y, 4.5, 0, Math.PI * 2);
                ctx.fill();
                ctx.stroke();
                ctx.restore();
            }
            return;
        }

        // Linha com área suave
        ctx.strokeStyle = "#0b6b3a";
        ctx.lineWidth = 2;
        ctx.beginPath();
        seriesValues.forEach((val, index) => {
            const x = plotLeft + (width * index) / (seriesValues.length - 1);
            const y = plotTop + height - ((val - minPlot) / range) * height;
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        ctx.stroke();

        ctx.lineTo(plotLeft + width, plotTop + height);
        ctx.lineTo(plotLeft, plotTop + height);
        ctx.closePath();

        const gradient = ctx.createLinearGradient(0, padding, 0, padding + height);
        gradient.addColorStop(0, "rgba(11, 107, 58, 0.28)");
        gradient.addColorStop(1, "rgba(11, 107, 58, 0)");
        ctx.fillStyle = gradient;
        ctx.fill();

        if (maValues) {
            ctx.strokeStyle = "#0b6bb8";
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            maValues.forEach((val, index) => {
                const x = plotLeft + (width * index) / (maValues.length - 1);
                const y = plotTop + height - ((val - minPlot) / range) * height;
                if (index === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            });
            ctx.stroke();
        }

        if (hoverIndex !== null && hoverIndex >= 0 && hoverIndex < seriesValues.length) {
            const idx = hoverIndex;
            const val = seriesValues[idx];
            const x = plotLeft + (width * idx) / (seriesValues.length - 1);
            const y = plotTop + height - ((val - minPlot) / range) * height;
            ctx.save();
            ctx.strokeStyle = "rgba(11, 107, 58, 0.35)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(x, plotTop);
            ctx.lineTo(x, plotTop + height);
            ctx.stroke();
            ctx.fillStyle = "#ffffff";
            ctx.strokeStyle = "#0b6b3a";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(x, y, 4.5, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
            ctx.restore();
        }
    };

    const buttons = document.querySelectorAll(".toggle-btn");
    buttons.forEach(btn => {
        btn.addEventListener("click", () => {
            buttons.forEach(b => b.classList.remove("is-active"));
            btn.classList.add("is-active");
            applyFilter();
            drawChart(btn.dataset.chart);
        });
    });

    const parsePtDate = (value) => {
        if (!value) return null;
        const text = value.toString().trim();
        const isoMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (isoMatch) {
            return new Date(Number(isoMatch[1]), Number(isoMatch[2]) - 1, Number(isoMatch[3]));
        }
        const brMatch = text.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
        if (brMatch) {
            return new Date(Number(brMatch[3]), Number(brMatch[2]) - 1, Number(brMatch[1]));
        }
        const fallback = new Date(text);
        return Number.isNaN(fallback.getTime()) ? null : fallback;
    };

    const buildMonthOptions = () => {
        if (!monthsOptions) return;
        const unique = new Map();
        evolucaoData.forEach(item => {
            if (!item.data) return;
            const d = parsePtDate(item.data);
            if (!d) return;
            const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
            if (!unique.has(key)) {
                const label = d.toLocaleDateString("pt-BR", { month: "short", year: "numeric" });
                unique.set(key, label);
            }
        });
        monthsOptions.innerHTML = "";
        const entries = Array.from(unique.entries()).sort((a, b) => a[0].localeCompare(b[0]));
        entries.forEach(([key, label], idx) => {
            const wrapper = document.createElement("label");
            wrapper.className = "filter-radio";
            const input = document.createElement("input");
            input.type = "radio";
            input.name = "mes";
            input.value = key;
            if (idx === 0) input.checked = true;
            const text = document.createTextNode(label);
            wrapper.appendChild(input);
            wrapper.appendChild(text);
            monthsOptions.appendChild(wrapper);
        });
    };

    const setQuickActive = (rangeKey) => {
        quickRange = rangeKey || null;
        quickButtons.forEach(btn => {
            const isActive = quickRange && btn.dataset.range === quickRange;
            btn.classList.toggle("is-active", Boolean(isActive));
        });
        const periodoTodos = document.querySelector("input[name='periodo'][value='todos']");
        if (quickRange && periodoTodos) {
            periodoTodos.checked = true;
        }
    };

    const toggleGroups = () => {
        const periodo = document.querySelector("input[name='periodo']:checked")?.value;
        if (monthsGroup && weeksGroup) {
            monthsGroup.style.display = periodo === "mes" ? "flex" : "none";
            weeksGroup.style.display = periodo === "semana" ? "flex" : "none";
        }
    };

    const applyFilter = () => {
        const periodo = document.querySelector("input[name='periodo']:checked")?.value;
        const semana = document.querySelector("input[name='semana']:checked")?.value;
        const mesSelecionado = document.querySelector("input[name='mes']:checked")?.value;

        if (!Array.isArray(evolucaoData) || evolucaoData.length === 0) {
            filteredIndexes = null;
            return;
        }

        if (quickRange) {
            const { values, labels } = getSeries();
            const quickIndexes = computeQuickIndexes(values, labels, quickRange);
            filteredIndexes = quickIndexes && quickIndexes.length ? quickIndexes : null;
            return;
        }

        if (periodo === "semana") {
            const wk = parseInt(semana || "1", 10);
            const daysStart = (wk - 1) * 7 + 1;
            const daysEnd = wk * 7;
            filteredIndexes = evolucaoData
                .map((item, idx) => ({ item, idx }))
                .filter(({ item }) => {
                    if (!item.data) return false;
                    const d = parsePtDate(item.data);
                    if (!d) return false;
                    const day = d.getDate();
                    return day >= daysStart && day <= daysEnd;
                })
                .map(({ idx }) => idx);
        } else if (periodo === "mes") {
            if (mesSelecionado) {
                filteredIndexes = evolucaoData
                    .map((item, idx) => ({ item, idx }))
                    .filter(({ item }) => {
                        if (!item.data) return false;
                        const d = parsePtDate(item.data);
                        if (!d) return false;
                        const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
                        return key === mesSelecionado;
                    })
                    .map(({ idx }) => idx);
            } else {
                filteredIndexes = null;
            }
        } else {
            filteredIndexes = null;
        }
    };

    const initialMode = document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line";
    buildMonthOptions();
    toggleGroups();
    if (quickButtons && quickButtons.length) {
        quickButtons.forEach(btn => {
            btn.addEventListener("click", () => {
                const rangeKey = btn.dataset.range || "";
                if (quickRange === rangeKey) {
                    setQuickActive(null);
                } else {
                    setQuickActive(rangeKey);
                }
                applyFilter();
                drawChart(document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line");
            });
        });
    }
    document.querySelectorAll("input[name='periodo']").forEach(r => {
        r.addEventListener("change", toggleGroups);
    });
    applyFilter();
    drawChart(initialMode);
    hoverIndex = null;

    if (filterOk) {
        filterOk.addEventListener("click", () => {
            setQuickActive(null);
            applyFilter();
            drawChart(document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line");
            setFilterVisible(false);
        });
    }

    if (maToggle || maPeriodInput) {
        const redraw = () => drawChart(document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line");
        if (maToggle) maToggle.addEventListener("change", redraw);
        if (maPeriodInput) maPeriodInput.addEventListener("input", redraw);
    }

    if (filterClear) {
        filterClear.addEventListener("click", () => {
            const periodoTodos = document.querySelector("input[name='periodo'][value='todos']");
            if (periodoTodos) periodoTodos.checked = true;
            const semana1 = document.querySelector("input[name='semana'][value='1']");
            if (semana1) semana1.checked = true;
            const mesFirst = document.querySelector("input[name='mes']");
            if (mesFirst) mesFirst.checked = true;
            if (maToggle) maToggle.checked = true;
            if (maPeriodInput) maPeriodInput.value = "2";
            toggleGroups();
            setQuickActive(null);
            filteredIndexes = null;
            drawChart(document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line");
        });
    }

    if (chartWrap) {
        const observer = new MutationObserver(() => {
            if (!chartWrap.classList.contains("is-hidden")) {
                drawChart(document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line");
            }
        });
        observer.observe(chartWrap, { attributes: true, attributeFilter: ["class"] });
    }

    window.addEventListener("resize", () => {
        drawChart(document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line");
    });

    if (chartWrap && chartTooltip) {
        const hideTooltip = () => {
            chartTooltip.style.opacity = "0";
            chartTooltip.setAttribute("aria-hidden", "true");
        };

        const updateTooltip = (event) => {
            if (!chartState || !chartState.seriesValues || chartState.seriesValues.length < 2) {
                hoverIndex = null;
                hideTooltip();
                return;
            }

            const rect = canvas.getBoundingClientRect();
            const wrapRect = chartWrap.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const canvasX = (event.clientX - rect.left) * scaleX;

            const { seriesValues, seriesLabels, minPlot, range, width, height, plotLeft, plotTop, mode } = chartState;
            if (canvasX < plotLeft || canvasX > plotLeft + width) {
                hoverIndex = null;
                hideTooltip();
                drawChart(document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line");
                return;
            }

            let idx = 0;
            if (mode === "bar") {
                const barWidth = width / seriesValues.length;
                idx = Math.floor((canvasX - plotLeft) / barWidth);
            } else {
                idx = Math.round(((canvasX - plotLeft) / width) * (seriesValues.length - 1));
            }
            idx = Math.max(0, Math.min(seriesValues.length - 1, idx));
            hoverIndex = idx;

            const value = seriesValues[idx];
            const label = seriesLabels[idx] || "";
            const tooltipText = label ? `${label} • ${formatCurrency(value)}` : formatCurrency(value);
            chartTooltip.textContent = tooltipText;

            const pointX = mode === "bar"
                ? plotLeft + (idx + 0.5) * (width / seriesValues.length)
                : plotLeft + (width * idx) / (seriesValues.length - 1);
            const pointY = plotTop + height - ((value - minPlot) / range) * height;

            const left = Math.max(14, Math.min(wrapRect.width - 14, (rect.left - wrapRect.left) + (pointX / scaleX)));
            const top = Math.max(12, (rect.top - wrapRect.top) + (pointY / (canvas.height / rect.height)));

            chartTooltip.style.left = `${left}px`;
            chartTooltip.style.top = `${top}px`;
            chartTooltip.style.opacity = "1";
            chartTooltip.setAttribute("aria-hidden", "false");

            drawChart(document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line");
        };

        canvas.addEventListener("mousemove", updateTooltip);
        canvas.addEventListener("mouseleave", () => {
            hoverIndex = null;
            hideTooltip();
            drawChart(document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line");
        });
    }

    refreshEvolucaoChart = (data) => {
        evolucaoData = Array.isArray(data) ? data : [];
        buildMonthOptions();
        toggleGroups();
        applyFilter();
        drawChart(document.querySelector(".toggle-btn.is-active")?.dataset.chart || "line");
        hoverIndex = null;
        if (chartTooltip) {
            chartTooltip.style.opacity = "0";
            chartTooltip.setAttribute("aria-hidden", "true");
        }
    };
}

const atualizarRelatorio = async () => {
    try {
        await fetch("/relatorio/atualizar", { method: "GET" });
        await fetch("/informacoes/atualizar", { method: "GET" });
        const response = await fetch("/evolucao/dados");
        if (response.ok) {
            const data = await response.json();
            if (refreshEvolucaoChart) {
                refreshEvolucaoChart(data);
            } else {
                evolucaoData = data;
            }
        } else if (response.status === 401) {
            window.location.href = "/?msg=sessao_expirada";
        }
    } catch (err) {
        // silencioso
    }
};

atualizarRelatorio();
setInterval(atualizarRelatorio, 40000);

let lastActivityPing = 0;
const pingSession = async () => {
    const now = Date.now();
    if (now - lastActivityPing < 15000) return;
    lastActivityPing = now;
    try {
        const res = await fetch("/session/ping", { method: "GET" });
        if (res.status === 401) {
            window.location.href = "/?msg=sessao_expirada";
        }
    } catch (err) {
        // silencioso
    }
};

["click", "mousemove", "keydown", "scroll", "touchstart"].forEach(evt => {
    document.addEventListener(evt, pingSession, { passive: true });
});
