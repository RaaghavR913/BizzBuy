import { z } from 'zod';

const severityEnum = z.enum(['low', 'medium', 'high', 'critical']);
const enforceabilityEnum = z.enum(['low', 'medium', 'high']);
const escalationTypeEnum = z.enum(['fixed', 'CPI', 'percentage']);

const RenewalOptionSchema = z.object({
  term: z.string(),
  conditions: z.string(),
});

const LeaseDetailsSchema = z.object({
  landlord: z.string(),
  monthlyRent: z.number().describe('Monthly rent in USD'),
  annualRent: z.number().describe('Annual rent in USD'),
  leaseStart: z.string(),
  leaseEnd: z.string(),
  remainingMonths: z.number().int(),
  isTransferable: z.boolean(),
  assignmentClause: z.string().optional(),
  rentEscalation: z.object({
    type: escalationTypeEnum,
    rate: z.number().optional().describe('Escalation rate as decimal'),
    schedule: z.string().optional(),
  }),
  renewalOptions: z.array(RenewalOptionSchema),
  restrictions: z.array(z.string()),
});

const NonCompeteSchema = z.object({
  exists: z.boolean(),
  scope: z.string().optional(),
  duration: z.string().optional(),
  geographicArea: z.string().optional(),
  enforceability: enforceabilityEnum,
});

const OtherContractSchema = z.object({
  type: z.string(),
  counterparty: z.string(),
  term: z.string(),
  transferable: z.boolean(),
  keyTerms: z.array(z.string()),
  risks: z.array(z.string()),
});

const LeaseRiskSchema = z.object({
  id: z.string(),
  severity: severityEnum,
  title: z.string(),
  description: z.string(),
  recommendation: z.string(),
});

export const LeaseContractOutputSchema = z
  .object({
    lease: LeaseDetailsSchema.nullable().describe(
      'Primary business lease details, null if no lease exists'
    ),
    nonCompete: NonCompeteSchema.nullable().describe(
      'Non-compete agreement details, null if none exists'
    ),
    otherContracts: z.array(OtherContractSchema),
    risks: z.array(LeaseRiskSchema),
    overallScore: z
      .number()
      .int()
      .min(1)
      .max(10)
      .describe(
        'Lease and contract score, 1 (major issues) to 10 (favorable terms)'
      ),
    confidence: z.number().min(0).max(1),
    summary: z
      .string()
      .describe('Plain-language lease and contract summary'),
  })
  .describe(
    'Lease & Contract agent output — lease terms, non-compete, vendor contracts, and transferability analysis'
  );

export type LeaseContractOutput = z.infer<typeof LeaseContractOutputSchema>;
