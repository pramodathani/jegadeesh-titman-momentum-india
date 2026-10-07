'use strict';

class MonthArithmetic {
  static toNumber(monthText) {
    const year = Number(monthText.slice(0, 4));
    const month = Number(monthText.slice(5, 7));
    return year * 12 + month - 1;
  }

  static fromNumber(monthNumber) {
    const year = Math.floor(monthNumber / 12);
    const month = (monthNumber % 12) + 1;
    return `${year}-${String(month).padStart(2, '0')}`;
  }

  static shift(monthText, months) {
    return MonthArithmetic.fromNumber(MonthArithmetic.toNumber(monthText) + months);
  }

  static label(monthText) {
    const names = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    return `${names[Number(monthText.slice(5, 7)) - 1]} ${monthText.slice(0, 4)}`;
  }
}

class DataStore {
  constructor(basePath) {
    this.basePath = basePath;
    this.cache = new Map();
  }

  async json(relativePath) {
    if (!this.cache.has(relativePath)) {
      const request = fetch(this.basePath + relativePath).then((response) => {
        if (!response.ok) {
          throw new Error(`Could not load ${relativePath}: HTTP ${response.status}`);
        }
        return response.json();
      });
      this.cache.set(relativePath, request);
    }
    return this.cache.get(relativePath);
  }

  meta() {
    return this.json('meta.json');
  }

  returns() {
    return this.json('returns.json');
  }

  stats() {
    return this.json('stats.json');
  }

  cohorts(universe, rankingMonths, skippedDays) {
    return this.json(`cohorts/${universe}_j${rankingMonths}_skip${skippedDays}.json`);
  }
}

class PortfolioBook {
  constructor(cohortDocument, holdingMonths) {
    this.cohortDocument = cohortDocument;
    this.holdingMonths = holdingMonths;
    this.positionByMonth = new Map();
    cohortDocument.months.forEach((month, position) => {
      this.positionByMonth.set(month, position);
    });
    this.holdingsCache = new Map();
  }

  holdingsAt(holdingMonth) {
    if (this.holdingsCache.has(holdingMonth)) {
      return this.holdingsCache.get(holdingMonth);
    }
    const holdings = new Map();
    let complete = true;
    for (let lag = this.holdingMonths; lag >= 1; lag -= 1) {
      const formationMonth = MonthArithmetic.shift(holdingMonth, -lag);
      const position = this.positionByMonth.get(formationMonth);
      if (position === undefined) {
        complete = false;
        break;
      }
      const members = this.cohortDocument.members[position];
      const weightEach = 1 / this.holdingMonths / members.length;
      for (const member of members) {
        const symbolNumber = member[0];
        const holding = holdings.get(symbolNumber) || {
          weight: 0,
          cohorts: 0,
        };
        holding.weight += weightEach;
        holding.cohorts += 1;
        holding.rankingReturn = member[1];
        holding.tradedValue = member[2];
        holding.tercile = member[3];
        holding.lastRanked = formationMonth;
        holdings.set(symbolNumber, holding);
      }
    }
    const result = complete ? holdings : null;
    this.holdingsCache.set(holdingMonth, result);
    return result;
  }

  availableHoldingMonths() {
    const months = [];
    const first = MonthArithmetic.shift(this.cohortDocument.months[0], this.holdingMonths);
    const last = MonthArithmetic.shift(this.cohortDocument.months[this.cohortDocument.months.length - 1], 1);
    for (let number = MonthArithmetic.toNumber(first); number <= MonthArithmetic.toNumber(last); number += 1) {
      const month = MonthArithmetic.fromNumber(number);
      if (this.holdingsAt(month) !== null) {
        months.push(month);
      }
    }
    return months;
  }

  latestHoldingMonth() {
    const months = this.cohortDocument.months;
    return MonthArithmetic.shift(months[months.length - 1], 1);
  }

  monthsHeld(symbolNumber, holdingMonth) {
    let count = 0;
    let month = holdingMonth;
    while (true) {
      const holdings = this.holdingsAt(month);
      if (holdings === null || !holdings.has(symbolNumber)) {
        break;
      }
      count += 1;
      month = MonthArithmetic.shift(month, -1);
    }
    return count;
  }

  symbolsEverHeld() {
    const symbols = new Set();
    for (const members of this.cohortDocument.members) {
      for (const member of members) {
        symbols.add(member[0]);
      }
    }
    return symbols;
  }
}

class Statistics {
  static mean(values) {
    let total = 0;
    for (const value of values) {
      total += value;
    }
    return total / values.length;
  }

  static standardDeviation(values) {
    const average = Statistics.mean(values);
    let total = 0;
    for (const value of values) {
      total += (value - average) ** 2;
    }
    return Math.sqrt(total / (values.length - 1));
  }

  static compoundAnnual(returns) {
    let wealth = 1;
    for (const value of returns) {
      wealth *= 1 + value;
    }
    return wealth ** (12 / returns.length) - 1;
  }

  static wealth(returns) {
    const path = [];
    let wealth = 1;
    for (const value of returns) {
      wealth *= 1 + value;
      path.push(wealth);
    }
    return path;
  }

  static drawdowns(returns) {
    const path = Statistics.wealth(returns);
    const result = [];
    let peak = 1;
    for (const value of path) {
      peak = Math.max(peak, value);
      result.push(value / peak - 1);
    }
    return result;
  }

