import { PageHeader } from "@/components/page-header";
import { CheckIn } from "@/features/check-in";

export default function ScanPage() {
  return (
    <div className="mx-auto max-w-md">
      <PageHeader title="Scan attendance QR" description="Point your camera at the code shown by your lecturer." />
      <CheckIn />
    </div>
  );
}
