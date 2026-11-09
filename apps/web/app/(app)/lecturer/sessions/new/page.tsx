import { PageHeader } from "@/components/page-header";
import { Card } from "@/components/ui/card";
import { NewSessionForm } from "@/features/new-session-form";

export default function NewSessionPage() {
  return (
    <div className="mx-auto max-w-xl">
      <PageHeader title="New attendance session" description="The session opens immediately. The QR code rotates every few seconds." />
      <Card>
        <NewSessionForm />
      </Card>
    </div>
  );
}