  static regression(dependent, explanatory) {
    const meanY = Statistics.mean(dependent);
    const meanX = Statistics.mean(explanatory);
    let covariance = 0;
    let varianceX = 0;
    for (let index = 0; index < dependent.length; index += 1) {
      covariance += (explanatory[index] - meanX) * (dependent[index] - meanY);
      varianceX += (explanatory[index] - meanX) ** 2;
    }
    const beta = covariance / varianceX;
    const alpha = meanY - beta * meanX;
    let residualSquares = 0;
    let totalSquares = 0;
    for (let index = 0; index < dependent.length; index += 1) {
      const residual = dependent[index] - alpha - beta * explanatory[index];
      residualSquares += residual ** 2;
      totalSquares += (dependent[index] - meanY) ** 2;
    }
    const count = dependent.length;
    const residualVariance = residualSquares / (count - 2);
    const alphaError = Math.sqrt(residualVariance * (1 / count + meanX ** 2 / varianceX));
    return {
      alpha: alpha,
      beta: beta,
      alphaT: alpha / alphaError,
      rSquared: 1 - residualSquares / totalSquares,
    };
  }
}

class Format {
  static percent(value, decimals = 1, signed = false) {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return '—';
    }
    const text = (value * 100).toFixed(decimals);
    if (signed && value > 0) {
      return `+${text}%`;
    }
    return `${text.replace('-', '−')}%`;
  }

  static number(value, decimals = 2) {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return '—';
    }
    return value.toFixed(decimals).replace('-', '−');
  }

  static escape(text) {
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
}

class Theme {
  read(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  colours() {
    return {
      ink: this.read('--ink'),
      inkSecondary: this.read('--ink-secondary'),
      inkMuted: this.read('--ink-muted'),
      hairline: this.read('--hairline'),
      baseline: this.read('--baseline'),
      surface: this.read('--surface'),
      series: [
        this.read('--series-1'),
        this.read('--series-2'),
        this.read('--series-3'),
      ],
      diverging: [
        this.read('--diverging-negative-strong'),
        this.read('--diverging-negative'),
        this.read('--diverging-neutral'),
        this.read('--diverging-positive'),
        this.read('--diverging-positive-strong'),
      ],
      serif: this.read('--serif'),
    };
  }
}

class ChartRegistry {
  constructor(theme) {
    this.theme = theme;
    this.charts = new Map();
    window.addEventListener('resize', () => {
      for (const chart of this.charts.values()) {
        chart.resize();
      }
    });
  }

  chart(elementId) {
    if (!this.charts.has(elementId)) {
      const element = document.getElementById(elementId);
      this.charts.set(elementId, echarts.init(element, null, {
        renderer: 'svg',
      }));
    }
    return this.charts.get(elementId);
  }

  base() {
    const colours = this.theme.colours();
    return {
      colours: colours,
      textStyle: {
        fontFamily: colours.serif,
        color: colours.inkSecondary,
        fontSize: 12,
      },
      axisLine: {
        lineStyle: {
          color: colours.baseline,
        },
      },
      splitLine: {
        lineStyle: {
          color: colours.hairline,
        },
      },
      tooltip: {
        backgroundColor: colours.surface,
        borderColor: colours.baseline,
        textStyle: {
          color: colours.ink,
          fontFamily: colours.serif,
          fontSize: 12,
        },
        confine: true,
      },
    };
  }
}

class CompanionApp {
  constructor() {
    this.store = new DataStore('data/');
    this.theme = new Theme();
    this.registry = new ChartRegistry(this.theme);
    this.specification = {
      rankingMonths: 9,
      holdingMonths: 3,
      skippedDays: 0,
      universe: 'top500',
    };
  }

  async start() {
    this.meta = await this.store.meta();
    this.returns = await this.store.returns();
    this.stats = await this.store.stats();
    this.statsByName = new Map();
    for (const row of this.stats) {
      this.statsByName.set(row.strategy, row);
    }
    document.getElementById('data-through').textContent = MonthArithmetic.label(this.meta.latest_formation_month);
    document.getElementById('generated').textContent = this.meta.generated;
    this.fillAbstract();
    this.fillControls();
    this.readHash();
    this.attachListeners();
    await this.render();
  }

  fillAbstract() {
    const best = this.statsByName.get('jt-momentum-j9-k3-skip0-top500');
    document.getElementById('abstract-best-return').textContent = Format.percent(best.compound_annual);
    document.getElementById('abstract-benchmark-return').textContent = Format.percent(best.benchmark_compound_annual);
  }

  fillControls() {
    const ranking = document.getElementById('control-ranking');
    for (const months of this.meta.ranking_months) {
      ranking.add(new Option(`${months} months`, String(months)));
    }
    const holding = document.getElementById('control-holding');
    for (const months of this.meta.holding_months) {
      holding.add(new Option(`${months} months`, String(months)));
    }
  }

  strategyName() {
    const specification = this.specification;
    return `jt-momentum-j${specification.rankingMonths}-k${specification.holdingMonths}-skip${specification.skippedDays}-${specification.universe}`;
  }

