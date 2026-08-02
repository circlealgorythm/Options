// Option Levels Dashboard - Frontend Application Logic (Russian Version + LocalStorage persistence)

// State management
let state = {
    currency: 'EUR',
    date: '',
    data: null,
    chart: null,
    activeTab: 'calculated', // 'calculated' or 'key-strikes'
    search: '',
    syncStatus: null,
    zeroGamma: null,
    maxGammaStrike: null,
    currentView: 'dashboard', // 'dashboard' or 'analysis'
    activeAnalysisTab: 'weekly', // 'weekly', 'monday', etc.
    analysisData: null,
    noiseThresholdPercent: 2.0, // Default 2.0%
    adaptSpot: false
};

// Elements
const elements = {
    dateSelect: document.getElementById('date-select'),
    currencyTabs: document.querySelectorAll('.currency-tab'),
    toggleGex: document.getElementById('toggle-gex'),
    toggleGamma: document.getElementById('toggle-gamma'),
    toggleSpot: document.getElementById('toggle-spot'),
    toggleBands: document.getElementById('toggle-bands'),
    toggleZeroGamma: document.getElementById('toggle-zerogamma'),
    toggleAdaptSpot: document.getElementById('toggle-adapt-spot'),
    noiseFilterSlider: document.getElementById('noise-filter-slider'),
    noiseFilterVal: document.getElementById('noise-filter-val'),
    btnUpdate: document.getElementById('btn-update'),
    btnExport: document.getElementById('btn-export'),
    btnRefresh: document.getElementById('btn-refresh'),
    syncText: document.getElementById('sync-text'),
    mt5DirText: document.getElementById('mt5-dir-text'),
    sessionTime: document.getElementById('session-time'),
    statusDbDate: document.getElementById('status-db-date'),
    
    // Metric Cards
    metricSpot: document.getElementById('metric-spot'),
    metricSpotCurrency: document.getElementById('metric-spot-currency'),
    metricNetGex: document.getElementById('metric-net-gex'),
    metricGexIcon: document.getElementById('metric-gex-icon'),
    metricGexProgress: document.getElementById('metric-gex-progress'),
    metricZeroGamma: document.getElementById('metric-zero-gamma'),
    metricMaxGamma: document.getElementById('metric-max-gamma'),
    metricMaxGammaVal: document.getElementById('metric-max-gamma-val'),
    metricMonths: document.getElementById('metric-months'),
    
    // Table
    tableSearch: document.getElementById('table-search'),
    searchBoxWrapper: document.getElementById('search-box-wrapper'),
    filterBtns: document.querySelectorAll('.filter-btn'),
    tableHead: document.getElementById('levels-table-head'),
    tableBody: document.getElementById('levels-table-body'),
    
    // Modal
    pipelineModal: document.getElementById('pipeline-modal'),
    modalTerminalLog: document.getElementById('modal-terminal-log'),
    btnCloseModal: document.getElementById('btn-close-modal'),

    // GEX Analysis elements
    navBtns: document.querySelectorAll('.nav-menu .nav-btn'),
    analysisViewContainer: document.getElementById('analysis-view-container'),
    analysisTabBtns: document.querySelectorAll('.analysis-tab-btn'),
    analysisContent: document.getElementById('analysis-content'),
    analysisUpdatedLabel: document.getElementById('analysis-updated-label'),
    metricsGrid: document.querySelector('.metrics-grid'),
    chartSection: document.querySelector('.chart-section'),
    tableSection: document.querySelector('.table-section')
};

// Formatting helpers
function formatGEX(value) {
    if (value === undefined || isNaN(value)) return '0.00M';
    const absVal = Math.abs(value);
    const sign = value >= 0 ? '+' : '-';
    if (absVal >= 1e9) {
        return sign + (absVal / 1e9).toFixed(2) + 'B';
    } else if (absVal >= 1e6) {
        return sign + (absVal / 1e6).toFixed(2) + 'M';
    } else if (absVal >= 1e3) {
        return sign + (absVal / 1e3).toFixed(1) + 'K';
    } else if (absVal > 0 && absVal < 1.0) {
        return sign + absVal.toFixed(4);
    } else if (absVal > 0 && absVal < 10.0) {
        return sign + absVal.toFixed(2);
    }
    return sign + absVal.toFixed(0);
}

// Load saved settings from LocalStorage
function loadSavedState() {
    // 1. Currency Pair
    const savedCurrency = localStorage.getItem('gex_dashboard_currency');
    if (savedCurrency === 'GBP' || savedCurrency === 'EUR' || savedCurrency === 'XAU' || savedCurrency === 'NAS' || savedCurrency === 'SPX' || savedCurrency === 'BTC' || savedCurrency === 'USDCAD') {
        state.currency = savedCurrency;
        elements.currencyTabs.forEach(t => {
            if (t.dataset.currency === savedCurrency) {
                t.classList.add('active');
            } else {
                t.classList.remove('active');
            }
        });
    }

    // 2. Option Trade Date (Disabled localStorage restore on startup to always default to the latest date)
    /*
    const savedDate = localStorage.getItem('gex_dashboard_date');
    if (savedDate) {
        state.date = savedDate;
    }
    */

    // 3. Display Toggles
    const loadCheckbox = (id, storageKey) => {
        const val = localStorage.getItem(storageKey);
        const el = document.getElementById(id);
        if (val !== null && el) {
            el.checked = (val === 'true');
        }
    };
    loadCheckbox('toggle-gex', 'gex_dashboard_show_gex');
    loadCheckbox('toggle-gamma', 'gex_dashboard_show_gamma');
    loadCheckbox('toggle-spot', 'gex_dashboard_show_spot');
    loadCheckbox('toggle-bands', 'gex_dashboard_show_bands');
    loadCheckbox('toggle-zerogamma', 'gex_dashboard_show_zerogamma');
    loadCheckbox('toggle-adapt-spot', 'gex_dashboard_adapt_spot');
    state.adaptSpot = elements.toggleAdaptSpot ? elements.toggleAdaptSpot.checked : false;

    // 4. Current View
    const savedView = localStorage.getItem('gex_dashboard_view');
    if (savedView === 'dashboard' || savedView === 'analysis') {
        state.currentView = savedView;
        elements.navBtns.forEach(b => {
            if (b.dataset.view === savedView) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });
    }

    // 5. Active Analysis Tab
    const savedAnalysisTab = localStorage.getItem('gex_dashboard_analysis_tab');
    if (savedAnalysisTab) {
        state.activeAnalysisTab = savedAnalysisTab;
        elements.analysisTabBtns.forEach(b => {
            if (b.dataset.day === savedAnalysisTab) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });
    }

    // 6. Noise threshold
    const savedNoise = localStorage.getItem('gex_dashboard_noise_filter');
    if (savedNoise) {
        state.noiseThresholdPercent = parseFloat(savedNoise);
    } else {
        // Set dynamic default based on currency
        state.noiseThresholdPercent = state.currency === 'XAU' ? 5.0 : (state.currency === 'NAS' || state.currency === 'SPX' ? 2.0 : (state.currency === 'BTC' ? 2.0 : 1.0));
    }
    
    if (elements.noiseFilterSlider) {
        elements.noiseFilterSlider.value = state.noiseThresholdPercent;
    }
    if (elements.noiseFilterVal) {
        elements.noiseFilterVal.textContent = state.noiseThresholdPercent.toFixed(1) + '%';
    }
}

