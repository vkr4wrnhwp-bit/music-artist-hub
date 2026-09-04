import { notFound } from "next/navigation";
import Link from "next/link";
import { requireUser } from "@/lib/auth";
import { loadRevision } from "@/lib/data";
import { featureSummary, fmtTol } from "@/lib/domain/features";
import { TopBar } from "@/components/nav";
import { AddFeature } from "@/components/add-feature";
import { ProfileInput } from "@/components/profile-input";
import { Button, EmptyState, Notice, Panel, SectionHeading, StatusChip } from "@/components/ui";
import { createFeature, deleteFeature } from "./feature-actions";
import { importDxfProfile, saveDrawnProfile } from "./geometry-actions";

/**
 * THE PART'S FEATURES
 *
 * There was no page like this and no way to add a feature by hand: the only
 * route into a part's geometry was accepting an AI proposal. A shop wanting to
 * type in the 40 mm bore they are holding had nowhere to do it, and the empty
 * state told them to "add features" with no control to do it with.
 */

export default async function FeaturesPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const user = await requireUser();
  const revision = await loadRevision(user.organizationId, id);
  if (!revision) notFound();

  const byHand = revision.features.length;

  return (
    <>
      <TopBar>
        <Link href={`/parts/${id}`} className="tech-label hover:text-platinum">
          {revision.partName}
        </Link>
        <span className="text-muted">/</span>
        <span className="tech-label">Features</span>
      </TopBar>

      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">
          <SectionHeading sub="Geometry, and what each piece of it is responsible for. A part with no features has no manufacturing plan — nothing can be reached, held, cut or verified against nothing.">
            Features
          </SectionHeading>

          {/*
            The part's outside shape. `Feature.chain` was read by the contour
            engine and written by nothing, so every profile was a rounded
            rectangle from three numbers — an L-bracket came out a rectangle
            and nothing said so.
          */}
          <ProfileInput
            importDxf={importDxfProfile.bind(null, id)}
            saveDrawn={saveDrawnProfile.bind(null, id)}
            proposalsHref={`/parts/${id}/proposals`}
          />

          <AddFeature action={createFeature.bind(null, id)} />

          {byHand === 0 ? (
            <EmptyState
              title="No features yet"
              body="Add what the part has above, or accept the suggestions from the intake if a drawing or a scan produced any. A suggestion stays a suggestion until somebody accepts it."
              action={{ label: "Proposals", href: `/parts/${id}/proposals` }}
            />
          ) : (
            <Panel title={`Features — ${byHand}`} dense>
              <ul>
                {revision.features.map((f) => (
                  <li key={f.id} className="flex flex-wrap items-baseline justify-between gap-3 border-b border-line/60 px-4 py-3 last:border-0">
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-center gap-2 font-mono text-[12.5px] text-platinum">
                        <Link href={`/parts/${id}/features/${f.id}`} className="underline decoration-dotted hover:text-white">
                          {f.label}
                        </Link>
                        {f.critical && <StatusChip tone="risk">Critical</StatusChip>}
                      </p>
                      <p className="tech-label mt-0.5">
                        {f.kind.toLowerCase().replace(/_/g, " ")} · {featureSummary(f)}
                        {f.tolerance && ` · ${fmtTol(f.tolerance)}`}
                        {f.functionalRole !== "NONE" && ` · ${f.functionalRole.toLowerCase().replace(/_/g, " ")}`}
                      </p>
                    </div>
                    <form action={deleteFeature.bind(null, id)}>
                      <input type="hidden" name="featureId" value={f.id} />
                      <Button type="submit" size="sm" variant="danger">Remove</Button>
                    </form>
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          <Notice tone="review" title="Removing a feature removes the operations planned for it">
            An operation is the plan for cutting a specific feature. With the feature gone it points at nothing, so it
            goes too. The setups themselves stay.
          </Notice>
        </div>
      </main>
    </>
  );
}

export const dynamic = "force-dynamic";