  readHash() {
    const match = window.location.hash.match(/^#j(\d+)-k(\d+)-skip(\d+)-(top500|all)$/);
    if (match) {
      this.specification = {
        rankingMonths: Number(match[1]),
        holdingMonths: Number(match[2]),
        skippedDays: Number(match[3]),
        universe: match[4],
      };
    }
    document.getElementById('control-ranking').value = String(this.specification.rankingMonths);
    document.getElementById('control-holding').value = String(this.specification.holdingMonths);
    document.getElementById('control-gap').value = String(this.specification.skippedDays);
    document.getElementById('control-universe').value = this.specification.universe;
  }

  attachListeners() {
    const controlIds = [
      'control-ranking',
      'control-holding',
      'control-gap',
      'control-universe',
    ];
    for (const controlId of controlIds) {
      document.getElementById(controlId).addEventListener('change', () => this.onSpecificationChange());
    }
    document.getElementById('control-change-month').addEventListener('change', () => this.renderChanges());
    document.getElementById('control-history-month').addEventListener('input', () => this.renderHistory());
    document.getElementById('control-share').addEventListener('change', () => this.renderShare());
    document.getElementById('download-current').addEventListener('click', () => this.downloadCurrent());
  }

  async onSpecificationChange() {
    this.specification = {
      rankingMonths: Number(document.getElementById('control-ranking').value),
      holdingMonths: Number(document.getElementById('control-holding').value),
      skippedDays: Number(document.getElementById('control-gap').value),
      universe: document.getElementById('control-universe').value,
    };
    history.replaceState(null, '', `#j${this.specification.rankingMonths}-k${this.specification.holdingMonths}-skip${this.specification.skippedDays}-${this.specification.universe}`);
    await this.render();
  }

  async render() {
    document.getElementById('specification-summary').textContent = 'Loading…';
    const cohorts = await this.store.cohorts(this.specification.universe, this.specification.rankingMonths, this.specification.skippedDays);
    this.book = new PortfolioBook(cohorts, this.specification.holdingMonths);
    this.holdingMonthList = this.book.availableHoldingMonths();
    this.prepareSeries();
    this.renderSpecificationSummary();
    this.renderPerformance();
    this.renderCurrent();
    this.renderChangeMonths();
    this.renderChanges();
    this.renderHistoryControl();
    this.renderHistory();
    this.renderShareList();
    this.renderShare();
    this.renderCrossSection();
    this.renderAnalytics();
  }

  prepareSeries() {
    const strategy = this.returns.strategies[this.strategyName()];
    const commonStart = this.statsByName.get(this.strategyName()).first_month;
    const months = [];
    const portfolio = [];
    const benchmark = [];
    const gross = [];
    const turnover = [];
    this.returns.months.forEach((month, index) => {
      const value = strategy.net[index];
      const benchmarkValue = this.returns.benchmark[index];
      if (value !== null && benchmarkValue !== null && month >= commonStart) {
        months.push(month);
        portfolio.push(value);
        benchmark.push(benchmarkValue);
        gross.push(strategy.gross[index]);
        turnover.push(strategy.turnover[index]);
      }
    });
    this.series = {
      months: months,
      portfolio: portfolio,
      benchmark: benchmark,
      gross: gross,
      turnover: turnover,
    };
  }

  universeLabel() {
    return this.specification.universe === 'top500' ? 'the 500 most-traded NSE shares' : 'all NSE shares';
  }

  renderSpecificationSummary() {
    const specification = this.specification;
    const row = this.statsByName.get(this.strategyName());
    const gap = specification.skippedDays === 0 ? 'no gap' : 'a one-week gap';
    document.getElementById('specification-summary').innerHTML = `Rank ${this.universeLabel()} on their past ${specification.rankingMonths}-month return, hold the top decile for ${specification.holdingMonths} months, ${gap}. Over the common sample: ${Format.percent(row.compound_annual)} a year, ${Format.percent(row.excess_annual, 1, true)} a year above the NIFTY 500 (<i>t</i> = ${Format.number(row.excess_t)}).`;
  }

  renderPerformance() {
    const base = this.registry.base();
    const colours = base.colours;
    const months = this.series.months;
    const portfolioWealth = Statistics.wealth(this.series.portfolio);
    const benchmarkWealth = Statistics.wealth(this.series.benchmark);
    const labels = months.map((month) => MonthArithmetic.label(month));
    const lineSeries = (name, data, colour) => ({
      name: name,
      type: 'line',
      data: data,
      showSymbol: false,
      lineStyle: {
        width: 2,
        color: colour,
      },
      itemStyle: {
        color: colour,
      },
    });
    const axisBase = {
      axisLine: base.axisLine,
      axisLabel: {
        color: colours.inkMuted,
        fontFamily: colours.serif,
      },
      splitLine: base.splitLine,
    };
    this.registry.chart('figure-growth').setOption({
      textStyle: base.textStyle,
      grid: {
        left: 56,
        right: 24,
        top: 40,
        bottom: 32,
      },
      legend: {
        top: 0,
        itemGap: 28,
        textStyle: base.textStyle,
      },
      tooltip: {
        ...base.tooltip,
        trigger: 'axis',
        valueFormatter: (value) => `₹${value.toFixed(2)}`,
      },
      xAxis: {
        ...axisBase,
        type: 'category',
        data: labels,
        boundaryGap: false,
        splitLine: {
          show: false,
        },
      },
      yAxis: {
        ...axisBase,
        type: 'log',
        logBase: 2,
        axisLabel: {
          ...axisBase.axisLabel,
          formatter: (value) => `₹${value}`,
        },
      },
      series: [
        lineSeries('Portfolio, after costs', portfolioWealth, colours.series[0]),
        lineSeries('NIFTY 500 with dividends', benchmarkWealth, colours.series[1]),
      ],
    }, true);
    this.registry.chart('figure-drawdown').setOption({
      textStyle: base.textStyle,
      grid: {
        left: 56,
        right: 24,
        top: 36,
        bottom: 32,
      },
      legend: {
        top: 0,
        itemGap: 28,
        textStyle: base.textStyle,
      },
      tooltip: {
        ...base.tooltip,
        trigger: 'axis',
        valueFormatter: (value) => Format.percent(value),
      },
      xAxis: {
        ...axisBase,
        type: 'category',
        data: labels,
        boundaryGap: false,
        splitLine: {
          show: false,
        },
      },
      yAxis: {
        ...axisBase,
        type: 'value',
        max: 0,
        axisLabel: {
          ...axisBase.axisLabel,
          formatter: (value) => Format.percent(value, 0),
        },
      },
      series: [
        lineSeries('Portfolio', Statistics.drawdowns(this.series.portfolio), colours.series[0]),
        lineSeries('NIFTY 500', Statistics.drawdowns(this.series.benchmark), colours.series[1]),
      ],
    }, true);
    this.renderSummaryTable();
    this.renderCalendar(base);
    this.renderRolling(base, labels, axisBase);
  }

  renderSummaryTable() {
    const portfolio = this.series.portfolio;
    const benchmark = this.series.benchmark;
    const excess = portfolio.map((value, index) => value - benchmark[index]);
    const excessT = Statistics.mean(excess) / (Statistics.standardDeviation(excess) / Math.sqrt(excess.length));
    const rows = [
      [
        'Compound annual return',
        Format.percent(Statistics.compoundAnnual(portfolio)),
        Format.percent(Statistics.compoundAnnual(benchmark)),
      ],
      [
        'Annual volatility',
        Format.percent(Statistics.standardDeviation(portfolio) * Math.sqrt(12)),
        Format.percent(Statistics.standardDeviation(benchmark) * Math.sqrt(12)),
      ],
      [
        'Sharpe ratio, no risk-free rate',
        Format.number(Statistics.mean(portfolio) / Statistics.standardDeviation(portfolio) * Math.sqrt(12)),
        Format.number(Statistics.mean(benchmark) / Statistics.standardDeviation(benchmark) * Math.sqrt(12)),
      ],
      [
        'Maximum drawdown',
        Format.percent(Math.min(...Statistics.drawdowns(portfolio))),
        Format.percent(Math.min(...Statistics.drawdowns(benchmark))),
      ],
      [
        'Best month',
        Format.percent(Math.max(...portfolio)),
        Format.percent(Math.max(...benchmark)),
      ],
      [
        'Worst month',
        Format.percent(Math.min(...portfolio)),
        Format.percent(Math.min(...benchmark)),
      ],
      [
        'Annual return above the index',
        Format.percent(Statistics.compoundAnnual(portfolio) - Statistics.compoundAnnual(benchmark), 1, true),
        '',
      ],
      [
        '<i>t</i>-statistic of the monthly difference',
        Format.number(excessT),
        '',
      ],
      [
        'Months beating the index',
        Format.percent(excess.filter((value) => value > 0).length / excess.length, 0),
        '',
      ],
    ];
    const body = rows.map((row) => `<tr><td class="text">${row[0]}</td><td>${row[1]}</td><td>${row[2]}</td></tr>`).join('');
    const first = MonthArithmetic.label(this.series.months[0]);
    const last = MonthArithmetic.label(this.series.months[this.series.months.length - 1]);
    document.getElementById('table-summary').innerHTML = `<caption><b>Table 1.</b> Summary statistics of monthly returns, ${first} to ${last} (${this.series.months.length} months). The portfolio is measured after Indian trading costs; the index includes dividends.</caption><thead><tr><th class="text"></th><th>Portfolio</th><th>NIFTY 500</th></tr></thead><tbody>${body}</tbody>`;
  }

  renderCalendar(base) {
    const colours = base.colours;
    const years = [];
    const data = [];
    let largest = 0;
    this.series.months.forEach((month, index) => {
      const year = month.slice(0, 4);
      if (!years.includes(year)) {
        years.push(year);
      }
      const value = this.series.portfolio[index] - this.series.benchmark[index];
      largest = Math.max(largest, Math.abs(value));
      data.push([Number(month.slice(5, 7)) - 1, years.indexOf(year), value]);
    });
    const bound = Math.min(largest, 0.15);
    this.registry.chart('figure-calendar').setOption({
      textStyle: base.textStyle,
      grid: {
        left: 48,
        right: 16,
        top: 8,
        bottom: 64,
      },
      tooltip: {
        ...base.tooltip,
        formatter: (parameters) => {
          const monthText = `${years[parameters.value[1]]}-${String(parameters.value[0] + 1).padStart(2, '0')}`;
          return `${MonthArithmetic.label(monthText)}: ${Format.percent(parameters.value[2], 1, true)} versus the index`;
        },
      },
      xAxis: {
        type: 'category',
        data: [
          'Jan',
          'Feb',
          'Mar',
          'Apr',
          'May',
          'Jun',
          'Jul',
          'Aug',
          'Sep',
          'Oct',
          'Nov',
          'Dec',
        ],
        axisLine: base.axisLine,
        axisLabel: {
          color: colours.inkMuted,
        },
        splitArea: {
          show: false,
        },
      },
      yAxis: {
        type: 'category',
        data: years,
        inverse: true,
        axisLine: base.axisLine,
        axisLabel: {
          color: colours.inkMuted,
        },
      },
      visualMap: {
        min: -bound,
        max: bound,
        calculable: false,
        orient: 'horizontal',
        left: 'center',
        bottom: 4,
        itemHeight: 160,
        text: [
          `${Format.percent(bound, 0, true)}`,
          `${Format.percent(-bound, 0)}`,
        ],
        textStyle: base.textStyle,
        inRange: {
          color: colours.diverging,
        },
      },
      series: [
        {
          type: 'heatmap',
          data: data,
          itemStyle: {
            borderColor: colours.surface,
            borderWidth: 2,
          },
        },
      ],
    }, true);
  }

  renderRolling(base, labels, axisBase) {
    const colours = base.colours;
    const windowMonths = 36;
    const values = [];
    for (let index = 0; index < this.series.portfolio.length; index += 1) {
      if (index < windowMonths - 1) {
        values.push(null);
        continue;
      }
      const portfolio = this.series.portfolio.slice(index - windowMonths + 1, index + 1);
      const benchmark = this.series.benchmark.slice(index - windowMonths + 1, index + 1);
      values.push(Statistics.compoundAnnual(portfolio) - Statistics.compoundAnnual(benchmark));
    }
    this.registry.chart('figure-rolling').setOption({
      textStyle: base.textStyle,
      grid: {
        left: 56,
        right: 24,
        top: 16,
        bottom: 32,
      },
      tooltip: {
        ...base.tooltip,
        trigger: 'axis',
        valueFormatter: (value) => (value === null ? '—' : Format.percent(value, 1, true)),
      },
      xAxis: {
        ...axisBase,
        type: 'category',
        data: labels,
        boundaryGap: false,
        splitLine: {
          show: false,
        },
      },
      yAxis: {
        ...axisBase,
        type: 'value',
        axisLabel: {
          ...axisBase.axisLabel,
          formatter: (value) => Format.percent(value, 0),
        },
      },
      series: [
        {
          name: '36-month return above the index',
          type: 'line',
          data: values,
          showSymbol: false,
          lineStyle: {
            width: 2,
            color: colours.series[0],
          },
          itemStyle: {
            color: colours.series[0],
          },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: {
              color: colours.baseline,
              type: 'solid',
            },
            label: {
              show: false,
            },
            data: [
              {
                yAxis: 0,
              },
            ],
          },
        },
      ],
    }, true);
  }