function formatGamma(value) {
    if (value === undefined || isNaN(value)) return '0.0K';
    const absVal = Math.abs(value);
    if (absVal >= 1e6) {
        return (absVal / 1e6).toFixed(2) + 'M';
    } else if (absVal >= 1e3) {
        return (absVal / 1e3).toFixed(1) + 'K';
    } else if (absVal > 0 && absVal < 1.0) {
        return absVal.toFixed(4);
    } else if (absVal > 0 && absVal < 10.0) {
        return absVal.toFixed(2);
    }
    return absVal.toFixed(1);
}

function formatPrice(value) {
    if (value === undefined || isNaN(value)) return (state.currency === 'XAU' || state.currency === 'NAS' || state.currency === 'SPX' || state.currency === 'BTC') ? '0.00' : '0.0000';
    return (state.currency === 'XAU' || state.currency === 'NAS' || state.currency === 'SPX' || state.currency === 'BTC') ? value.toFixed(2) : value.toFixed(4);
}

// Start live clock widget
function startClock() {
    setInterval(() => {
        const now = new Date();
        elements.sessionTime.innerHTML = `<i class="fa-solid fa-clock"></i> ${now.toTimeString().split(' ')[0]}`;
    }, 1000);
}

// Fetch Dates dropdown
async function fetchDates() {
    try {
        const response = await fetch(`/api/dates?currency=${state.currency}`);
        const payload = await response.json();
        
        elements.dateSelect.innerHTML = '';
        if (payload.dates && payload.dates.length > 0) {
            payload.dates.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d;
                opt.textContent = d;
                elements.dateSelect.appendChild(opt);
            });
            
            // Check if saved state date is in the list
            if (state.date && payload.dates.includes(state.date)) {
                elements.dateSelect.value = state.date;
            } else {
                state.date = payload.dates[0]; // default to latest
                elements.dateSelect.value = state.date;
                localStorage.setItem('gex_dashboard_date', state.date);
            }
        } else {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'Нет доступных дат';
            elements.dateSelect.appendChild(opt);
        }
    } catch (e) {
        console.error('Error fetching dates', e);
        elements.dateSelect.innerHTML = '<option value="">Ошибка загрузки дат</option>';
    }
}

// Fetch MT5 Sync Status
async function fetchSyncStatus() {
    try {
        const response = await fetch('/api/status');
        const payload = await response.json();
        state.syncStatus = payload;
        
        if (payload.exists) {
            elements.syncText.innerHTML = `Синхронизация MT5 активна (${payload.sync_files_count} ф.)`;
            elements.syncText.previousElementSibling.className = 'status-indicator online';
            elements.mt5DirText.innerHTML = `Путь: ${payload.mt5_directory}`;
        } else {
            elements.syncText.innerHTML = 'Синхронизация MT5 отключена';
            elements.syncText.previousElementSibling.className = 'status-indicator offline';
            elements.mt5DirText.innerHTML = 'Укажите путь в MT5_GEX_DIR';
        }
    } catch (e) {
        elements.syncText.innerHTML = 'Ошибка подключения к серверу';
        elements.syncText.previousElementSibling.className = 'status-indicator offline';
        elements.mt5DirText.innerHTML = 'Не удалось запросить статус терминала';
    }
}

// Detect Zero Gamma by interpolation; no sign crossing means no level.
function findZeroGammaStrike(levels, spot) {
    if (!levels || levels.length < 2) return null;
    if (!spot) spot = state.data?.metadata?.spot || 0;
    
    // Sort levels ascending by strike
    const sorted = [...levels].sort((a, b) => a.strike - b.strike);
    
    let closestZeroStrike = null;
    let minDistance = Infinity;
    
    // Check points where GEX changes sign
    for (let i = 0; i < sorted.length - 1; i++) {
        const curr = sorted[i];
        const next = sorted[i+1];
        
        if ((curr.gex >= 0 && next.gex < 0) || (curr.gex < 0 && next.gex >= 0)) {
            const denominator = Math.abs(curr.gex) + Math.abs(next.gex);
            if (denominator === 0) continue;
            const weight = Math.abs(curr.gex) / denominator;
            const transitionStrike = curr.strike + weight * (next.strike - curr.strike);
            const dist = Math.abs(transitionStrike - spot);
            if (dist < minDistance) {
                minDistance = dist;
                closestZeroStrike = transitionStrike;
            }
        }
    }
    
    return closestZeroStrike;
}

// Fetch dashboard option level data
async function fetchLevelData() {
    try {
        const url = `/api/data?currency=${state.currency}&date=${state.date}`;
        const response = await fetch(url);
        const payload = await response.json();
        
        if (payload.error) {
            let errorMsg = payload.error;
            elements.tableBody.innerHTML = `<tr><td colspan="10" class="text-center value-red">${errorMsg}</td></tr>`;
            clearDashboardData();
            return;
        }

        state.data = payload;
        
        // Update summary metrics
        updateMetrics(payload);
        
        // Update data table (Calculated or Key Strikes)
        renderTable(payload.levels, payload.metadata.spot);
        
        // Update chart
        renderChart(payload);
        
        // Update DB Date Badge
        elements.statusDbDate.innerHTML = `<i class="fa-solid fa-database"></i> ${payload.metadata.date}`;
        
    } catch (e) {
        console.error('Error fetching levels data', e);
        elements.tableBody.innerHTML = `<tr><td colspan="10" class="text-center value-red">Ошибка чтения опционных уровней из API.</td></tr>`;
        clearDashboardData();
    }
}

// Clear dashboard chart and reset metric cards to default states on error
function clearDashboardData() {
    if (elements.metricSpot) elements.metricSpot.textContent = '0.00';
    if (elements.metricSpotCurrency) {
        const currencyLabel = state.currency.includes('USD') ? state.currency : `${state.currency}USD`;
        elements.metricSpotCurrency.textContent = `Опорный спот ${currencyLabel}`;
    }
    if (elements.metricNetGex) {
        elements.metricNetGex.textContent = '0.00';
        elements.metricNetGex.className = 'value';
    }
    if (elements.metricZeroGamma) elements.metricZeroGamma.textContent = '0.00';
    if (elements.metricMaxGamma) elements.metricMaxGamma.textContent = '0.00';
    if (elements.metricMaxGammaVal) elements.metricMaxGammaVal.textContent = 'GEX: 0.00';
    if (elements.metricMonths) elements.metricMonths.textContent = 'Периоды: -';
    if (elements.statusDbDate) elements.statusDbDate.innerHTML = `<i class="fa-solid fa-database"></i> Нет данных`;

    if (state.chart) {
        state.chart.destroy();
        state.chart = null;
    }
}


