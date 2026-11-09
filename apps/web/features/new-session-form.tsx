"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Alert, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { useFetch } from "@/hooks/use-fetch";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { getPosition } from "@/lib/geo";
import type { ClassSession, MyCourse, Venue } from "@/types/api";

const schema = z.object({
  course_id: z.string().min(1, "Choose a course"),
  venue_id: z.string(),
  duration_minutes: z.coerce.number().int().min(5, "At least 5 minutes").max(300, "At most 300 minutes"),
  radius_m: z.string().refine((v) => v === "" || (Number(v) >= 5 && Number(v) <= 1000), "Between 5 and 1000 metres"),
  use_my_location: z.boolean(),
});
type Input_ = z.input<typeof schema>;
type Output = z.output<typeof schema>;

export function NewSessionForm() {
  const { api } = useAuth();
  const router = useRouter();
  const courses = useFetch<MyCourse[]>("/me/courses");
  const venues = useFetch<Venue[]>("/venues");
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Input_, unknown, Output>({
    resolver: zodResolver(schema),
    defaultValues: { course_id: "", venue_id: "", duration_minutes: 60, radius_m: "", use_my_location: false },
  });

  async function onSubmit(v: Output) {
    setServerError(null);
    const body: Record<string, unknown> = { course_id: Number(v.course_id), duration_minutes: v.duration_minutes };
    if (v.venue_id) body.venue_id = Number(v.venue_id);
    if (v.radius_m) body.radius_m = Number(v.radius_m);
    if (v.use_my_location || !v.venue_id) {
      try {
        const pos = await getPosition();
        body.start_lat = pos.lat;
        body.start_lng = pos.lng;
      } catch (e) {
        if (!v.venue_id) {
          setError("venue_id", { message: "Choose a venue, or allow location so your position can be used." });
          return;
        }
        setServerError(`Could not read your location (${(e as Error).message}). The venue alone will be used.`);
      }
    }
    try {
      const s = await api.request<ClassSession>("/sessions", { method: "POST", body });
      router.push(`/lecturer/sessions/${s.id}`);
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Could not create the session.");
    }
  }

  if (courses.loading || venues.loading) return <Spinner />;
  if (courses.error) return <ErrorState error={courses.error} onRetry={() => void courses.reload()} />;
  if (venues.error) return <ErrorState error={venues.error} onRetry={() => void venues.reload()} />;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate aria-label="New attendance session">
      <Field label="Course" htmlFor="course_id" error={errors.course_id?.message}>
        <Select id="course_id" {...register("course_id")}>
          <option value="">Select a course…</option>
          {courses.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} — {c.title}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Lecture venue" htmlFor="venue_id" error={errors.venue_id?.message} hint="Students must be within the venue's radius to check in.">
        <Select id="venue_id" {...register("venue_id")}>
          <option value="">No fixed venue (use my location)</option>
          {venues.data?.map((v) => (
            <option key={v.id} value={v.id}>
              {v.name} ({v.default_radius_m} m)
            </option>
          ))}
        </Select>
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Duration (minutes)" htmlFor="duration_minutes" error={errors.duration_minutes?.message}>
          <Input id="duration_minutes" type="number" inputMode="numeric" {...register("duration_minutes")} />
        </Field>
        <Field label="Radius override (metres)" htmlFor="radius_m" error={errors.radius_m?.message} hint="Leave empty to use the venue default.">
          <Input id="radius_m" type="number" inputMode="numeric" {...register("radius_m")} />
        </Field>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" {...register("use_my_location")} /> Also use my current location as a check-in anchor
      </label>
      {serverError ? <Alert tone="error">{serverError}</Alert> : null}
      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating…" : "Start session"}
      </Button>
    </form>
  );
}