  holdingRows(holdingMonth) {
    const holdings = this.book.holdingsAt(holdingMonth);
    const rows = [];
    for (const [symbolNumber, holding] of holdings.entries()) {
      rows.push({
        symbol: this.meta.symbols[symbolNumber],
        symbolNumber: symbolNumber,
        ...holding,
      });
    }
    rows.sort((left, right) => right.weight - left.weight || right.rankingReturn - left.rankingReturn);
    return rows;
  }

  holdingTable(rows, holdingMonth, caption) {
    const tercileNames = {
      1: 'least',
      2: 'middle',
      3: 'most',
    };
    const body = rows.map((row, index) => `<tr><td>${index + 1}</td><td class="symbol">${Format.escape(row.symbol)}</td><td>${Format.percent(row.weight, 2)}</td><td>${row.cohorts}</td><td>${this.book.monthsHeld(row.symbolNumber, holdingMonth)}</td><td>${Format.percent(row.rankingReturn, 1, true)}</td><td>${Format.number(row.tradedValue, 2)}</td><td class="text">${tercileNames[row.tercile] || '—'}</td></tr>`).join('');
    return `<caption>${caption}</caption><thead><tr><th>#</th><th class="text">Share</th><th>Weight</th><th>Cohorts</th><th>Months held</th><th>${this.specification.rankingMonths}-month return</th><th>Traded, ₹ cr/day</th><th class="text">Liquidity third</th></tr></thead><tbody>${body}</tbody>`;
  }

