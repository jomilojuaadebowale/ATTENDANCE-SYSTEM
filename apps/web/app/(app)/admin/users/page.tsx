import { PageHeader } from "@/components/page-header";
import { UserAdmin } from "@/features/user-admin";

export default function UsersPage() {
  return (
    <>
      <PageHeader title="Users" description="Create accounts before people sign in for the first time. Roles are controlled here, not in Firebase." />
      <UserAdmin />
    </>
  );
}