// Update Metric Cards
function updateMetrics(payload) {
    const meta = payload.metadata;
    const levels = payload.levels;
    const offset = (state.adaptSpot && Number.isFinite(meta.live_offset)) ? meta.live_offset : 0;
    
    // Spot Price
    elements.metricSpot.textContent = formatPrice(meta.spot + offset);
    const currencyLabel = meta.currency.includes('USD') ? meta.currency : `${meta.currency}USD`;
    const adaptedLabel = meta.offset_status === 'historical_open' ? 'Исторический спот' : 'Живой спот';
    elements.metricSpotCurrency.textContent = state.adaptSpot ? `${adaptedLabel} ${currencyLabel}` : `Опорный фьючерс ${currencyLabel}`;
    
    // Net GEX
    const totalGex = levels.reduce((acc, curr) => acc + curr.gex, 0);
    elements.metricNetGex.textContent = formatGEX(totalGex);
    if (totalGex >= 0) {
        elements.metricNetGex.className = 'value value-green';
        elements.metricGexIcon.className = 'card-icon icon-green';
        elements.metricGexProgress.className = 'card-progress bg-green';
    } else {
        elements.metricNetGex.className = 'value value-red';
        elements.metricGexIcon.className = 'card-icon icon-red';
        elements.metricGexProgress.className = 'card-progress bg-red';
    }
    
    // Zero Gamma
    const zeroGammaStrike = (meta.gamma_flip && meta.gamma_flip > 0) ? meta.gamma_flip : findZeroGammaStrike(levels, meta.spot);
    state.zeroGamma = zeroGammaStrike;
    elements.metricZeroGamma.textContent = zeroGammaStrike === null ? '—' : formatPrice(zeroGammaStrike + offset);
    
    // Max Abs Gamma
    let maxGamma = 0;
    let maxGammaStrike = 0;
    levels.forEach(l => {
        if (l.gamma > maxGamma) {
            maxGamma = l.gamma;
            maxGammaStrike = l.strike;
        }
    });
    state.maxGammaStrike = maxGammaStrike;
    elements.metricMaxGamma.textContent = formatPrice(maxGammaStrike + offset);
    elements.metricMaxGammaVal.textContent = `Сила: ${formatGamma(maxGamma)}`;
    
    // Option Months
    const dailyExpiry = meta.daily_expiry && meta.daily_expiry !== 'UNKNOWN' ? ` @ ${meta.daily_expiry}` : '';
    const globalExpiry = meta.global_expiry && meta.global_expiry !== 'UNKNOWN' ? ` @ ${meta.global_expiry}` : '';
    const qualityStatus = meta.quality_status && meta.quality_status !== 'UNKNOWN' ? ` | DATA: ${meta.quality_status}` : '';
    const referenceSources = meta.spot_source && meta.iv_source
        ? ` | REF: ${meta.spot_source}/${meta.iv_source}`
        : '';
    elements.metricMonths.textContent = `DLY: ${meta.daily_month}${dailyExpiry} | GLB: ${meta.global_month}${globalExpiry}${qualityStatus}${referenceSources}`;
    elements.metricMonths.title = meta.quality_reasons && meta.quality_reasons !== 'NONE'
        ? meta.quality_reasons
        : '';
}

