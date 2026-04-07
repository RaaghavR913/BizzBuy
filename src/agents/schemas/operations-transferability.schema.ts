import { z } from 'zod';

const severityEnum = z.enum(['low', 'medium', 'high', 'critical']);
const criticalityEnum = z.enum(['low', 'medium', 'high']);
const conditionEnum = z.enum(['good', 'fair', 'poor']);

const KeyPersonnelSchema = z.object({
  name: z.string(),
  role: z.string(),
  tenure: z.string().describe('How long this person has been in the role'),
  criticality: criticalityEnum,
  retentionRisk: criticalityEnum,
});

const LicenseSchema = z.object({
  type: z.string(),
  holder: z.string(),
  transferable: z.boolean(),
  expiryDate: z.string().optional(),
  renewalProcess: z.string().optional(),
});

const InsuranceSchema = z.object({
  type: z.string(),
  provider: z.string(),
  annualPremium: z.number().describe('Annual premium in USD'),
  adequate: z.boolean(),
  notes: z.string().optional(),
});

const EquipmentItemSchema = z.object({
  name: z.string(),
  condition: conditionEnum,
  estimatedAge: z.string(),
  estimatedValue: z.number().describe('Estimated current value in USD'),
  replacementNeeded: z.boolean(),
});

const OpsRiskSchema = z.object({
  id: z.string(),
  severity: severityEnum,
  category: z.string(),
  title: z.string(),
  description: z.string(),
  recommendation: z.string(),
});

export const OpsTransferabilityOutputSchema = z
  .object({
    ownerDependence: z.object({
      weeklyHoursWorked: z.number(),
      rolesPerformed: z.array(z.string()),
      hasDelegatedManagement: z.boolean(),
      transitionTimeEstimate: z
        .string()
        .describe('Estimated time for a new owner to take over'),
      score: z
        .number()
        .int()
        .min(1)
        .max(10)
        .describe(
          'Owner dependence score, 1 (owner does everything) to 10 (fully delegated)'
        ),
    }),
    employees: z.object({
      headcount: z.number().int(),
      keyPersonnel: z.array(KeyPersonnelSchema),
      turnoverRate: z.number().optional().describe('Annual turnover rate as decimal'),
    }),
    licenses: z.array(LicenseSchema),
    insurance: z.array(InsuranceSchema),
    equipment: z.object({
      totalEstimatedValue: z
        .number()
        .describe('Total estimated equipment value in USD'),
      items: z.array(EquipmentItemSchema),
    }),
    risks: z.array(OpsRiskSchema),
    overallScore: z
      .number()
      .int()
      .min(1)
      .max(10)
      .describe(
        'Operations transferability score, 1 (very difficult) to 10 (seamless)'
      ),
    confidence: z.number().min(0).max(1),
    summary: z
      .string()
      .describe('Plain-language operations and transferability summary'),
  })
  .describe(
    'Operations & Transferability agent output — owner dependence, staffing, licenses, insurance, and equipment analysis'
  );

export type OpsTransferabilityOutput = z.infer<
  typeof OpsTransferabilityOutputSchema
>;
