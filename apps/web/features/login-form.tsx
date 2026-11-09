"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { useAuth } from "@/lib/auth";
import { config } from "@/lib/config";
import { HOME } from "@/lib/roles";

const schema = z.object({
  email: z.string().min(1, "Enter your email").email("Enter a valid email address"),
  password: z.string(),
});
type Values = z.infer<typeof schema>;

export function LoginForm() {
  const { signIn, status, me, error } = useAuth();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);
  const dev = config.authMode === "dev";
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  useEffect(() => {
    if (status === "signed_in" && me) router.replace(HOME[me.role]);
  }, [status, me, router]);

  async function onSubmit(values: Values) {
    setFormError(null);
    if (!dev && values.password.length < 6) {
      setError("password", { message: "Enter your password" });
      return;
    }
    try {
      await signIn(values.email, values.password);
    } catch {
      setFormError("Sign-in failed. Check your email and password.");
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate aria-label="Sign in">
      {dev ? (
        <Alert tone="warning" title="Development sign-in">
          Email-only sign-in is enabled for local development. It is refused by the API in production.
        </Alert>
      ) : null}
      <Field label="University email" htmlFor="email" error={errors.email?.message}>
        <Input id="email" type="email" autoComplete="username" {...register("email")} />
      </Field>
      {!dev ? (
        <Field label="Password" htmlFor="password" error={errors.password?.message}>
          <Input id="password" type="password" autoComplete="current-password" {...register("password")} />
        </Field>
      ) : null}
      {formError ? <Alert tone="error">{formError}</Alert> : null}
      {status === "not_provisioned" && error ? <Alert tone="error">{error}</Alert> : null}
      <Button type="submit" className="w-full" disabled={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
