import { z } from 'zod';

const documentTypeEnum = z.enum([
  'profit_and_loss',
  'balance_sheet',
  'cash_flow_statement',
  'tax_return_1120s',
  'tax_return_1040',
  'tax_return_schedule_c',
  'ar_aging_report',
  'customer_list',
  'contract',
  'lease_agreement',
  'employee_roster',
  'insurance_policy',
  'equipment_list',
  'other',
]);

export const DocumentSectionSchema = z
  .object({
    documentId: z.string().describe('References the source UploadedDocument id'),
    documentType: documentTypeEnum,
    timeframe: z.object({
      startDate: z.string().optional(),
      endDate: z.string().optional(),
      fiscalYear: z.number().int().optional(),
    }),
    extractedData: z
      .record(z.string(), z.any())
      .describe('Raw key-value pairs extracted from this section'),
    rawText: z.string().describe('Original text from the document section'),
    confidence: z
      .number()
      .min(0)
      .max(1)
      .describe('Model confidence in extraction accuracy, 0-1'),
  })
  .describe('A parsed section of an uploaded document');

export const IngestionOutputSchema = z
  .object({
    documents: z.array(
      z.object({
        documentId: z.string(),
        fileName: z.string(),
        mimeType: z.string(),
        documentType: documentTypeEnum,
        sections: z.array(DocumentSectionSchema),
      })
    ),
    metadata: z.object({
      totalDocuments: z.number().int(),
      successfullyParsed: z.number().int(),
      failedDocuments: z
        .array(z.string())
        .describe('Document IDs that could not be parsed'),
      warnings: z.array(z.string()),
    }),
  })
  .describe(
    'Document Ingestion agent output — structured data extracted from all uploaded business documents'
  );

export type DocumentSection = z.infer<typeof DocumentSectionSchema>;
export type IngestionOutput = z.infer<typeof IngestionOutputSchema>;
