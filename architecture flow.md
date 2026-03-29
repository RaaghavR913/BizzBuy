# Architecture Flow

This reflects the current application flow as implemented in the codebase today.

## Visual overview

![BizBuy application architecture flow — Phases 1–4 from ingestion through buyer PDF](./architecture-flow.png)

*Generated flowchart (PNG). The Mermaid diagram in the next section is the same flow in an editable, text-based form.*

---

## Editable diagram (Mermaid)

```mermaid
flowchart TD
    landing[LandingPage] --> upload[UploadPage]

    subgraph phase1 [Phase1_DocumentIngestion]
        upload -->|"upload files"| parse["/api/parse-documents"]
        upload -->|"demo mode"| demo[DemoFinancialData]
        upload -->|"manual skip"| manual[ManualFinancialData]

        parse --> structuredPayload[StructuredDataPayload]
        demo --> structuredPayload
        manual --> structuredPayload
    end

    structuredPayload --> review[ReviewPage]
    review --> dealInfo[DealInfoConfirmed]

    subgraph phase2 [Phase2_ParallelAgents]
        dealInfo --> questions[QuestionsPage]
        questions --> questionnaire[QuestionnaireData]
        questionnaire --> phase2Runner["runPhase2Agents()"]

        phase2Runner --> financial["/api/agents/financial"]
        phase2Runner --> tax["/api/agents/tax"]
        phase2Runner --> ar["/api/agents/ar-collections"]
        phase2Runner --> customer["/api/agents/customer"]
        phase2Runner --> operations["/api/agents/operations"]
        phase2Runner --> lease["/api/agents/lease-contracts"]
        phase2Runner --> market["/api/agents/market-macro"]

        financial --> merge["/api/agents/merge"]
        tax --> merge
        ar --> merge
        customer --> merge
        operations --> merge
        lease --> merge
        market --> merge
    end

    subgraph phase3 [Phase3_SharedContextAndAnalysis]
        merge --> sharedContext[SharedContext]
        sharedContext --> analyze["/api/analyze"]
        analyze --> lending[LendingAndAffordability]
        lending --> synthesis[SynthesisAndReport]
    end

    subgraph phase4 [Phase4_BuyerReport]
        synthesis --> report[ReportPage]
        report --> download["/api/generate-pdf"]
        download --> pdf[PlainLanguageBuyerPDF]
    end
```

## Notes

- `Phase 1` produces the structured financial payload from uploads, demo data, or manual entry.
- `Phase 2` runs seven specialized agents in parallel, then merges their outputs into a single shared context.
- `Phase 3` performs lending and affordability analysis, then synthesizes the final report payload.
- `Phase 4` renders the on-screen buyer report and generates a downloadable PDF.
