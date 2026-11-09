import { PageHeader } from "@/components/page-header";
import { VenueAdmin } from "@/features/venue-admin";

export default function VenuesPage() {
  return (
    <>
      <PageHeader title="Lecture venues" description="Only approved venues can anchor a geofence." />
      <VenueAdmin />
    </>
  );
}