  renderCurrent() {
    const holdingMonth = this.book.latestHoldingMonth();
    const rows = this.holdingRows(holdingMonth);
    this.currentRows = rows;
    for (const element of document.querySelectorAll('.current-holding-month')) {
      element.textContent = MonthArithmetic.label(holdingMonth);
    }
    const caption = `<b>Table 2.</b> Target portfolio for ${MonthArithmetic.label(holdingMonth)}: ${rows.length} shares from ${this.specification.holdingMonths} cohorts. "${this.specification.rankingMonths}-month return" is the ranking return at the share's most recent cohort; traded value is the median daily value over six months.`;
    document.getElementById('table-current').innerHTML = this.holdingTable(rows, holdingMonth, caption);
    const largest = rows.length > 0 ? rows[0].weight : 0;
    document.getElementById('current-summary').textContent = `${rows.length} shares; largest weight ${Format.percent(largest, 2)}.`;
    document.getElementById('current-summary').classList.remove('loading');
  }

  downloadCurrent() {
    const holdingMonth = this.book.latestHoldingMonth();
    const lines = [
      'rank,symbol,weight,cohorts,months_held,ranking_return,traded_value_crore,liquidity_tercile',
    ];
    this.currentRows.forEach((row, index) => {
      lines.push([
        index + 1,
        row.symbol,
        row.weight.toFixed(6),
        row.cohorts,
        this.book.monthsHeld(row.symbolNumber, holdingMonth),
        row.rankingReturn,
        row.tradedValue,
        row.tercile,
      ].join(','));
    });
    const blob = new Blob([lines.join('\n') + '\n'], {
      type: 'text/csv',
    });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${this.strategyName()}-${holdingMonth}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  renderChangeMonths() {
    const select = document.getElementById('control-change-month');
    select.innerHTML = '';
    for (let index = this.holdingMonthList.length - 1; index >= 1; index -= 1) {
      const month = this.holdingMonthList[index];
      select.add(new Option(MonthArithmetic.label(month), month));
    }
  }

  renderChanges() {
    const month = document.getElementById('control-change-month').value;
    const previousMonth = MonthArithmetic.shift(month, -1);
    const current = this.book.holdingsAt(month);
    const previous = this.book.holdingsAt(previousMonth);
    const joiners = [];
    const leavers = [];
    let stayers = 0;
    for (const [symbolNumber, holding] of current.entries()) {
      if (previous.has(symbolNumber)) {
        stayers += 1;
      } else {
        joiners.push({
          symbol: this.meta.symbols[symbolNumber],
          ...holding,
        });
      }
    }
    for (const [symbolNumber, holding] of previous.entries()) {
      if (!current.has(symbolNumber)) {
        leavers.push({
          symbol: this.meta.symbols[symbolNumber],
          monthsHeld: this.book.monthsHeld(symbolNumber, previousMonth),
          ...holding,
        });
      }
    }
    joiners.sort((left, right) => right.rankingReturn - left.rankingReturn);
    leavers.sort((left, right) => left.symbol.localeCompare(right.symbol));
    const joinerBody = joiners.map((row) => `<tr><td class="symbol">${Format.escape(row.symbol)}</td><td>${Format.percent(row.weight, 2)}</td><td>${Format.percent(row.rankingReturn, 1, true)}</td></tr>`).join('');
    const leaverBody = leavers.map((row) => `<tr><td class="symbol">${Format.escape(row.symbol)}</td><td>${row.monthsHeld}</td><td class="text">${MonthArithmetic.label(row.lastRanked)}</td></tr>`).join('');
    document.getElementById('table-joiners').innerHTML = `<caption><b>Table 3.</b> Joiners in ${MonthArithmetic.label(month)}: shares in the cohort ranked at the end of ${MonthArithmetic.label(previousMonth)} that were not already held.</caption><thead><tr><th class="text">Share</th><th>Weight</th><th>Ranking return</th></tr></thead><tbody>${joinerBody || '<tr><td class="text" colspan="3">None</td></tr>'}</tbody>`;
    document.getElementById('table-leavers').innerHTML = `<caption><b>Table 4.</b> Leavers in ${MonthArithmetic.label(month)}: shares whose last winning cohort expired. "Last ranked" is the last month-end at which the share was a winner.</caption><thead><tr><th class="text">Share</th><th>Months held</th><th class="text">Last ranked</th></tr></thead><tbody>${leaverBody || '<tr><td class="text" colspan="3">None</td></tr>'}</tbody>`;
    document.getElementById('change-summary').textContent = `${joiners.length} joined, ${leavers.length} left, ${stayers} stayed.`;
  }

  renderHistoryControl() {
    const slider = document.getElementById('control-history-month');
    slider.max = String(this.holdingMonthList.length - 1);
    slider.value = String(this.holdingMonthList.length - 1);
  }

  renderHistory() {
    const slider = document.getElementById('control-history-month');
    const month = this.holdingMonthList[Number(slider.value)];
    document.getElementById('history-month-label').textContent = MonthArithmetic.label(month);
    const rows = this.holdingRows(month);
    const caption = `<b>Table 5.</b> The portfolio held in ${MonthArithmetic.label(month)}: ${rows.length} shares. Move the slider to choose any month since ${MonthArithmetic.label(this.holdingMonthList[0])}.`;
    document.getElementById('table-history').innerHTML = this.holdingTable(rows, month, caption);
  }

  renderShareList() {
    const list = document.getElementById('share-list');
    const symbols = [];
    for (const symbolNumber of this.book.symbolsEverHeld()) {
      symbols.push(this.meta.symbols[symbolNumber]);
    }
    symbols.sort();
    list.innerHTML = symbols.map((symbol) => `<option value="${Format.escape(symbol)}">`).join('');
    const input = document.getElementById('control-share');
    if (!input.value && this.currentRows.length > 0) {
      input.value = this.currentRows[0].symbol;
    }
  }

  renderShare() {
    const base = this.registry.base();
    const colours = base.colours;
    const symbol = document.getElementById('control-share').value.trim().toUpperCase();
    const symbolNumber = this.meta.symbols.indexOf(symbol);
    const weights = [];
    let monthsHeld = 0;
    let firstMonth = null;
    let lastMonth = null;
    for (const month of this.holdingMonthList) {
      const holding = symbolNumber >= 0 ? this.book.holdingsAt(month).get(symbolNumber) : undefined;
      const weight = holding ? holding.weight : 0;
      weights.push(weight);
      if (weight > 0) {
        monthsHeld += 1;
        firstMonth = firstMonth || month;
        lastMonth = month;
      }
    }
    const summary = document.getElementById('share-summary');
    if (symbolNumber < 0) {
      summary.textContent = 'Not an NSE symbol in the data.';
    } else if (monthsHeld === 0) {
      summary.textContent = `${symbol} was never held by this portfolio.`;
    } else {
      summary.textContent = `${symbol}: held in ${monthsHeld} of ${this.holdingMonthList.length} months, first in ${MonthArithmetic.label(firstMonth)}, last in ${MonthArithmetic.label(lastMonth)}.`;
    }
    this.registry.chart('figure-share').setOption({
      textStyle: base.textStyle,
      grid: {
        left: 56,
        right: 24,
        top: 16,
        bottom: 32,
      },
      tooltip: {
        ...base.tooltip,
        trigger: 'axis',
        valueFormatter: (value) => Format.percent(value, 2),
      },
      xAxis: {
        type: 'category',
        data: this.holdingMonthList.map((month) => MonthArithmetic.label(month)),
        axisLine: base.axisLine,
        axisLabel: {
          color: colours.inkMuted,
        },
      },
      yAxis: {
        type: 'value',
        axisLine: base.axisLine,
        splitLine: base.splitLine,
        axisLabel: {
          color: colours.inkMuted,
          formatter: (value) => Format.percent(value, 1),
        },
      },
      series: [
        {
          name: `${symbol} weight`,
          type: 'bar',
          data: weights,
          barCategoryGap: '10%',
          itemStyle: {
            color: colours.series[0],
            borderRadius: [
              2,
              2,
              0,
              0,
            ],
          },
        },
      ],
    }, true);
  }

  renderCrossSection() {
    const base = this.registry.base();
    const colours = base.colours;
    const specification = this.specification;
    const ranking = this.meta.ranking_months;
    const holding = this.meta.holding_months;
    const cells = [];
    let largest = 0;
    ranking.forEach((rankingMonths, row) => {
      holding.forEach((holdingMonths, column) => {
        const name = `jt-momentum-j${rankingMonths}-k${holdingMonths}-skip${specification.skippedDays}-${specification.universe}`;
        const value = this.statsByName.get(name).excess_annual;
        largest = Math.max(largest, Math.abs(value));
        cells.push([column, row, value]);
      });
    });
    this.registry.chart('figure-heatmap').setOption({
      textStyle: base.textStyle,
      grid: {
        left: 64,
        right: 16,
        top: 8,
        bottom: 72,
      },
      tooltip: {
        ...base.tooltip,
        formatter: (parameters) => `J = ${ranking[parameters.value[1]]}, K = ${holding[parameters.value[0]]}: ${Format.percent(parameters.value[2], 1, true)} a year`,
      },
      xAxis: {
        type: 'category',
        name: 'Holding period K',
        nameLocation: 'middle',
        nameGap: 28,
        data: holding.map((months) => String(months)),
        axisLine: base.axisLine,
        axisLabel: {
          color: colours.inkMuted,
        },
      },
      yAxis: {
        type: 'category',
        name: 'Ranking period J',
        nameLocation: 'middle',
        nameGap: 40,
        data: ranking.map((months) => String(months)),
        axisLine: base.axisLine,
        axisLabel: {
          color: colours.inkMuted,
        },
      },
      visualMap: {
        min: -largest,
        max: largest,
        show: false,
        inRange: {
          color: colours.diverging,
        },
      },
      series: [
        {
          type: 'heatmap',
          data: cells,
          label: {
            show: true,
            formatter: (parameters) => Format.percent(parameters.value[2], 1, true),
            color: colours.ink,
            fontFamily: colours.serif,
          },
          itemStyle: {
            borderColor: colours.surface,
            borderWidth: 2,
          },
        },
      ],
    }, true);
    const pointsByUniverse = {
      top500: [],
      all: [],
    };
    let selected = null;
    for (const row of this.stats) {
      const strategy = this.meta.strategies.find((item) => item.name === row.strategy);
      const point = {
        value: [row.maximum_drawdown, row.compound_annual],
        name: row.strategy.replace('jt-momentum-', ''),
      };
      pointsByUniverse[strategy.universe].push(point);
      if (row.strategy === this.strategyName()) {
        selected = point;
      }
    }
    const scatterSeries = (name, data, colour) => ({
      name: name,
      type: 'scatter',
      data: data,
      symbolSize: 8,
      itemStyle: {
        color: colour,
        borderColor: colours.surface,
        borderWidth: 1,
      },
    });
    this.registry.chart('figure-scatter').setOption({
      textStyle: base.textStyle,
      grid: {
        left: 56,
        right: 16,
        top: 36,
        bottom: 48,
      },
      legend: {
        top: 0,
        itemGap: 28,
        textStyle: base.textStyle,
      },
      tooltip: {
        ...base.tooltip,
        formatter: (parameters) => `${parameters.name}<br>${Format.percent(parameters.value[1])} a year, worst fall ${Format.percent(parameters.value[0])}`,
      },
      xAxis: {
        type: 'value',
        name: 'Maximum drawdown',
        nameLocation: 'middle',
        nameGap: 28,
        scale: true,
        axisLine: base.axisLine,
        splitLine: base.splitLine,
        axisLabel: {
          color: colours.inkMuted,
          formatter: (value) => Format.percent(value, 0),
        },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLine: base.axisLine,
        splitLine: base.splitLine,
        axisLabel: {
          color: colours.inkMuted,
          formatter: (value) => Format.percent(value, 0),
        },
      },
      series: [
        scatterSeries('500 most traded', pointsByUniverse.top500, colours.series[0]),
        scatterSeries('All shares', pointsByUniverse.all, colours.series[1]),
        {
          name: 'Selected',
          type: 'scatter',
          data: selected ? [selected] : [],
          symbolSize: 18,
          itemStyle: {
            color: 'transparent',
            borderColor: colours.ink,
            borderWidth: 2,
          },
          z: 10,
        },
      ],
    }, true);
    this.renderPaperTable();
  }

  renderPaperTable() {
    const key = `skip${this.specification.skippedDays}`;
    const groups = [
      [
        'Jegadeesh and Titman (1993), NYSE and AMEX, 1965–1989',
        this.meta.paper_table_one[key],
      ],
      [
        `India, 500 most-traded NSE shares, ${this.meta.india_table_one_months}`,
        this.meta.india_table_one.top500[key],
      ],
      [
        `India, all NSE shares, ${this.meta.india_table_one_months}`,
        this.meta.india_table_one.all[key],
      ],
    ];
    let body = '';
    for (const [label, grid] of groups) {
      body += `<tr class="group-start"><td class="text" colspan="5"><i>${label}</i></td></tr>`;
      for (const rankingMonths of this.meta.ranking_months) {
        const cells = grid[String(rankingMonths)].map((cell) => `<td>${Format.percent(cell[0], 2)} (${Format.number(cell[1])})</td>`).join('');
        body += `<tr><td class="text">J = ${rankingMonths}</td>${cells}</tr>`;
      }
    }
    const gapText = this.specification.skippedDays === 0 ? 'without a gap (Panel A)' : 'with a one-week gap (Panel B)';
    document.getElementById('table-paper').innerHTML = `<caption><b>Table 6.</b> The paper's Table I and its Indian counterparts, ${gapText}: average monthly return of buying the top decile and selling the bottom decile, before costs, with <i>t</i>-statistics in brackets.</caption><thead><tr><th class="text"></th><th>K = 3</th><th>K = 6</th><th>K = 9</th><th>K = 12</th></tr></thead><tbody>${body}</tbody>`;
  }

  renderAnalytics() {
    const base = this.registry.base();
    const colours = base.colours;
    const counts = [];
    const effective = [];
    const analysisMonths = this.holdingMonthList.filter((month) => month >= this.series.months[0]);
    for (const month of analysisMonths) {
      const holdings = this.book.holdingsAt(month);
      let squares = 0;
      for (const holding of holdings.values()) {
        squares += holding.weight ** 2;
      }
      counts.push(holdings.size);
      effective.push(1 / squares);
    }
    const labels = analysisMonths.map((month) => MonthArithmetic.label(month));
    const lineSeries = (name, data, colour) => ({
      name: name,
      type: 'line',
      data: data,
      showSymbol: false,
      lineStyle: {
        width: 2,
        color: colour,
      },
      itemStyle: {
        color: colour,
      },
    });
    this.registry.chart('figure-breadth').setOption({
      textStyle: base.textStyle,
      grid: {
        left: 56,
        right: 24,
        top: 36,
        bottom: 32,
      },
      legend: {
        top: 0,
        itemGap: 28,
        textStyle: base.textStyle,
      },
      tooltip: {
        ...base.tooltip,
        trigger: 'axis',
        valueFormatter: (value) => value.toFixed(0),
      },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLine: base.axisLine,
        axisLabel: {
          color: colours.inkMuted,
        },
      },
      yAxis: {
        type: 'value',
        axisLine: base.axisLine,
        splitLine: base.splitLine,
        axisLabel: {
          color: colours.inkMuted,
        },
      },
      series: [
        lineSeries('Shares held', counts, colours.series[0]),
        lineSeries('Effective number of shares', effective, colours.series[1]),
      ],
    }, true);
    const turnover = this.series.turnover;
    const rollingTurnover = [];
    for (let index = 0; index < turnover.length; index += 1) {
      if (index < 11) {
        rollingTurnover.push(null);
        continue;
      }
      let total = 0;
      for (let offset = 0; offset < 12; offset += 1) {
        total += turnover[index - offset];
      }
      rollingTurnover.push(total);
    }
    this.registry.chart('figure-turnover').setOption({
      textStyle: base.textStyle,
      grid: {
        left: 56,
        right: 24,
        top: 16,
        bottom: 32,
      },
      tooltip: {
        ...base.tooltip,
        trigger: 'axis',
        valueFormatter: (value) => (value === null ? '—' : Format.percent(value, 0)),
      },
      xAxis: {
        type: 'category',
        data: this.series.months.map((month) => MonthArithmetic.label(month)),
        boundaryGap: false,
        axisLine: base.axisLine,
        axisLabel: {
          color: colours.inkMuted,
        },
      },
      yAxis: {
        type: 'value',
        axisLine: base.axisLine,
        splitLine: base.splitLine,
        axisLabel: {
          color: colours.inkMuted,
          formatter: (value) => Format.percent(value, 0),
        },
      },
      series: [
        lineSeries('12-month turnover', rollingTurnover, colours.series[0]),
      ],
    }, true);
    this.renderRiskTable(counts, effective);
  }