// Render data table (Dynamic: Calculated Levels or Key Strikes Only)
function renderTable(levels, spot) {
    elements.tableBody.innerHTML = '';
    const liveOffset = state.data?.metadata?.live_offset;
    const offset = (state.adaptSpot && Number.isFinite(liveOffset)) ? liveOffset : 0;
    const adaptedSpot = spot + offset;
    
    if (state.activeTab === 'calculated') {
        // Hide search box for calculated view
        elements.searchBoxWrapper.style.display = 'none';
        
        // Render Headers for Calculated Levels
        elements.tableHead.innerHTML = `
            <tr>
                <th>Название уровня</th>
                <th>Базовый страйк</th>
                <th>Формула расчета</th>
                <th>Итоговая цена (уровень)</th>
                <th>Расстояние от спота</th>
                <th>Открытый интерес (OI)</th>
                <th>Тип уровня</th>
            </tr>
        `;
        
        // Find key rows
        const dailyCallRow = levels.find(l => l.daily_call_oi > 0 && l.daily_call_settle > 0);
        const dailyPutRow = levels.find(l => l.daily_put_oi > 0 && l.daily_put_settle > 0);
        const globalCallRow = levels.find(l => l.global_call_oi > 0);
        const globalPutRow = levels.find(l => l.global_put_oi > 0);
        
        const calcLevels = [];
        const meta = state.data.metadata;
        
        // 1. Spot base
        calcLevels.push({
            name: state.adaptSpot ? 'Живая цена спот (База)' : 'Текущий спот фьючерса (База)',
            baseStrike: adaptedSpot,
            formula: 'Рыночная цена спот',
            price: adaptedSpot,
            oi: '-',
            badge: 'badge-bg-cyan',
            badgeText: 'FUT SPOT'
        });

        const isXAU = state.currency === 'XAU' || state.currency === 'NAS' || state.currency === 'SPX' || state.currency === 'BTC';

        // 2. Daily Call MDD
        if (dailyCallRow) {
            calcLevels.push({
                name: 'Дн./Нед. Call MDD (Сопротивление)',
                baseStrike: dailyCallRow.strike + offset,
                formula: isXAU ? 
                    `${(dailyCallRow.strike + offset).toFixed(2)} + ${dailyCallRow.daily_call_settle.toFixed(2)}` :
                    `${(dailyCallRow.strike + offset).toFixed(4)} + ${dailyCallRow.daily_call_settle.toFixed(5)}`,
                price: dailyCallRow.strike + dailyCallRow.daily_call_settle + offset,
                oi: dailyCallRow.daily_call_oi.toLocaleString(),
                badge: 'badge-bg-green',
                badgeText: 'Daily Call MDD'
            });
        }
        
        // 3. Daily Put MDD
        if (dailyPutRow) {
            calcLevels.push({
                name: 'Дн./Нед. Put MDD (Поддержка)',
                baseStrike: dailyPutRow.strike + offset,
                formula: isXAU ? 
                    `${(dailyPutRow.strike + offset).toFixed(2)} - ${dailyPutRow.daily_put_settle.toFixed(2)}` :
                    `${(dailyPutRow.strike + offset).toFixed(4)} - ${dailyPutRow.daily_put_settle.toFixed(5)}`,
                price: dailyPutRow.strike - dailyPutRow.daily_put_settle + offset,
                oi: dailyPutRow.daily_put_oi.toLocaleString(),
                badge: 'badge-bg-red',
                badgeText: 'Daily Put MDD'
            });
        }

        // 4. Zero Gamma
        if (state.zeroGamma) {
            calcLevels.push({
                name: 'Точка переворота Zero Gamma',
                baseStrike: state.zeroGamma + offset,
                formula: 'Пересечение GEX = 0',
                price: state.zeroGamma + offset,
                oi: '-',
                badge: 'badge-bg-gold',
                badgeText: 'Zero Gamma'
            });
        }

        // 5. Max Abs Gamma Magnet
        if (state.maxGammaStrike) {
            const maxAbsGammaRow = levels.find(l => l.strike === state.maxGammaStrike);
            calcLevels.push({
                name: 'Макс. Абс. Гамма (Страйк-магнит)',
                baseStrike: state.maxGammaStrike + offset,
                formula: `Максимальная Гамма (${formatGamma(maxAbsGammaRow?.gamma)})`,
                price: state.maxGammaStrike + offset,
                oi: '-',
                badge: 'badge-bg-purple',
                badgeText: 'Max Gamma'
            });
        }

        // 6. Global Call
        if (globalCallRow) {
            calcLevels.push({
                name: 'Глобальный Call барьер (Max OI)',
                baseStrike: globalCallRow.strike + offset,
                formula: 'Глобальный месячный Call',
                price: globalCallRow.strike + offset,
                oi: globalCallRow.global_call_oi.toLocaleString(),
                badge: 'badge-bg-green',
                badgeText: 'Glob Call'
            });
        }

        // 7. Global Put
        if (globalPutRow) {
            calcLevels.push({
                name: 'Глобальный Put барьер (Max OI)',
                baseStrike: globalPutRow.strike + offset,
                formula: 'Глобальный месячный Put',
                price: globalPutRow.strike + offset,
                oi: globalPutRow.global_put_oi.toLocaleString(),
                badge: 'badge-bg-red',
                badgeText: 'Glob Put'
            });
        }
        // 8. Expected Move Bands
        if (meta.r68_high > 0) {
            calcLevels.push({
                name: 'Граница Expected Move R68 Вверх',
                baseStrike: adaptedSpot,
                formula: isXAU ? `${adaptedSpot.toFixed(2)} + 1σ` : `${adaptedSpot.toFixed(4)} + 1σ`,
                price: meta.r68_high + offset,
                oi: '-',
                badge: 'badge-bg-cyan',
                badgeText: 'R68 ВЕРХ'
            });
        }
        if (meta.r68_low > 0) {
            calcLevels.push({
                name: 'Граница Expected Move R68 Низ',
                baseStrike: adaptedSpot,
                formula: isXAU ? `${adaptedSpot.toFixed(2)} - 1σ` : `${adaptedSpot.toFixed(4)} - 1σ`,
                price: meta.r68_low + offset,
                oi: '-',
                badge: 'badge-bg-cyan',
                badgeText: 'R68 НИЗ'
            });
        }
        if (meta.r95_high > 0) {
            calcLevels.push({
                name: 'Граница Expected Move R95 Вверх (Экстремум)',
                baseStrike: adaptedSpot,
                formula: isXAU ? `${adaptedSpot.toFixed(2)} + 2σ` : `${adaptedSpot.toFixed(4)} + 2σ`,
                price: meta.r95_high + offset,
                oi: '-',
                badge: 'badge-bg-cyan',
                badgeText: 'R95 ВЕРХ'
            });
        }
        if (meta.r95_low > 0) {
            calcLevels.push({
                name: 'Граница Expected Move R95 Низ (Экстремум)',
                baseStrike: adaptedSpot,
                formula: isXAU ? `${adaptedSpot.toFixed(2)} - 2σ` : `${adaptedSpot.toFixed(4)} - 2σ`,
                price: meta.r95_low + offset,
                oi: '-',
                badge: 'badge-bg-cyan',
                badgeText: 'R95 НИЗ'
            });
        }
        // Sort descending by price (so resistance is top, spot middle, support bottom)
        calcLevels.sort((a, b) => b.price - a.price);

        elements.tableBody.innerHTML = calcLevels.map(lvl => {
            const isXAU = state.currency === 'XAU' || state.currency === 'NAS' || state.currency === 'SPX' || state.currency === 'BTC';
            const pipSize = isXAU ? 1.0 : 0.0001;
            const distPips = (lvl.price - adaptedSpot) / pipSize;
            let distHtml = '';
            const unit = (state.currency === 'XAU' || state.currency === 'BTC') ? ' $' : ' п.';
            
            if (distPips > 0) {
                distHtml = `<span class="value-green">+${distPips.toFixed(1)}${unit}</span>`;
            } else if (distPips < 0) {
                distHtml = `<span class="value-red">${distPips.toFixed(1)}${unit}</span>`;
            } else {
                distHtml = `<span style="color: var(--text-muted);">0.0${unit} (Спот)</span>`;
            }

            const isSpotRow = lvl.price === adaptedSpot;
            const rowHighlightClass = isSpotRow ? 'strike-spot' : (lvl.badgeText.includes('Call') ? 'strike-spot' : (lvl.badgeText.includes('Put') ? 'strike-max-gamma' : ''));

            return `
                <tr class="${isSpotRow ? 'strike-spot' : ''}">
                    <td style="font-weight: 700;">${lvl.name}</td>
                    <td>${isXAU ? lvl.baseStrike.toFixed(2) : lvl.baseStrike.toFixed(4)}</td>
                    <td style="font-family: monospace; color: var(--text-secondary);">${lvl.formula}</td>
                    <td style="font-weight: 800; font-size: 14px;" class="value-cyan">${isXAU ? lvl.price.toFixed(2) : lvl.price.toFixed(5)}</td>
                    <td style="font-weight: 600;">${distHtml}</td>
                    <td style="font-weight: 600; color: var(--accent-gold);">${lvl.oi}</td>
                    <td><span class="level-badge ${lvl.badge}">${lvl.badgeText}</span></td>
                </tr>
            `;
        }).join('');

    } else if (state.activeTab === 'key-strikes') {
        // Show search box for key strikes list
        elements.searchBoxWrapper.style.display = 'flex';
        
        // Render Headers for Key Strikes
        elements.tableHead.innerHTML = `
            <tr>
                <th>Страйк</th>
                <th>Чистый GEX</th>
                <th>Абс. Гамма</th>
                <th>Дн. Call Клиринг</th>
                <th>Дн. Call ОИ</th>
                <th>Дн. Put Клиринг</th>
                <th>Дн. Put ОИ</th>
                <th>Глоб. Call ОИ</th>
                <th>Глоб. Put ОИ</th>
                <th>Статус уровня</th>
            </tr>
        `;

        // Sort levels descending by strike
        const sortedLevels = [...levels].sort((a, b) => b.strike - a.strike);
        
        // Find closest strike to spot
        let closestStrike = null;
        let minDiff = Infinity;
        sortedLevels.forEach(l => {
            const diff = Math.abs((l.strike + offset) - adaptedSpot);
            if (diff < minDiff) {
                minDiff = diff;
                closestStrike = l.strike;
            }
        });

        // Find closest strike to Zero Gamma
        let closestZeroGammaStrike = null;
        let minZeroDiff = Infinity;
        if (state.zeroGamma) {
            sortedLevels.forEach(l => {
                const diff = Math.abs(l.strike - state.zeroGamma);
                if (diff < minZeroDiff) {
                    minZeroDiff = diff;
                    closestZeroGammaStrike = l.strike;
                }
            });
        }
        
        const rowsHtml = sortedLevels.map(l => {
            let rowClass = '';
            let badgeHtml = '';
            
            if (l.strike === closestStrike) {
                rowClass = 'strike-spot';
                badgeHtml += '<span class="level-badge badge-bg-cyan">Спот ATM</span> ';
            }
            if (state.zeroGamma && l.strike === closestZeroGammaStrike) {
                rowClass = 'strike-zero-gamma';
                badgeHtml += '<span class="level-badge badge-bg-gold">Zero Gamma</span> ';
            }
            if (l.strike === state.maxGammaStrike) {
                rowClass = 'strike-max-gamma';
                badgeHtml += '<span class="level-badge badge-bg-purple">Макс. Гамма</span> ';
            }
            
            if (l.daily_call_oi > 0) {
                badgeHtml += '<span class="level-badge badge-bg-green">Дн. Call</span> ';
            }
            if (l.daily_put_oi > 0) {
                badgeHtml += '<span class="level-badge badge-bg-red">Дн. Put</span> ';
            }
            if (l.global_call_oi > 0) {
                badgeHtml += '<span class="level-badge badge-bg-green">Глоб. Call</span> ';
            }
            if (l.global_put_oi > 0) {
                badgeHtml += '<span class="level-badge badge-bg-red">Глоб. Put</span> ';
            }
            
            // Filter key strikes: must have at least one badge
            if (badgeHtml === '') return '';
            
            const isXAU = state.currency === 'XAU' || state.currency === 'NAS' || state.currency === 'SPX' || state.currency === 'BTC';
            
            // Match Search filter
            const matchesSearch = state.search === '' || (isXAU ? (l.strike + offset).toFixed(2) : (l.strike + offset).toFixed(4)).includes(state.search);
            if (!matchesSearch) return '';
            
            return `
                <tr class="${rowClass}">
                    <td style="font-weight: 700;">${isXAU ? (l.strike + offset).toFixed(2) : (l.strike + offset).toFixed(4)}</td>
                    <td style="font-weight: 600;" class="${l.gex >= 0 ? 'value-green' : 'value-red'}">${formatGEX(l.gex)}</td>
                    <td style="font-weight: 600;" class="value-gold">${formatGamma(l.gamma)}</td>
                    <td>${l.daily_call_settle > 0 ? (isXAU ? l.daily_call_settle.toFixed(2) : l.daily_call_settle.toFixed(5)) : (isXAU ? '0.00' : '0.0')}</td>
                    <td style="color: var(--accent-green); font-weight: 600;">${l.daily_call_oi > 0 ? l.daily_call_oi.toLocaleString() : '-'}</td>
                    <td>${l.daily_put_settle > 0 ? (isXAU ? l.daily_put_settle.toFixed(2) : l.daily_put_settle.toFixed(5)) : (isXAU ? '0.00' : '0.0')}</td>
                    <td style="color: var(--accent-red); font-weight: 600;">${l.daily_put_oi > 0 ? l.daily_put_oi.toLocaleString() : '-'}</td>
                    <td style="color: var(--accent-green);">${l.global_call_oi > 0 ? l.global_call_oi.toLocaleString() : '-'}</td>
                    <td style="color: var(--accent-red);">${l.global_put_oi > 0 ? l.global_put_oi.toLocaleString() : '-'}</td>
                    <td>${badgeHtml}</td>
                </tr>
            `;
        }).join('');
        
        if (rowsHtml === '') {
            elements.tableBody.innerHTML = `<tr><td colspan="10" class="text-center text-muted">Нет уровней, соответствующих поиску.</td></tr>`;
        } else {
            elements.tableBody.innerHTML = rowsHtml;
        }
    }
}

