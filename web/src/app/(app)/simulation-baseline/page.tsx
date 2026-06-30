"use client";

import { useState } from "react";
import { FileDown, Loader2 } from "lucide-react";
import PageHeader from "@/components/shell/PageHeader";
import CampaignWhatIf from "@/components/simulation/CampaignWhatIf";
import { api, mediaUrl } from "@/lib/api";

export default function SimulationBaselinePage() {
  const [reportBusy, setReportBusy] = useState(false);
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  const downloadReport = async () => {
    setReportBusy(true);
    setReportUrl(null);
    try {
      const { run_id } = await api.reportBuildingSemantic();
      // Poll until the run completes, then surface the PDF link.
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        const run = await api.agentRun(run_id);
        if (run.status !== "running") {
          const pdf = run.state_json?.pdf_path;
          if (pdf) setReportUrl(pdf);
          break;
        }
      }
    } finally {
      setReportBusy(false);
    }
  };

  return (
    <div data-wide-page className="pb-4">
      <PageHeader
        title="Validation Experiment"
        actions={
          <div className="flex items-center gap-2">
            {reportUrl && (
              <a href={mediaUrl(reportUrl)} target="_blank" className="btn-secondary text-[13px]">
                <FileDown size={15} /> Open PDF
              </a>
            )}
            <button onClick={downloadReport} disabled={reportBusy} className="btn-primary">
              {reportBusy ? <Loader2 size={15} className="animate-spin" /> : <FileDown size={15} />}
              {reportBusy ? "Generating..." : "Building Semantic Report"}
            </button>
          </div>
        }
      />
      <CampaignWhatIf />
    </div>
  );
}
