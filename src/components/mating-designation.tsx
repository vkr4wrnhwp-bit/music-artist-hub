"use client";

import { useState } from "react";
import { inputClass } from "@/components/ui";
import { BearingStamp } from "@/components/bearing-stamp";

/**
 * The designation field, with the photograph route beside it.
 *
 * The provenance rule is enforced here rather than trusted from the form: the
 * value counts as confirmed-from-a-photograph only while it is still exactly
 * what was picked. Type a character afterwards and the photograph is no longer
 * what the value came from, so the evidence link is dropped and it is recorded
 * as typed. Anything else would attach a photograph to a number it does not
 * show.
 */
export function MatingDesignationField({
  featureId,
  initial,
  showPhoto,
}: {
  featureId: string;
  initial: string;
  showPhoto: boolean;
}) {
  const [value, setValue] = useState(initial);
  const [picked, setPicked] = useState<{ designation: string; photoId: string } | null>(null);
  const confirmedFromPhoto = picked !== null && picked.designation === value;

  return (
    <div>
      <label htmlFor="matingDesignation" className="tech-label mb-1 block">
        Designation, if known
      </label>
      <input
        id="matingDesignation"
        name="matingDesignation"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="e.g. 6203-2RS"
        className={inputClass}
      />
      <input
        type="hidden"
        name="matingDesignationSource"
        value={confirmedFromPhoto ? "PHOTO_CONFIRMED" : value.trim() === "" ? "" : "USER"}
      />
      <input type="hidden" name="matingDesignationPhotoId" value={confirmedFromPhoto ? picked.photoId : ""} />

      {confirmedFromPhoto && (
        <p className="mt-1 text-[11.5px] leading-relaxed text-review">
          Read from the photograph and not yet saved. Check it against the bearing before you save — this number
          decides a bore diameter.
        </p>
      )}

      {showPhoto && (
        <BearingStamp
          featureId={featureId}
          onPick={(designation, photoId) => {
            setValue(designation);
            setPicked({ designation, photoId });
          }}
        />
      )}
    </div>
  );
}
