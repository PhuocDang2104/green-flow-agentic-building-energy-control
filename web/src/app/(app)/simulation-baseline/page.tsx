import PageHeader from "@/components/shell/PageHeader";
import CampaignWhatIf from "@/components/simulation/CampaignWhatIf";

export default function SimulationBaselinePage() {
  return (
    <div className="pb-4">
      <PageHeader
        title="Control & Simulation"
        subtitle="Compare measured energy with the same period under an AI setpoint policy."
      />
      <CampaignWhatIf />
    </div>
  );
}
