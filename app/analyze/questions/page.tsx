'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronRight, ChevronLeft, Loader2, HelpCircle, Users, UserCircle, TrendingUp, Truck, DollarSign, Building2 } from 'lucide-react';
import { useAnalysis } from '@/context/AnalysisContext';
import type { QuestionnaireData } from '@/lib/types';
import { analyzeData } from '@/lib/api-client';
import { cn } from '@/lib/utils';
import { Slider } from '@/components/ui/slider';

type RadioOption = { value: string; label: string; sublabel?: string };

function RadioGroup({
  label,
  options,
  value,
  onChange,
  includeUnknown = true,
}: {
  label: string;
  options: RadioOption[];
  value: string | null;
  onChange: (v: string) => void;
  includeUnknown?: boolean;
}) {
  const allOptions = includeUnknown
    ? [...options, { value: 'unknown', label: "I don't know" }]
    : options;

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {allOptions.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={cn(
              'flex flex-col items-start px-4 py-3 rounded-xl border text-left transition-all',
              value === opt.value
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:bg-slate-50'
            )}
          >
            <span className="text-sm font-medium">{opt.label}</span>
            {opt.sublabel && <span className="text-xs text-slate-400 mt-0.5">{opt.sublabel}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

function SliderQuestion({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  hint?: string;
}) {
  const displayValue = value ?? 50;
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">{label}</p>
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-blue-600">{value ?? '—'}%</span>
          <button
            type="button"
            onClick={() => onChange(null)}
            className="text-xs text-slate-400 hover:text-slate-600 flex items-center gap-1"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            Unknown
          </button>
        </div>
      </div>
      <Slider
        value={[displayValue]}
        onValueChange={(vals) => onChange(Array.isArray(vals) ? vals[0] : vals)}
        min={0}
        max={100}
        step={5}
        className="w-full"
      />
      <div className="flex justify-between text-xs text-slate-400">
        <span>0%</span>
        <span>50%</span>
        <span>100%</span>
      </div>
      {hint && <p className="text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

function TriStateToggle({
  label,
  value,
  onChange,
  trueLabel = 'Yes',
  falseLabel = 'No',
}: {
  label: string;
  value: boolean | null;
  onChange: (v: boolean | null) => void;
  trueLabel?: string;
  falseLabel?: string;
}) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <div className="flex gap-2">
        {[
          { val: true, label: trueLabel },
          { val: false, label: falseLabel },
          { val: null, label: "Don't know" },
        ].map(({ val, label: lbl }) => (
          <button
            key={String(val)}
            type="button"
            onClick={() => onChange(val)}
            className={cn(
              'flex-1 py-2 px-3 rounded-lg border text-sm font-medium transition-all',
              value === val
                ? 'border-blue-500 bg-blue-50 text-blue-700'
                : 'border-slate-200 bg-white text-slate-600 hover:border-blue-200'
            )}
          >
            {lbl}
          </button>
        ))}
      </div>
    </div>
  );
}

const SECTIONS = [
  {
    id: 'ownerDependence',
    title: 'Owner Dependence',
    icon: UserCircle,
    description: 'How much does the business rely on the current owner to operate and generate revenue?',
    color: 'text-purple-600',
    bgColor: 'bg-purple-50',
  },
  {
    id: 'customerConcentration',
    title: 'Customer Concentration',
    icon: Users,
    description: 'How concentrated is revenue among a few key customers? Losing one big client could be devastating.',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50',
  },
  {
    id: 'revenueQuality',
    title: 'Revenue Quality',
    icon: TrendingUp,
    description: 'Is revenue predictable and recurring, or lumpy and project-based?',
    color: 'text-green-600',
    bgColor: 'bg-green-50',
  },
  {
    id: 'employeeRisk',
    title: 'Employee & Operational Risk',
    icon: Building2,
    description: 'Does the business have documented processes and a team that can operate without the owner?',
    color: 'text-orange-600',
    bgColor: 'bg-orange-50',
  },
  {
    id: 'supplierRisk',
    title: 'Supplier & Vendor Risk',
    icon: Truck,
    description: 'Are there critical supplier dependencies that could disrupt operations after acquisition?',
    color: 'text-red-600',
    bgColor: 'bg-red-50',
  },
  {
    id: 'financialRisk',
    title: 'Financial & Add-Back Risk',
    icon: DollarSign,
    description: 'Are the financial statements reliable? Are add-backs reasonable and documented?',
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50',
  },
];

const DEFAULT_QUESTIONNAIRE: QuestionnaireData = {
  ownerDependence: {
    ownerSalesPercentage: null,
    ownerInvolvement: 'unknown',
    ownerHoldsRelationships: null,
    survives90DayAbsence: 'unknown',
  },
  customerConcentration: {
    topCustomerRevenuePercent: null,
    top5CustomersRevenuePercent: null,
    contractType: 'unknown',
    averageCustomerTenure: 'unknown',
  },
  revenueQuality: {
    recurringRevenuePercent: null,
    projectBasedPercent: null,
    revenueTrend: 'unknown',
    knownUpcomingLosses: null,
  },
  employeeRisk: {
    totalEmployees: null,
    missionCriticalEmployees: null,
    hasSOPs: null,
    hasManagementLayer: null,
  },
  supplierRisk: {
    singleSupplierOver30Pct: null,
    supplierAgreementsDocumented: null,
    exclusiveVendorRelationships: null,
  },
  financialRisk: {
    hasAddBacks: null,
    addBacksExceed30Pct: null,
    pendingLiabilities: null,
  },
};

export default function QuestionsPage() {
  const router = useRouter();
  const { state, setQuestionnaire, setSharedContext, setReport, setStep, setLoading, setError } = useAnalysis();
  const [currentSection, setCurrentSection] = useState(0);
  const [q, setQ] = useState<QuestionnaireData>(state.questionnaire ?? DEFAULT_QUESTIONNAIRE);

  useEffect(() => {
    setStep(3);
  }, [setStep]);

  function updateOwner(updates: Partial<QuestionnaireData['ownerDependence']>) {
    setQ((prev) => ({ ...prev, ownerDependence: { ...prev.ownerDependence, ...updates } }));
  }
  function updateCustomer(updates: Partial<QuestionnaireData['customerConcentration']>) {
    setQ((prev) => ({ ...prev, customerConcentration: { ...prev.customerConcentration, ...updates } }));
  }
  function updateRevenue(updates: Partial<QuestionnaireData['revenueQuality']>) {
    setQ((prev) => ({ ...prev, revenueQuality: { ...prev.revenueQuality, ...updates } }));
  }
  function updateEmployee(updates: Partial<QuestionnaireData['employeeRisk']>) {
    setQ((prev) => ({ ...prev, employeeRisk: { ...prev.employeeRisk, ...updates } }));
  }
  function updateSupplier(updates: Partial<QuestionnaireData['supplierRisk']>) {
    setQ((prev) => ({ ...prev, supplierRisk: { ...prev.supplierRisk, ...updates } }));
  }
  function updateFinancial(updates: Partial<QuestionnaireData['financialRisk']>) {
    setQ((prev) => ({ ...prev, financialRisk: { ...prev.financialRisk, ...updates } }));
  }

  async function handleGenerate() {
    if (!state.financialData || !state.dealInfo) {
      setError('Missing financial data. Please go back and re-enter your financials.');
      return;
    }
    setQuestionnaire(q);
    setSharedContext(null);
    setLoading(true, 'Running deterministic backend analysis...');
    setError(null);

    try {
      const result = await analyzeData(state.financialData, q, state.dealInfo);
      setReport(result.report);
      setStep(4);
      router.push('/analyze/report');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  const section = SECTIONS[currentSection];
  const Icon = section.icon;
  const progress = ((currentSection + 1) / SECTIONS.length) * 100;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">Risk Assessment</h1>
        <p className="text-slate-500 text-sm">Section {currentSection + 1} of {SECTIONS.length}</p>
        <div className="mt-3 h-1.5 bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-600 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-6">
        <div className="flex items-start gap-4">
          <div className={cn('w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0', section.bgColor)}>
            <Icon className={cn('w-6 h-6', section.color)} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">{section.title}</h2>
            <p className="text-sm text-slate-500 mt-1">{section.description}</p>
          </div>
        </div>

        <div className="space-y-6">
          {currentSection === 0 && (
            <>
              <SliderQuestion
                label="What percentage of sales does the owner personally generate or close?"
                value={q.ownerDependence.ownerSalesPercentage}
                onChange={(v) => updateOwner({ ownerSalesPercentage: v })}
              />
              <RadioGroup
                label="How involved is the owner in day-to-day operations?"
                value={q.ownerDependence.ownerInvolvement}
                onChange={(v) => updateOwner({ ownerInvolvement: v as QuestionnaireData['ownerDependence']['ownerInvolvement'] })}
                options={[
                  { value: 'full_time', label: 'Full-time', sublabel: 'Owner is essential to daily ops' },
                  { value: 'part_time', label: 'Part-time', sublabel: 'Some involvement required' },
                  { value: 'minimal', label: 'Minimal', sublabel: 'Largely hands-off' },
                ]}
              />
              <TriStateToggle
                label="Does the owner hold key customer relationships not shared with staff?"
                value={q.ownerDependence.ownerHoldsRelationships}
                onChange={(v) => updateOwner({ ownerHoldsRelationships: v })}
              />
              <RadioGroup
                label="If the owner disappeared for 90 days, would the business survive?"
                value={q.ownerDependence.survives90DayAbsence}
                onChange={(v) => updateOwner({ survives90DayAbsence: v as QuestionnaireData['ownerDependence']['survives90DayAbsence'] })}
                options={[
                  { value: 'yes', label: 'Yes, definitely' },
                  { value: 'likely', label: 'Likely' },
                  { value: 'unlikely', label: 'Unlikely' },
                  { value: 'no', label: 'No, it would struggle' },
                ]}
              />
            </>
          )}

          {currentSection === 1 && (
            <>
              <SliderQuestion
                label="What % of total revenue comes from the top 1 customer?"
                value={q.customerConcentration.topCustomerRevenuePercent}
                onChange={(v) => updateCustomer({ topCustomerRevenuePercent: v })}
                hint="A single customer over 20% is a concentration risk"
              />
              <SliderQuestion
                label="What % of total revenue comes from the top 5 customers?"
                value={q.customerConcentration.top5CustomersRevenuePercent}
                onChange={(v) => updateCustomer({ top5CustomersRevenuePercent: v })}
              />
              <RadioGroup
                label="Are customer relationships contractual or handshake-based?"
                value={q.customerConcentration.contractType}
                onChange={(v) => updateCustomer({ contractType: v as QuestionnaireData['customerConcentration']['contractType'] })}
                options={[
                  { value: 'mostly_contracted', label: 'Mostly contracted', sublabel: 'Formal agreements in place' },
                  { value: 'mixed', label: 'Mixed', sublabel: 'Some contracts, some informal' },
                  { value: 'mostly_handshake', label: 'Mostly handshake', sublabel: 'Informal relationships' },
                ]}
              />
              <RadioGroup
                label="What is the average customer tenure?"
                value={q.customerConcentration.averageCustomerTenure}
                onChange={(v) => updateCustomer({ averageCustomerTenure: v as QuestionnaireData['customerConcentration']['averageCustomerTenure'] })}
                options={[
                  { value: 'less_than_1_year', label: 'Less than 1 year' },
                  { value: '1_to_3_years', label: '1–3 years' },
                  { value: '3_plus_years', label: '3+ years' },
                ]}
              />
            </>
          )}

          {currentSection === 2 && (
            <>
              <SliderQuestion
                label="What % of revenue is recurring (subscriptions, contracts, retainers)?"
                value={q.revenueQuality.recurringRevenuePercent}
                onChange={(v) => updateRevenue({ recurringRevenuePercent: v })}
                hint="Higher recurring revenue = more predictable cash flow"
              />
              <SliderQuestion
                label="What % of revenue is project-based or one-time?"
                value={q.revenueQuality.projectBasedPercent}
                onChange={(v) => updateRevenue({ projectBasedPercent: v })}
              />
              <RadioGroup
                label="Has revenue grown, stayed flat, or declined over the past 3 years?"
                value={q.revenueQuality.revenueTrend}
                onChange={(v) => updateRevenue({ revenueTrend: v as QuestionnaireData['revenueQuality']['revenueTrend'] })}
                options={[
                  { value: 'growing', label: 'Growing' },
                  { value: 'flat', label: 'Flat' },
                  { value: 'declining', label: 'Declining' },
                ]}
              />
              <TriStateToggle
                label="Are there any known upcoming customer losses or contract expirations?"
                value={q.revenueQuality.knownUpcomingLosses}
                onChange={(v) => updateRevenue({ knownUpcomingLosses: v })}
              />
            </>
          )}

          {currentSection === 3 && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <p className="text-sm font-medium text-slate-700">Total employees</p>
                  <input
                    type="number"
                    value={q.employeeRisk.totalEmployees ?? ''}
                    onChange={(e) => updateEmployee({ totalEmployees: parseInt(e.target.value) || null })}
                    placeholder="e.g. 8"
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
                <div className="space-y-1.5">
                  <p className="text-sm font-medium text-slate-700">Mission-critical employees</p>
                  <input
                    type="number"
                    value={q.employeeRisk.missionCriticalEmployees ?? ''}
                    onChange={(e) => updateEmployee({ missionCriticalEmployees: parseInt(e.target.value) || null })}
                    placeholder="e.g. 2"
                    className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <TriStateToggle
                label="Are there documented standard operating procedures (SOPs)?"
                value={q.employeeRisk.hasSOPs}
                onChange={(v) => updateEmployee({ hasSOPs: v })}
                trueLabel="Yes, documented"
                falseLabel="No, not documented"
              />
              <TriStateToggle
                label="Is there a management layer between the owner and frontline staff?"
                value={q.employeeRisk.hasManagementLayer}
                onChange={(v) => updateEmployee({ hasManagementLayer: v })}
                trueLabel="Yes, managers in place"
                falseLabel="No, owner manages directly"
              />
            </>
          )}

          {currentSection === 4 && (
            <>
              <TriStateToggle
                label="Is there a single supplier that accounts for >30% of COGS or operations?"
                value={q.supplierRisk.singleSupplierOver30Pct}
                onChange={(v) => updateSupplier({ singleSupplierOver30Pct: v })}
              />
              <TriStateToggle
                label="Are supplier agreements documented and transferable to a new owner?"
                value={q.supplierRisk.supplierAgreementsDocumented}
                onChange={(v) => updateSupplier({ supplierAgreementsDocumented: v })}
                trueLabel="Yes, transferable"
                falseLabel="No, not transferable"
              />
              <TriStateToggle
                label="Are there exclusive or hard-to-replace vendor relationships?"
                value={q.supplierRisk.exclusiveVendorRelationships}
                onChange={(v) => updateSupplier({ exclusiveVendorRelationships: v })}
              />
            </>
          )}

          {currentSection === 5 && (
            <>
              <TriStateToggle
                label="Has the seller presented add-backs to adjusted EBITDA (owner salary, one-time expenses)?"
                value={q.financialRisk.hasAddBacks}
                onChange={(v) => updateFinancial({ hasAddBacks: v })}
              />
              <TriStateToggle
                label="Do the add-backs exceed 30% of stated EBITDA?"
                value={q.financialRisk.addBacksExceed30Pct}
                onChange={(v) => updateFinancial({ addBacksExceed30Pct: v })}
              />
              <TriStateToggle
                label="Are there any pending lawsuits, tax liabilities, or environmental issues?"
                value={q.financialRisk.pendingLiabilities}
                onChange={(v) => updateFinancial({ pendingLiabilities: v })}
              />
            </>
          )}
        </div>
      </div>

      {state.error && (
        <div className="mt-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {state.error}
        </div>
      )}

      {state.isLoading && (
        <div className="mt-4 bg-white border border-slate-200 rounded-2xl p-4">
          <p className="text-sm font-semibold text-slate-900">Backend Analysis In Progress</p>
          <p className="text-sm text-slate-500 mt-1">
            The frontend is sending your financials and questionnaire answers to the Python backend for deterministic scoring.
          </p>
        </div>
      )}

      <div className="mt-6 flex gap-3">
        <button
          onClick={() => currentSection > 0 ? setCurrentSection(s => s - 1) : router.push('/analyze/review')}
          className="flex items-center gap-2 border border-slate-200 bg-white text-slate-700 hover:border-slate-300 px-5 py-3 rounded-xl font-medium transition-colors text-sm"
        >
          <ChevronLeft className="w-4 h-4" />
          {currentSection === 0 ? 'Back to Review' : 'Previous'}
        </button>

        {currentSection < SECTIONS.length - 1 ? (
          <button
            onClick={() => setCurrentSection(s => s + 1)}
            className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-semibold transition-colors"
          >
            Next Section
            <ChevronRight className="w-5 h-5" />
          </button>
        ) : (
          <button
            onClick={handleGenerate}
            disabled={state.isLoading}
            className="flex-1 flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl font-semibold transition-colors"
          >
            {state.isLoading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                {state.loadingMessage || 'Generating report...'}
              </>
            ) : (
              <>
                Generate Report
                <ChevronRight className="w-5 h-5" />
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
