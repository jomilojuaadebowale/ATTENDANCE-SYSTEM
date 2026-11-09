import { LoginForm } from "@/features/login-form";

export default function LoginPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-semibold">University Attendance</h1>
        <p className="mt-1 text-sm text-slate-600">Sign in with the account your department set up for you.</p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <LoginForm />
      </div>
    </main>
  );
}