// Chart.js Custom Annotations Plugin to draw Spot, Zero Gamma & Volatility boundaries on the canvas
const verticalLinePlugin = {
    id: 'verticalLinePlugin',
    afterDraw: (chart) => {
        const { ctx, chartArea: { top, bottom }, scales: { x } } = chart;
        const meta = state.data?.metadata;
        
        if (!meta) return;
        
        const offset = (state.adaptSpot && Number.isFinite(meta.live_offset)) ? meta.live_offset : 0;
        
        // Helper function to draw a vertical line with label
        function drawVertical(strikeValue, color, labelText, lineStyle = []) {
            const xPixel = x.getPixelForValue(strikeValue);
            if (xPixel === undefined || xPixel < chart.chartArea.left || xPixel > chart.chartArea.right) return;
            
            ctx.save();
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.setLineDash(lineStyle);
            
            // Draw Line
            ctx.beginPath();
            ctx.moveTo(xPixel, top);
            ctx.lineTo(xPixel, bottom);
            ctx.stroke();
            
            // Draw Label
            ctx.fillStyle = color;
            ctx.font = 'bold 9px Inter';
            ctx.textAlign = 'center';
            ctx.fillText(labelText, xPixel, top - 8);
            ctx.restore();
        }

        // Draw Spot line
        if (elements.toggleSpot.checked && meta.spot > 0) {
            const isXAU = state.currency === 'XAU' || state.currency === 'NAS' || state.currency === 'SPX' || state.currency === 'BTC';
            const displaySpot = meta.spot + offset;
            const priceStr = isXAU ? displaySpot.toFixed(2) : displaySpot.toFixed(4);
            drawVertical(displaySpot, 'rgba(255, 204, 0, 0.85)', `Price: ${priceStr}`, []);
        }

        // Draw Zero Gamma line
        if (elements.toggleZeroGamma.checked && state.zeroGamma > 0) {
            drawVertical(state.zeroGamma + offset, 'rgba(255, 127, 80, 0.85)', 'ZERO GAMMA', [3, 3]);
        }

        // Draw Volatility ranges
        if (elements.toggleBands.checked) {
            if (meta.r68_high > 0) drawVertical(meta.r68_high + offset, 'rgba(255, 51, 102, 0.6)', 'R68 ВЕРХ', [6, 3]);
            if (meta.r68_low > 0) drawVertical(meta.r68_low + offset, 'rgba(255, 51, 102, 0.6)', 'R68 НИЗ', [6, 3]);
            if (meta.r95_high > 0) drawVertical(meta.r95_high + offset, 'rgba(0, 255, 102, 0.5)', 'R95 ВЕРХ', [6, 3]);
            if (meta.r95_low > 0) drawVertical(meta.r95_low + offset, 'rgba(0, 255, 102, 0.5)', 'R95 НИЗ', [6, 3]);
        }
    }
};

