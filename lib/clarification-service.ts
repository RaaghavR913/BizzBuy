import type {
  CanonicalDocumentType,
  ClarificationAnswer,
  ClarificationOption,
  ClarificationQuestion,
  FinancialData,
  PipelineDocumentPayload,
  QuestionnaireData,
} from './types';

type ClarificationResponseValue = string | number | boolean | null;

const MAX_CLARIFICATIONS = 4;

export const DEFAULT_QUESTIONNAIRE: QuestionnaireData = {
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

type QuestionFactoryArgs = {
  prompt: string;
  helpText: string;
  relatedDocumentTypes: CanonicalDocumentType[];
  legacyFieldPath: string;
};

function percentQuestion(id: string, category: ClarificationQuestion['category'], args: QuestionFactoryArgs): ClarificationQuestion {
  return {
    id,
    category,
    answerType: 'percent',
    prompt: args.prompt,
    helpText: args.helpText,
    relatedDocumentTypes: args.relatedDocumentTypes,
    legacyFieldPath: args.legacyFieldPath,
  };
}

function booleanQuestion(id: string, category: ClarificationQuestion['category'], args: QuestionFactoryArgs): ClarificationQuestion {
  return {
    id,
    category,
    answerType: 'boolean',
    prompt: args.prompt,
    helpText: args.helpText,
    relatedDocumentTypes: args.relatedDocumentTypes,
    legacyFieldPath: args.legacyFieldPath,
  };
}

function selectQuestion(
  id: string,
  category: ClarificationQuestion['category'],
  args: QuestionFactoryArgs & { options: ClarificationOption[] }
): ClarificationQuestion {
  return {
    id,
    category,
    answerType: 'select',
    prompt: args.prompt,
    helpText: args.helpText,
    relatedDocumentTypes: args.relatedDocumentTypes,
    legacyFieldPath: args.legacyFieldPath,
    options: args.options,
  };
}

function notesContain(financialData: FinancialData | null, patterns: RegExp[]): boolean {
  const notes = financialData?.parsingNotes ?? [];
  return notes.some((note) => patterns.some((pattern) => pattern.test(note)));
}

export function generateClarificationQuestions(
  documents: PipelineDocumentPayload[],
  financialData: FinancialData | null
): ClarificationQuestion[] {
  const availableTypes = new Set(documents.map((document) => document.document_type));
  const questions: ClarificationQuestion[] = [];

  if (!availableTypes.has('customer_list') && !availableTypes.has('ar_aging_report')) {
    questions.push(
      percentQuestion('customer-top-revenue', 'customer_concentration', {
        prompt: 'No customer concentration schedule was found. Roughly what percent of revenue comes from the largest customer?',
        helpText: 'Use your best estimate only if the documents do not already show it.',
        relatedDocumentTypes: ['customer_list', 'ar_aging_report'],
        legacyFieldPath: 'customerConcentration.topCustomerRevenuePercent',
      })
    );
  }

  if (!availableTypes.has('contract')) {
    questions.push(
      selectQuestion('customer-contracting', 'customer_concentration', {
        prompt: 'Customer contract coverage is unclear from the uploaded package. How are most customer relationships structured today?',
        helpText: 'This is supplemental context until customer contracts are reviewed.',
        relatedDocumentTypes: ['contract'],
        legacyFieldPath: 'customerConcentration.contractType',
        options: [
          { value: 'mostly_contracted', label: 'Mostly contracted', sublabel: 'Formal agreements drive most revenue' },
          { value: 'mixed', label: 'Mixed', sublabel: 'Some contracts, some informal' },
          { value: 'mostly_handshake', label: 'Mostly handshake', sublabel: 'Renewals depend on relationships' },
        ],
      })
    );
  }

  if (!availableTypes.has('employee_roster')) {
    questions.push(
      booleanQuestion('management-layer', 'operational_transferability', {
        prompt: 'No employee roster or org chart was found. Is there a manager or lead operator who can run day-to-day operations without the owner?',
        helpText: 'We treat this as buyer-provided context, not documentary proof.',
        relatedDocumentTypes: ['employee_roster'],
        legacyFieldPath: 'employeeRisk.hasManagementLayer',
      })
    );
  }

  if (!availableTypes.has('employee_roster') && !availableTypes.has('contract')) {
    questions.push(
      selectQuestion('owner-absence', 'owner_dependence', {
        prompt: 'Based on how the business currently runs, what happens if the owner steps away for 90 days?',
        helpText: 'Use this only to fill a transferability gap not covered in the files.',
        relatedDocumentTypes: ['employee_roster', 'contract'],
        legacyFieldPath: 'ownerDependence.survives90DayAbsence',
        options: [
          { value: 'yes', label: 'Business runs normally' },
          { value: 'likely', label: 'Likely manageable' },
          { value: 'unlikely', label: 'Would be strained' },
          { value: 'no', label: 'Would materially struggle' },
        ],
      })
    );
  }

  if (
    !availableTypes.has('tax_return_1120s')
    && !availableTypes.has('tax_return_1040')
    && !availableTypes.has('tax_return_schedule_c')
  ) {
    questions.push(
      booleanQuestion('pending-liabilities', 'financial_risk', {
        prompt: 'Tax and legal support is incomplete. Are there any known pending lawsuits, tax issues, or similar liabilities not shown in the uploaded documents?',
        helpText: 'Assertions here remain lower-confidence until documented.',
        relatedDocumentTypes: ['tax_return_1120s', 'tax_return_1040', 'tax_return_schedule_c'],
        legacyFieldPath: 'financialRisk.pendingLiabilities',
      })
    );
  } else if (notesContain(financialData, [/lawsuit/i, /liabilit/i, /tax issue/i, /unclear/i])) {
    questions.push(
      booleanQuestion('pending-liabilities', 'financial_risk', {
        prompt: 'The parsed documents reference a possible unresolved obligation. Are there any known pending liabilities still outside the uploaded package?',
        helpText: 'This answer supplements, but does not override, documentary evidence.',
        relatedDocumentTypes: ['tax_return_1120s', 'tax_return_1040', 'tax_return_schedule_c'],
        legacyFieldPath: 'financialRisk.pendingLiabilities',
      })
    );
  }

  return questions.slice(0, MAX_CLARIFICATIONS);
}

export function buildClarificationAnswers(
  questions: ClarificationQuestion[],
  responses: Record<string, ClarificationResponseValue>
): ClarificationAnswer[] {
  return questions.flatMap((question) => {
    const value = responses[question.id] ?? null;
    if (value === null || value === '' || typeof value === 'undefined') {
      return [];
    }

    const valueLabel =
      question.answerType === 'select'
        ? question.options?.find((option) => option.value === value)?.label
        : question.answerType === 'percent' && typeof value === 'number'
        ? `${value}%`
        : typeof value === 'boolean'
        ? value ? 'Yes' : 'No'
        : undefined;

    return [
      {
        questionId: question.id,
        prompt: question.prompt,
        category: question.category,
        answerType: question.answerType,
        value,
        valueLabel,
        relatedDocumentTypes: question.relatedDocumentTypes,
        legacyFieldPath: question.legacyFieldPath,
        source: 'user_asserted',
        confidence: 0.6,
        supplemental: true,
      },
    ];
  });
}

export function questionnaireFromClarifications(
  clarifications: ClarificationAnswer[],
  baseQuestionnaire: QuestionnaireData = DEFAULT_QUESTIONNAIRE
): QuestionnaireData {
  const next = structuredClone(baseQuestionnaire);

  for (const clarification of clarifications) {
    const path = clarification.legacyFieldPath.split('.');
    if (path.length !== 2) {
      continue;
    }

    const [sectionKey, fieldKey] = path as [keyof QuestionnaireData, string];
    const section = next[sectionKey];
    if (!section || !(fieldKey in section)) {
      continue;
    }

    (section as Record<string, string | number | boolean | null>)[fieldKey] =
      clarification.value as string | number | boolean | null;
  }

  return next;
}
