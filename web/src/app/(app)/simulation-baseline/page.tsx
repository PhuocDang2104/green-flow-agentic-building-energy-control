import PageHeader from "@/components/shell/PageHeader";
import CampaignWhatIf from "@/components/simulation/CampaignWhatIf";

export default function SimulationBaselinePage() {
  return (
    <div data-wide-page className="pb-4">
      <PageHeader
        title="Validation Experiment"
        subtitle="El Nino 2024 - Hanoi: EnergyPlus baseline compared with the validated predictive MPC replay."
      />
      <CampaignWhatIf />
    </div>
  );
}