// Render option levels on Chart.js canvas
function renderChart(payload) {
    const ctx = document.getElementById('gexChart').getContext('2d');
    
    // Sort levels ascending by strike for accurate left-to-right plotting
    const sortedData = [...payload.levels].sort((a, b) => a.strike - b.strike);
    
    const spot = payload.metadata.spot;
    const offset = (state.adaptSpot && Number.isFinite(payload.metadata.live_offset)) ? payload.metadata.live_offset : 0;
    
    // Find closest strike to spot
    const closestStrikeRow = sortedData.reduce((prev, curr) => 
        Math.abs(curr.strike - spot) < Math.abs(prev.strike - spot) ? curr : prev
    );
    const closestStrike = closestStrikeRow.strike;
    // Identify active strikes (Spot, Zero Gamma, Max Abs Gamma, Daily levels, Global levels)
    const activeStrikes = sortedData.filter(l => {
        const isKey = l.strike === closestStrike || 
                      l.strike === state.maxGammaStrike || 
                      l.daily_call_oi > 0 || 
                      l.daily_put_oi > 0 || 
                      l.global_call_oi > 0 || 
                      l.global_put_oi > 0;
        return isKey;
    }).map(l => l.strike);
    
    if (state.zeroGamma) {
        activeStrikes.push(state.zeroGamma);
    }
    
    // Compute chart scale bounds to focus on the active price scale (expand X axis zoom)
    let chartMinStrike = sortedData[0].strike;
    let chartMaxStrike = sortedData[sortedData.length - 1].strike;
    
    if (activeStrikes.length > 0) {
        let minActive = Math.min(...activeStrikes);
        let maxActive = Math.max(...activeStrikes);
        
        // If the currency is XAU or NAS, let's limit the range to avoid extremely far global barriers (e.g. 5350 when spot is 4595)
        if (state.currency === 'XAU' || state.currency === 'NAS' || state.currency === 'SPX' || state.currency === 'BTC') {
            const spotPrice = payload.metadata.spot;
            const r95_low = payload.metadata.r95_low || (spotPrice * 0.95);
            const r95_high = payload.metadata.r95_high || (spotPrice * 1.05);
            
            // Constrain minActive and maxActive to be within 1.3x of the R95 range
            const r95_span = r95_high - r95_low;
            minActive = Math.max(minActive, r95_low - r95_span * 0.3);
            maxActive = Math.min(maxActive, r95_high + r95_span * 0.3);
        }
        
        const rangeSpan = maxActive - minActive;
        const padding = Math.max(rangeSpan * 0.15, 0.015);
        
        chartMinStrike = minActive - padding;
        chartMaxStrike = maxActive + padding;
    }
    
    // Calculate noise threshold: based on state.noiseThresholdPercent (slider value)
    const maxGex = Math.max(...sortedData.map(l => Math.abs(l.gex)));
    const maxGamma = Math.max(...sortedData.map(l => Math.abs(l.gamma)));
    const pct = (state.noiseThresholdPercent || 2.0) / 100.0;
    const gexThreshold = maxGex * pct;
    const gammaThreshold = maxGamma * pct;
    
    // Filter dataset to fit the expanded range AND remove noise
    // Keep closestStrike (ATM), state.zeroGamma, state.maxGammaStrike, daily MDD levels or global levels
    const filteredChartData = sortedData.filter(l => 
        l.strike >= chartMinStrike && 
        l.strike <= chartMaxStrike &&
        (Math.abs(l.gex) >= gexThreshold || 
         Math.abs(l.gamma) >= gammaThreshold || 
         l.strike === closestStrike || 
         l.strike === state.zeroGamma || 
         l.strike === state.maxGammaStrike ||
         l.daily_call_oi > 0 ||
         l.daily_put_oi > 0 ||
         l.global_call_oi > 0 ||
         l.global_put_oi > 0)
    );
    
    // Prepare values for filtered dataset
    const gexData = filteredChartData.map(l => ({ x: l.strike + offset, y: l.gex }));
    
    // Client-side contract size lookup
    const contractSizeMap = {
        'GBP': 62500,
        'EUR': 125000,
        'USDCAD': 100000,
        'XAU': 100,
        'NAS': 20,
        'SPX': 50,
        'BTC': 5,
    };
    const contractSize = contractSizeMap[state.currency] || 1;
    
    // Reconstruct Call and Put GEX Waves
    const callGexData = filteredChartData.map(l => ({
        x: l.strike + offset,
        y: Math.max(0, 0.5 * (l.gamma * contractSize + l.gex))
    }));
    const putGexData = filteredChartData.map(l => ({
        x: l.strike + offset,
        y: Math.max(0, 0.5 * (l.gamma * contractSize - l.gex))
    }));
    
    // Update Net GEX Bar colors (Cyan for positive Call, Red for negative Put)
    const gexColors = gexData.map(d => d.y >= 0 ? 'rgba(0, 240, 255, 0.8)' : 'rgba(255, 51, 102, 0.8)');
    const gexBorderColors = gexData.map(d => d.y >= 0 ? '#00f0ff' : '#ff3366');
    
    // Destroy existing chart if it exists
    if (state.chart) {
        state.chart.destroy();
    }
    
    // Create custom canvas gradients for Call and Put waves
    const callGradient = ctx.createLinearGradient(0, 0, 0, 400);
    callGradient.addColorStop(0, 'rgba(37, 99, 235, 0.45)');
    callGradient.addColorStop(1, 'rgba(37, 99, 235, 0.0)');
    
    const putGradient = ctx.createLinearGradient(0, 0, 0, 400);
    putGradient.addColorStop(0, 'rgba(249, 115, 22, 0.45)');
    putGradient.addColorStop(1, 'rgba(249, 115, 22, 0.0)');
    
    const datasets = [];
    
    if (elements.toggleGex.checked) {
        datasets.push({
            type: 'bar',
            label: 'Чистый GEX (на основе Гаммы)',
            data: gexData,
            backgroundColor: gexColors,
            borderColor: gexBorderColors,
            borderWidth: 1.5,
            yAxisID: 'yGex',
            order: 2,
            barPercentage: 0.8
        });
    }
    
    if (elements.toggleGamma.checked) {
        datasets.push({
            type: 'line',
            label: 'Волна Calls',
            data: callGexData,
            borderColor: '#2563eb',
            borderWidth: 2.5,
            backgroundColor: callGradient,
            fill: true,
            tension: 0.4,
            pointRadius: 2.5,
            pointHoverRadius: 6,
            pointBackgroundColor: '#2563eb',
            pointBorderColor: '#0a0e1a',
            yAxisID: 'yGamma',
            order: 1
        });
        
        datasets.push({
            type: 'line',
            label: 'Волна Puts',
            data: putGexData,
            borderColor: '#f97316',
            borderWidth: 2.5,
            backgroundColor: putGradient,
            fill: true,
            tension: 0.4,
            pointRadius: 2.5,
            pointHoverRadius: 6,
            pointBackgroundColor: '#f97316',
            pointBorderColor: '#0a0e1a',
            yAxisID: 'yGamma',
            order: 1
        });
    }
    
    // Setup Chart.js configuration
    state.chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: filteredChartData.map(l => l.strike + offset), // Use raw float values so custom plugin works perfectly
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            animations: false,
            layout: {
                padding: {
                    top: 24,
                    bottom: 8
                }
            },
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    display: false // Using custom HTML legends
                },
                tooltip: {
                    backgroundColor: 'rgba(10, 14, 26, 0.95)',
                    titleColor: '#fff',
                    bodyColor: '#f3f4f6',
                    borderColor: 'rgba(255, 255, 255, 0.15)',
                    borderWidth: 1,
                    padding: 12,
                    titleFont: {
                        family: 'Outfit',
                        size: 13,
                        weight: 'bold'
                    },
                    bodyFont: {
                        family: 'Inter',
                        size: 12
                    },
                    callbacks: {
                        title: function(context) {
                            // Использовать parsed.x для получения точного числового значения страйка из линейной шкалы
                            const isXAU = state.currency === 'XAU' || state.currency === 'NAS' || state.currency === 'SPX' || state.currency === 'BTC';
                            return `Опционный страйк: ${parseFloat(context[0].parsed.x || context[0].label).toFixed(isXAU ? 2 : 4)}`;
                        },
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            // All datasets are formatted in GEX units
                            label += formatGEX(context.parsed.y);
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'linear', // Use linear scale so Spot and bands coordinates map correctly
                    min: chartMinStrike + offset,
                    max: chartMaxStrike + offset,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.03)',
                        tickColor: 'rgba(255, 255, 255, 0.1)'
                    },
                    ticks: {
                        color: '#9ca3af',
                        font: {
                            family: 'Inter',
                            size: 11
                        },
                        callback: function(val) {
                            return val.toFixed((state.currency === 'XAU' || state.currency === 'NAS' || state.currency === 'SPX' || state.currency === 'BTC') ? 2 : 4); // Format x axis strikes
                        }
                    }
                },
                yGex: {
                    type: 'linear',
                    position: 'left',
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#9ca3af',
                        callback: function(val) {
                            return formatGEX(val);
                        }
                    }
                },
                yGamma: {
                    type: 'linear',
                    position: 'right',
                    grid: {
                        drawOnChartArea: false // prevent double horizontal grid lines
                    },
                    ticks: {
                        color: '#9ca3af',
                        callback: function(val) {
                            return formatGEX(val);
                        }
                    }
                }
            }
        },
        plugins: [verticalLinePlugin]
    });
}

