import PageHeader from "@/components/shell/PageHeader";
import CampaignWhatIf from "@/components/simulation/CampaignWhatIf";

export default function SimulationBaselinePage() {
  return (
    <div data-wide-page className="pb-4">
      <PageHeader
        title="What-if Analysis"
        subtitle="Compare measured baseline with the precomputed predictive MPC replay."
      />
      <CampaignWhatIf />
    </div>
  );
}
