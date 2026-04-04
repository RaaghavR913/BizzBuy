import React from 'react';
import { Document, Page, StyleSheet, Text, View } from '@react-pdf/renderer';
import type { ReportOutput } from './types';

const styles = StyleSheet.create({
  page: {
    padding: 32,
    fontSize: 10,
    fontFamily: 'Helvetica',
    color: '#1e293b',
  },
  header: {
    marginBottom: 20,
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    marginBottom: 6,
  },
  subtitle: {
    fontSize: 10,
    color: '#64748b',
    marginBottom: 8,
  },
  badgeRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
    marginBottom: 12,
    flexWrap: 'wrap',
  },
  badge: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 999,
    backgroundColor: '#e2e8f0',
  },
  verdict: {
    backgroundColor: '#eff6ff',
    borderRadius: 10,
    padding: 12,
  },
  verdictTitle: {
    fontSize: 12,
    fontWeight: 700,
    marginBottom: 4,
  },
  section: {
    marginBottom: 18,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: 700,
    marginBottom: 8,
  },
  paragraph: {
    lineHeight: 1.5,
    marginBottom: 6,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  card: {
    width: '48%',
    backgroundColor: '#f8fafc',
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
  cardLabel: {
    fontSize: 8,
    color: '#64748b',
    marginBottom: 3,
    textTransform: 'uppercase',
  },
  cardValue: {
    fontSize: 12,
    fontWeight: 700,
  },
  listItem: {
    marginBottom: 4,
    lineHeight: 1.4,
  },
  flagCritical: {
    color: '#b91c1c',
  },
  flagWarning: {
    color: '#b45309',
  },
  flagInfo: {
    color: '#1d4ed8',
  },
  footer: {
    marginTop: 16,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#e2e8f0',
    fontSize: 8,
    color: '#64748b',
  },
});

function renderList(items: string[]) {
  return items.map((item, index) => (
    <Text key={`${item}-${index}`} style={styles.listItem}>
      • {item}
    </Text>
  ));
}

function renderFlagColor(severity: 'info' | 'warning' | 'critical') {
  if (severity === 'critical') return styles.flagCritical;
  if (severity === 'warning') return styles.flagWarning;
  return styles.flagInfo;
}

export function ReportPdfDocument({ report }: { report: ReportOutput }) {
  return (
    <Document
      title="BizBuy Acquisition Analysis Report"
      author="BizBuy"
      subject="Business acquisition diligence report"
      creator="BizBuy"
      producer="BizBuy"
    >
      <Page size="LETTER" style={styles.page}>
        <View style={styles.header}>
          <Text style={styles.title}>BizBuy Acquisition Analysis Report</Text>
          <Text style={styles.subtitle}>
            Generated {new Date(report.metadata.generatedAt).toLocaleDateString('en-US')}
          </Text>
          <View style={styles.badgeRow}>
            <Text style={styles.badge}>Risk: {report.executiveSummary.riskScore}/100 ({report.executiveSummary.riskLabel})</Text>
            <Text style={styles.badge}>Transferability: {report.transferabilityAnalysis.score}/100 ({report.executiveSummary.transferabilityLabel})</Text>
            <Text style={styles.badge}>Bankability: {report.sbaLoanSizing.bankabilityScore}/100 ({report.sbaLoanSizing.bankabilityLabel})</Text>
          </View>
          <View style={styles.verdict}>
            <Text style={styles.verdictTitle}>{report.finalRecommendation.action.replace(/_/g, ' ').toUpperCase()}</Text>
            <Text>{report.finalRecommendation.summaryStatement}</Text>
          </View>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>1. Executive Summary</Text>
          <Text style={styles.paragraph}>{report.executiveSummary.text}</Text>
          <Text style={styles.paragraph}>{report.executiveSummary.verdict}</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>2. Financial Snapshot</Text>
          <View style={styles.grid}>
            {Object.entries(report.financialSnapshot.metrics).slice(0, 8).map(([key, metric]) => (
              <View key={key} style={styles.card}>
                <Text style={styles.cardLabel}>{key}</Text>
                <Text style={styles.cardValue}>{metric.formatted}</Text>
                {metric.note ? <Text>{metric.note}</Text> : null}
              </View>
            ))}
          </View>
          <Text style={styles.paragraph}>
            Valuation multiple: {report.financialSnapshot.valuationMultiple === Infinity ? '∞' : `${report.financialSnapshot.valuationMultiple.toFixed(2)}x`}
          </Text>
          <Text style={styles.paragraph}>{report.financialSnapshot.multipleAssessment}</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>3. Debt Service & Affordability</Text>
          <View style={styles.grid}>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>Monthly Debt Service</Text>
              <Text style={styles.cardValue}>{new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(report.debtServiceAnalysis.monthlyDebtService)}</Text>
            </View>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>Annual Debt Service</Text>
              <Text style={styles.cardValue}>{new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(report.debtServiceAnalysis.annualDebtService)}</Text>
            </View>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>DSCR</Text>
              <Text style={styles.cardValue}>{report.debtServiceAnalysis.dscr === 999 ? '∞' : report.debtServiceAnalysis.dscr.toFixed(2)}</Text>
            </View>
            <View style={styles.card}>
              <Text style={styles.cardLabel}>SBA Max Loan</Text>
              <Text style={styles.cardValue}>{new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(report.sbaLoanSizing.maxSupportedLoan)}</Text>
            </View>
          </View>
          <Text style={styles.paragraph}>{report.debtServiceAnalysis.dscrAssessment}</Text>
          <Text style={styles.paragraph}>{report.debtServiceAnalysis.affordabilityVerdict}</Text>
          <Text style={styles.paragraph}>{report.sbaLoanSizing.explanation}</Text>
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>4. Risk Assessment</Text>
          {report.riskAssessment.dimensions.map((dimension) => (
            <View key={dimension.dimension} style={{ marginBottom: 8 }}>
              <Text style={styles.paragraph}>
                {dimension.dimension}: {dimension.score}/10 ({dimension.label})
              </Text>
              <Text style={styles.paragraph}>{dimension.explanation}</Text>
            </View>
          ))}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>5. Backend Risk Flags</Text>
          {report.agentFlags.length > 0 ? report.agentFlags.map((flag, index) => (
            <Text key={`${flag.message}-${index}`} style={[styles.listItem, renderFlagColor(flag.severity)]}>
              • [{flag.severity.toUpperCase()}] {flag.dimension}: {flag.message}
            </Text>
          )) : <Text style={styles.paragraph}>No additional shared agent flags were surfaced.</Text>}
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>6. Questions, Diligence, and Recommendation</Text>
          <Text style={styles.paragraph}>Top risks:</Text>
          {renderList(report.finalRecommendation.risks)}
          <Text style={styles.paragraph}>Top strengths:</Text>
          {renderList(report.finalRecommendation.strengths)}
          <Text style={styles.paragraph}>Next steps:</Text>
          {renderList(report.finalRecommendation.nextSteps)}
        </View>

        <View style={styles.footer}>
          {report.metadata.disclaimers.map((disclaimer, index) => (
            <Text key={`${disclaimer}-${index}`} style={styles.listItem}>
              {disclaimer}
            </Text>
          ))}
          <Text>BizBuy Analysis v{report.metadata.analysisVersion}</Text>
        </View>
      </Page>
    </Document>
  );
}