// Download PDF CME bulletin in real time
async function triggerCmeUpdate() {
    elements.pipelineModal.classList.add('active');
    elements.modalTerminalLog.textContent = '>> Запуск расчетного конвейера опционных уровней GEX...\n';
    elements.btnCloseModal.disabled = true;
    elements.btnCloseModal.textContent = 'Пожалуйста, подождите...';

    // Set spinner active animation
    elements.btnUpdate.querySelector('i').classList.add('fa-spin');
    
    try {
        const response = await fetch('/api/update', {
            method: 'POST'
        });
        const payload = await response.json();
        
        if (payload.success) {
            elements.modalTerminalLog.textContent += '\n>> Расчет опционных уровней завершен успешно!\n';
            elements.modalTerminalLog.textContent += `Код завершения: ${payload.exit_code}\n`;
            elements.modalTerminalLog.textContent += `Лог вывода:\n${payload.stdout}\n`;
            elements.btnCloseModal.textContent = 'Расчет завершен';
        } else {
            elements.modalTerminalLog.textContent += `\n>> ОШИБКА: Расчетный конвейер завершился со сбоем!\n`;
            elements.modalTerminalLog.textContent += `Код завершения: ${payload.exit_code}\n`;
            elements.modalTerminalLog.textContent += `Ошибки:\n${payload.stderr}\n`;
            elements.modalTerminalLog.textContent += `Логи вывода:\n${payload.stdout}\n`;
            elements.btnCloseModal.textContent = 'Сбой выполнения';
        }
    } catch (e) {
        elements.modalTerminalLog.textContent += `\n>> ИСКЛЮЧЕНИЕ: Сбой запроса к серверу: ${e.message}\n`;
        elements.btnCloseModal.textContent = 'Ошибка сети';
    } finally {
        elements.btnCloseModal.disabled = false;
        elements.btnUpdate.querySelector('i').classList.remove('fa-spin');
        
        // Reload all parameters
        await fetchDates();
        await fetchLevelData();
        await fetchSyncStatus();
    }
}

