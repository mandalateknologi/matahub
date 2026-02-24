/**
 * Chart.js Configuration Utility
 * 
 * Provides theme-matched Chart.js configurations for ATVISION
 * Colors: Navy #1D2F43, Accent #E1604C
 */

import { Chart, registerables } from 'chart.js';
import ChartDataLabels from 'chartjs-plugin-datalabels';

// Register Chart.js components
Chart.register(...registerables, ChartDataLabels);

// ATVISION theme colors
export const colors = {
  navy: '#1D2F43',
  accent: '#E1604C',
  gray: '#9CA3AF',
  lightGray: '#E5E7EB',
  success: '#10B981',
  warning: '#F59E0B',
  error: '#EF4444',
  info: '#3B82F6',
};

// Generate color palette for multiple classes
export function generateColorPalette(count: number): string[] {
  const baseColors = [
    colors.accent,
    colors.info,
    colors.success,
    colors.warning,
    colors.navy,
    '#8B5CF6', // Purple
    '#EC4899', // Pink
    '#14B8A6', // Teal
    '#F97316', // Orange
    '#6366F1', // Indigo
  ];
  
  // Repeat colors if we need more than available
  const palette: string[] = [];
  for (let i = 0; i < count; i++) {
    palette.push(baseColors[i % baseColors.length]);
  }
  return palette;
}

// Default chart options
export const defaultChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      position: 'bottom' as const,
      labels: {
        color: colors.navy,
        font: {
          family: 'Montserrat, sans-serif',
          size: 12,
        },
        padding: 15,
        usePointStyle: true,
      },
    },
    tooltip: {
      backgroundColor: colors.navy,
      titleColor: '#FFFFFF',
      bodyColor: '#FFFFFF',
      borderColor: colors.accent,
      borderWidth: 1,
      padding: 12,
      titleFont: {
        family: 'Montserrat, sans-serif',
        size: 14,
        weight: 'bold' as const,
      },
      bodyFont: {
        family: 'Montserrat, sans-serif',
        size: 13,
      },
      displayColors: true,
      boxPadding: 6,
    },
  },
};

// Configuration for horizontal bar chart (classification confidence)
export function getClassificationBarConfig(
  labels: string[],
  probabilities: number[],
  options: any = {}
) {
  return {
    type: 'bar' as const,
    data: {
      labels,
      datasets: [{
        label: 'Confidence',
        data: probabilities,
        backgroundColor: generateColorPalette(labels.length),
        borderColor: colors.navy,
        borderWidth: 1,
      }],
    },
    options: {
      ...defaultChartOptions,
      indexAxis: 'y' as const,
      scales: {
        x: {
          beginAtZero: true,
          max: 1.0,
          ticks: {
            callback: (value: number) => `${(value * 100).toFixed(0)}%`,
            color: colors.gray,
            font: {
              family: 'Montserrat, sans-serif',
              size: 11,
            },
          },
          grid: {
            color: colors.lightGray,
          },
        },
        y: {
          ticks: {
            color: colors.navy,
            font: {
              family: 'Montserrat, sans-serif',
              size: 12,
            },
          },
          grid: {
            display: false,
          },
        },
      },
      plugins: {
        ...defaultChartOptions.plugins,
        legend: {
          display: false,
        },
        datalabels: {
          anchor: 'end' as const,
          align: 'end' as const,
          color: colors.navy,
          font: {
            family: 'Montserrat, sans-serif',
            size: 11,
            weight: 'bold' as const,
          },
          formatter: (value: number) => `${(value * 100).toFixed(1)}%`,
        },
      },
      ...options,
    },
  };
}

// Configuration for confidence distribution histogram
export function getConfidenceHistogramConfig(
  confidenceValues: number[],
  bins: number = 10,
  options: any = {}
) {
  // Create histogram bins
  const binSize = 1.0 / bins;
  const binCounts = new Array(bins).fill(0);
  const binLabels: string[] = [];
  
  // Generate bin labels
  for (let i = 0; i < bins; i++) {
    const start = (i * binSize * 100).toFixed(0);
    const end = ((i + 1) * binSize * 100).toFixed(0);
    binLabels.push(`${start}-${end}%`);
  }
  
  // Count values in each bin
  confidenceValues.forEach(value => {
    const binIndex = Math.min(Math.floor(value / binSize), bins - 1);
    binCounts[binIndex]++;
  });
  
  return {
    type: 'bar' as const,
    data: {
      labels: binLabels,
      datasets: [{
        label: 'Frequency',
        data: binCounts,
        backgroundColor: colors.accent,
        borderColor: colors.navy,
        borderWidth: 1,
      }],
    },
    options: {
      ...defaultChartOptions,
      scales: {
        x: {
          ticks: {
            color: colors.gray,
            font: {
              family: 'Montserrat, sans-serif',
              size: 11,
            },
          },
          grid: {
            display: false,
          },
        },
        y: {
          beginAtZero: true,
          ticks: {
            color: colors.gray,
            font: {
              family: 'Montserrat, sans-serif',
              size: 11,
            },
            precision: 0,
          },
          grid: {
            color: colors.lightGray,
          },
        },
      },
      plugins: {
        ...defaultChartOptions.plugins,
        legend: {
          display: false,
        },
        datalabels: {
          display: false,
        },
      },
      ...options,
    },
  };
}

// Configuration for class distribution pie chart
export function getClassDistributionPieConfig(
  classNames: string[],
  classCounts: number[],
  options: any = {}
) {
  return {
    type: 'pie' as const,
    data: {
      labels: classNames,
      datasets: [{
        data: classCounts,
        backgroundColor: generateColorPalette(classNames.length),
        borderColor: '#FFFFFF',
        borderWidth: 2,
      }],
    },
    options: {
      ...defaultChartOptions,
      plugins: {
        ...defaultChartOptions.plugins,
        datalabels: {
          color: '#FFFFFF',
          font: {
            family: 'Montserrat, sans-serif',
            size: 12,
            weight: 'bold' as const,
          },
          formatter: (value: number, context: any) => {
            const total = context.chart.data.datasets[0].data.reduce((a: number, b: number) => a + b, 0);
            const percentage = ((value / total) * 100).toFixed(1);
            return `${percentage}%`;
          },
        },
      },
      ...options,
    },
  };
}

// Configuration for confusion matrix (heatmap - placeholder for future)
export function getConfusionMatrixConfig(
  classNames: string[],
  matrix: number[][],
  options: any = {}
) {
  // This is a placeholder - full implementation would use Chart.js matrix plugin
  // or a custom rendering approach
  return {
    type: 'scatter' as const,
    data: {
      datasets: [{
        label: 'Confusion Matrix',
        data: [],
        backgroundColor: colors.accent,
      }],
    },
    options: {
      ...defaultChartOptions,
      scales: {
        x: {
          type: 'category' as const,
          labels: classNames,
        },
        y: {
          type: 'category' as const,
          labels: classNames,
        },
      },
      ...options,
    },
  };
}

export default {
  colors,
  generateColorPalette,
  defaultChartOptions,
  getClassificationBarConfig,
  getConfidenceHistogramConfig,
  getClassDistributionPieConfig,
  getConfusionMatrixConfig,
};
