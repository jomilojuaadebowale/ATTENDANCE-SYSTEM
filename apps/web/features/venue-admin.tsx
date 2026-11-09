"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Alert, EmptyState, ErrorState, Spinner } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { Table, Td, Th } from "@/components/ui/table";
import { useFetch } from "@/hooks/use-fetch";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Venue } from "@/types/api";

const schema = z.object({
  name: z.string().min(2, "Enter a name"),
  latitude: z.coerce.number().min(-90, "Between -90 and 90").max(90, "Between -90 and 90"),
  longitude: z.coerce.number().min(-180, "Between -180 and 180").max(180, "Between -180 and 180"),
  default_radius_m: z.coerce.number().int().min(5, "At least 5 m").max(1000, "At most 1000 m"),
});
type In = z.input<typeof schema>;
type Out = z.output<typeof schema>;

export function VenueAdmin() {
  const { api } = useAuth();
  const venues = useFetch<Venue[]>("/venues");
  const [msg, setMsg] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<In, unknown, Out>({ resolver: zodResolver(schema), defaultValues: { name: "", latitude: "", longitude: "", default_radius_m: 75 } });

  async function onSubmit(v: Out) {
    setMsg(null);
    try {
      await api.request("/venues", { method: "POST", body: v });
      reset();
      setMsg({ tone: "success", text: "Venue saved." });
      await venues.reload();
    } catch (e) {
      setMsg({ tone: "error", text: e instanceof ApiError ? e.message : "Could not save the venue." });
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card>
        <CardTitle>Add venue</CardTitle>
        <p className="mb-3 text-xs text-slate-500">Use surveyed coordinates of the hall&apos;s centre (for example from a map app) and a radius that covers the whole room.</p>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-3" noValidate aria-label="Add venue">
          <Field label="Name" htmlFor="v_name" error={errors.name?.message}>
            <Input id="v_name" {...register("name")} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Latitude" htmlFor="v_lat" error={errors.latitude?.message}>
              <Input id="v_lat" inputMode="decimal" {...register("latitude")} />
            </Field>
            <Field label="Longitude" htmlFor="v_lng" error={errors.longitude?.message}>
              <Input id="v_lng" inputMode="decimal" {...register("longitude")} />
            </Field>
          </div>
          <Field label="Radius (metres)" htmlFor="v_radius" error={errors.default_radius_m?.message}>
            <Input id="v_radius" inputMode="numeric" {...register("default_radius_m")} />
          </Field>
          {msg ? <Alert tone={msg.tone}>{msg.text}</Alert> : null}
          <Button type="submit" disabled={isSubmitting}>
            Save venue
          </Button>
        </form>
      </Card>
      <Card className="lg:col-span-2">
        <CardTitle>Approved venues</CardTitle>
        {venues.loading ? <Spinner /> : null}
        {venues.error ? <ErrorState error={venues.error} onRetry={() => void venues.reload()} /> : null}
        {venues.data?.length === 0 ? <EmptyState title="No venues yet" /> : null}
        {venues.data && venues.data.length > 0 ? (
          <Table>
            <thead>
              <tr>
                <Th>Name</Th>
                <Th>Latitude</Th>
                <Th>Longitude</Th>
                <Th>Radius</Th>
              </tr>
            </thead>
            <tbody>
              {venues.data.map((v) => (
                <tr key={v.id}>
                  <Td className="font-medium">{v.name}</Td>
                  <Td>{v.latitude}</Td>
                  <Td>{v.longitude}</Td>
                  <Td>{v.default_radius_m} m</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : null}
      </Card>
    </div>
  );
}