  renderRiskTable(counts, effective) {
    const regression = Statistics.regression(this.series.portfolio, this.series.benchmark);
    const costDrag = [];
    this.series.gross.forEach((value, index) => {
      costDrag.push(value - this.series.portfolio[index]);
    });
    const exposure = {
      1: 0,
      2: 0,
      3: 0,
    };
    for (const row of this.currentRows) {
      if (row.tercile) {
        exposure[row.tercile] += row.weight;
      }
    }
    const rows = [
      [
        'Beta to the NIFTY 500',
        Format.number(regression.beta),
      ],
      [
        'Alpha, annualised (<i>t</i>-statistic)',
        `${Format.percent(regression.alpha * 12, 1, true)} (${Format.number(regression.alphaT)})`,
      ],
      [
        'R² against the NIFTY 500',
        Format.number(regression.rSquared),
      ],
      [
        'Average number of shares held',
        Statistics.mean(counts).toFixed(0),
      ],
      [
        'Average effective number of shares',
        Statistics.mean(effective).toFixed(0),
      ],
      [
        'Average annual turnover, bought plus sold',
        Format.percent(Statistics.mean(this.series.turnover) * 12, 0),
      ],
      [
        'Average annual return lost to trading costs',
        Format.percent(Statistics.mean(costDrag) * 12, 2),
      ],
      [
        'Current weight in least / middle / most traded third',
        `${Format.percent(exposure[1], 0)} / ${Format.percent(exposure[2], 0)} / ${Format.percent(exposure[3], 0)}`,
      ],
    ];
    const body = rows.map((row) => `<tr><td class="text">${row[0]}</td><td>${row[1]}</td></tr>`).join('');
    document.getElementById('table-risk').innerHTML = `<caption><b>Table 7.</b> Risk and implementation. Alpha and beta come from regressing monthly portfolio returns on the index's, without a risk-free rate. Liquidity thirds split each month's eligible shares by traded value.</caption><thead><tr><th class="text">Measure</th><th>Value</th></tr></thead><tbody>${body}</tbody>`;
  }
}

new CompanionApp().start().catch((error) => {
  document.getElementById('specification-summary').textContent = `The data could not be loaded: ${error.message}. If you opened this file directly, run jt-momentum-app instead, because browsers block local data files.`;
});