// Export levels data grid as local CSV file download
function exportCSV() {
    if (!state.data || !state.data.levels) return;
    
    const headers = [
        'Strike', 'Total_GEX', 'Total_Abs_Gamma', 
        'Daily_Call_Settle', 'Daily_Call_OI', 
        'Daily_Put_Settle', 'Daily_Put_OI',
        'Global_Call_OI', 'Global_Put_OI'
    ];
    
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += headers.join(",") + "\n";
    
    const sorted = [...state.data.levels].sort((a, b) => b.strike - a.strike);
    
    sorted.forEach(l => {
        const row = [
            l.strike, l.gex, l.gamma,
            l.daily_call_settle, l.daily_call_oi,
            l.daily_put_settle, l.daily_put_oi,
            l.global_call_oi, l.global_put_oi
        ];
        csvContent += row.join(",") + "\n";
    });
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    const fileCurrency = state.currency.includes('USD') ? state.currency : `${state.currency}USD`;
    link.setAttribute("download", `GEX_${fileCurrency}_${state.date}_Export.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Switch between dashboard widgets view and daily analysis view
function switchView(view) {
    if (view === 'dashboard') {
        elements.metricsGrid.style.display = 'grid';
        elements.chartSection.style.display = 'block';
        elements.tableSection.style.display = 'block';
        elements.analysisViewContainer.style.display = 'none';
    } else if (view === 'analysis') {
        elements.metricsGrid.style.display = 'none';
        elements.chartSection.style.display = 'none';
        elements.tableSection.style.display = 'none';
        elements.analysisViewContainer.style.display = 'block';
        fetchAnalysis();
    }
}

// Fetch GEX Daily Analysis
async function fetchAnalysis() {
    try {
        const response = await fetch('analysis.json?t=' + new Date().getTime());
        if (!response.ok) {
            throw new Error('Analysis file not found');
        }
        state.analysisData = await response.json();
        renderAnalysis();
    } catch (e) {
        console.error('Error fetching analysis:', e);
        elements.analysisContent.innerHTML = `
            <div class="text-center text-muted" style="padding: 40px 0;">
                <i class="fa-solid fa-triangle-exclamation" style="font-size: 48px; margin-bottom: 16px; color: var(--accent-red);"></i>
                <p>Не удалось загрузить файл аналитики (analysis.json).</p>
                <p style="font-size: 13px; margin-top: 8px;">Ошибка: ${e.message}</p>
            </div>
        `;
        elements.analysisUpdatedLabel.innerHTML = `<i class="fa-solid fa-clock"></i> Обновление: Ошибка`;
    }
}

// Render selected analysis tab
function renderAnalysis() {
    if (!state.analysisData) return;
    
    // Check if the currency key exists
    const currencyData = state.analysisData[state.currency];
    if (!currencyData) {
        const currencyLabel = state.currency.includes('USD') ? state.currency : `${state.currency}USD`;
        elements.analysisContent.innerHTML = `
            <div class="text-center text-muted" style="padding: 40px 0;">
                <i class="fa-solid fa-circle-info" style="font-size: 48px; margin-bottom: 16px; color: var(--accent-cyan);"></i>
                <p>Нет аналитических данных для валютной пары ${currencyLabel}.</p>
            </div>
        `;
        elements.analysisUpdatedLabel.innerHTML = `<i class="fa-solid fa-clock"></i> Обновление: Нет данных`;
        return;
    }
    
    // Check if the selected day/weekly tab exists
    const mdContent = currencyData[state.activeAnalysisTab];
    const updatedAt = state.analysisData.updated_at || currencyData.updated_at || 'Неизвестно';
    
    elements.analysisUpdatedLabel.innerHTML = `<i class="fa-solid fa-clock"></i> Последнее обновление: ${updatedAt}`;
    
    if (!mdContent || mdContent.trim() === '') {
        elements.analysisContent.innerHTML = `
            <div class="text-center text-muted" style="padding: 40px 0;">
                <i class="fa-solid fa-robot" style="font-size: 48px; margin-bottom: 16px; color: var(--accent-cyan);"></i>
                <p>Анализ для выбранного периода еще не составлен.</p>
                <p style="font-size: 13px; margin-top: 8px;">Запросите проведение анализа в чате с ИИ-помощником.</p>
            </div>
        `;
    } else {
        // Parse markdown using marked
        try {
            let htmlContent = marked.parse(mdContent);
            
            // Highlight specific GEX/MDD levels if they are mentioned
            htmlContent = htmlContent
                .replace(/Daily Call MDD|Дневной Call MDD|Call MDD/gi, '<span class="mdd-call">$&</span>')
                .replace(/Daily Put MDD|Дневной Put MDD|Put MDD/gi, '<span class="mdd-put">$&</span>')
                .replace(/Zero Gamma|Нулевая Гамма/gi, '<span class="zero-gamma-level">$&</span>')
                .replace(/Max Abs Gamma|Макс. Абс. Гамма|Максимальная Гамма/gi, '<span class="magnet-level">$&</span>');
            
            elements.analysisContent.innerHTML = htmlContent;
        } catch (err) {
            console.error('Error parsing markdown:', err);
            elements.analysisContent.innerHTML = `<p class="value-red">Ошибка парсинга Markdown: ${err.message}</p>`;
        }
    }
}

// Bind event listeners
function bindEvents() {
    // Currency Switcher tabs
    elements.currencyTabs.forEach(tab => {
        tab.addEventListener('click', async () => {
            elements.currencyTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.currency = tab.dataset.currency;
            localStorage.setItem('gex_dashboard_currency', state.currency); // SAVE State
            
            // Set dynamic default noise filter for the selected currency
            state.noiseThresholdPercent = state.currency === 'XAU' ? 5.0 : (state.currency === 'NAS' || state.currency === 'SPX' ? 2.0 : (state.currency === 'BTC' ? 2.0 : 1.0));
            localStorage.setItem('gex_dashboard_noise_filter', state.noiseThresholdPercent);
            if (elements.noiseFilterSlider) {
                elements.noiseFilterSlider.value = state.noiseThresholdPercent;
            }
            if (elements.noiseFilterVal) {
                elements.noiseFilterVal.textContent = state.noiseThresholdPercent.toFixed(1) + '%';
            }
            
            // Reload dates and then levels data
            await fetchDates();
            await fetchLevelData();
            
            // Reload GEX analysis if view is active
            if (state.currentView === 'analysis') {
                await fetchAnalysis();
            }
        });
    });

    // Noise filter slider configuration
    if (elements.noiseFilterSlider) {
        elements.noiseFilterSlider.addEventListener('input', (e) => {
            state.noiseThresholdPercent = parseFloat(e.target.value);
            if (elements.noiseFilterVal) {
                elements.noiseFilterVal.textContent = state.noiseThresholdPercent.toFixed(1) + '%';
            }
            localStorage.setItem('gex_dashboard_noise_filter', state.noiseThresholdPercent);
            if (state.data) {
                renderChart(state.data);
            }
        });
    }
    
    // Select date option
    elements.dateSelect.addEventListener('change', (e) => {
        state.date = e.target.value;
        localStorage.setItem('gex_dashboard_date', state.date); // SAVE State
        fetchLevelData();
    });
    
    // Toggle switches configuration with LocalStorage persistence
    elements.toggleGex.addEventListener('change', (e) => {
        localStorage.setItem('gex_dashboard_show_gex', e.target.checked);
        if (state.data) renderChart(state.data);
    });
    
    elements.toggleGamma.addEventListener('change', (e) => {
        localStorage.setItem('gex_dashboard_show_gamma', e.target.checked);
        if (state.data) renderChart(state.data);
    });
    
    elements.toggleSpot.addEventListener('change', (e) => {
        localStorage.setItem('gex_dashboard_show_spot', e.target.checked);
        if (state.data) renderChart(state.data);
    });
    
    elements.toggleBands.addEventListener('change', (e) => {
        localStorage.setItem('gex_dashboard_show_bands', e.target.checked);
        if (state.data) renderChart(state.data);
    });

    elements.toggleZeroGamma.addEventListener('change', (e) => {
        localStorage.setItem('gex_dashboard_show_zerogamma', e.target.checked);
        if (state.data) renderChart(state.data);
    });

    elements.toggleAdaptSpot.addEventListener('change', (e) => {
        state.adaptSpot = e.target.checked;
        localStorage.setItem('gex_dashboard_adapt_spot', e.target.checked);
        if (state.data) {
            updateMetrics(state.data);
            renderTable(state.data.levels, state.data.metadata.spot);
            renderChart(state.data);
        }
    });
    
    // Action Buttons triggers
    elements.btnUpdate.addEventListener('click', triggerCmeUpdate);
    elements.btnExport.addEventListener('click', exportCSV);
    elements.btnRefresh.addEventListener('click', async () => {
        elements.btnRefresh.querySelector('i').classList.add('fa-spin');
        await fetchLevelData();
        await fetchSyncStatus();
        if (state.currentView === 'analysis') {
            await fetchAnalysis();
        }
        setTimeout(() => {
            elements.btnRefresh.querySelector('i').classList.remove('fa-spin');
        }, 600);
    });
    
    // Table filter category buttons
    elements.filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeTab = btn.dataset.tab;
            if (state.data) renderTable(state.data.levels, state.data.metadata.spot);
        });
    });
    
    // Search Box query
    elements.tableSearch.addEventListener('input', (e) => {
        state.search = e.target.value.trim();
        if (state.data) renderTable(state.data.levels, state.data.metadata.spot);
    });
    
    // Close modal pipeline
    elements.btnCloseModal.addEventListener('click', () => {
        elements.pipelineModal.classList.remove('active');
    });

    // Navigation Menu buttons click
    elements.navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.currentView = btn.dataset.view;
            localStorage.setItem('gex_dashboard_view', state.currentView);
            switchView(state.currentView);
        });
    });

    // Analysis day-tabs click
    elements.analysisTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            elements.analysisTabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeAnalysisTab = btn.dataset.day;
            localStorage.setItem('gex_dashboard_analysis_tab', state.activeAnalysisTab);
            renderAnalysis();
        });
    });
}

// Start app initialization sequence
async function init() {
    startClock();
    loadSavedState(); // LOAD settings from LocalStorage
    bindEvents();
    
    // Apply current active view
    switchView(state.currentView);
    
    // Chain API load sequence
    await fetchDates();
    await fetchLevelData();
    await fetchSyncStatus();
}

window.addEventListener('DOMContentLoaded', init);
