import { TopBar } from "@/components/nav";
import { CommandBar } from "@/components/command-bar";
import { AxisTriad, Notice, Panel, SectionHeading } from "@/components/ui";

export default function NewPartPage() {
  return (
    <>
      <TopBar>
        <span className="tech-label">New part</span>
      </TopBar>
      <main className="flex-1 overflow-y-auto">
        <section className="precision-grid relative border-b border-line px-8 py-12">
          <AxisTriad className="absolute right-8 top-8 opacity-50" />
          <div className="mx-auto max-w-3xl">
            <SectionHeading sub="Describe the component the way you would to a machinist. CANVAS reduces it to a structured part intent model — every extracted field carries its source and confidence, and nothing becomes geometry until you confirm it.">
              What are we making?
            </SectionHeading>
            <CommandBar />
          </div>
        </section>

        <div className="mx-auto max-w-3xl space-y-6 p-8">
          <Panel title="What happens to your description">
            <ol className="space-y-3 text-[12.5px] leading-relaxed text-muted">
              <li>
                <span className="font-mono text-[11px] text-precision">01</span>{" "}
                <span className="text-platinum">Parse.</span> Dimensions, material, thread callouts, tolerances and
                features are extracted into the part intent model. Anything ambiguous becomes a named unknown rather
                than a guess.
              </li>
              <li>
                <span className="font-mono text-[11px] text-precision">02</span>{" "}
                <span className="text-platinum">Propose.</span> Parametric features are proposed, not created. They sit
                as suggestions until a human accepts them.
              </li>
              <li>
                <span className="font-mono text-[11px] text-precision">03</span>{" "}
                <span className="text-platinum">Interview.</span> CANVAS asks what the part actually does — load,
                environment, consequence of failure. It will not compare manufacturing processes without that.
              </li>
              <li>
                <span className="font-mono text-[11px] text-precision">04</span>{" "}
                <span className="text-platinum">Plan.</span> Stock, setups, workholding, tooling and operations, each
                validated against your machine and crib.
              </li>
            </ol>
          </Panel>

          <Notice tone="review" title="What CANVAS will not do">
            It will not invent a load case, a material substitution, a tolerance you did not state, or a machine
            capability you do not own. Where a value is missing it says so and stops, because a plausible number in a
            manufacturing plan is more dangerous than a blank one.
          </Notice>
        </div>
      </main>
    </>
  );
}
